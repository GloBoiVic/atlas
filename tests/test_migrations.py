from importlib.util import module_from_spec, spec_from_file_location
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

from alembic.migration import MigrationContext
from alembic.operations import Operations

MIGRATIONS_PATH = Path(__file__).parents[1] / "alembic/versions"
MIGRATION_PATH = MIGRATIONS_PATH / "002_bot_supervisor_schema.py"
CONSTRAINT_MIGRATION_PATH = MIGRATIONS_PATH / "003_bot_run_unique_constraint.py"


def load_migration(path: Path = MIGRATION_PATH):
    spec = spec_from_file_location("migration", path)
    assert spec is not None
    assert spec.loader is not None
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def render_migration(operation: str) -> str:
    output = StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql",
        opts={"as_sql": True, "output_buffer": output},
    )
    operations = Operations(context)
    migration = load_migration()
    original_op = migration.op
    migration.op = operations
    try:
        getattr(migration, operation)()
    finally:
        migration.op = original_op
    return output.getvalue()


def render_constraint_migration(operation: str) -> str:
    output = StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql",
        opts={"as_sql": True, "output_buffer": output},
    )
    operations = Operations(context)
    migration = load_migration(CONSTRAINT_MIGRATION_PATH)
    original_op = migration.op
    original_context = migration.context
    migration.op = operations
    migration.context = SimpleNamespace(is_offline_mode=lambda: True)
    try:
        getattr(migration, operation)()
    finally:
        migration.op = original_op
        migration.context = original_context
    return output.getvalue()


def test_bot_supervisor_migration_follows_initial_schema():
    migration = load_migration()

    assert migration.revision == "002"
    assert migration.down_revision == "001"
    assert callable(migration.upgrade)
    assert callable(migration.downgrade)


def test_upgrade_renders_reference_tables_and_constraints():
    sql = render_migration("upgrade")

    assert sql.index("CREATE TABLE strategies") < sql.index("CREATE TABLE bots")
    assert sql.index("CREATE TABLE strategy_versions") < sql.index("CREATE TABLE bots")
    assert 'FOREIGN KEY(strategy_id) REFERENCES strategies (id)' in sql
    assert 'FOREIGN KEY(strategy_version_id) REFERENCES strategy_versions (id)' in sql
    assert "pnl NUMERIC(20, 8) DEFAULT 0" in sql
    assert 'pnl NUMERIC(20, 8) DEFAULT 0 NOT NULL' not in sql
    assert "CONSTRAINT uq_bot_runs_bot_id UNIQUE (bot_id)" not in sql


def test_constraint_migration_follows_bot_supervisor_schema():
    migration = load_migration(CONSTRAINT_MIGRATION_PATH)

    assert migration.revision == "003"
    assert migration.down_revision == "002"


def test_constraint_migration_adds_and_removes_unique_constraint():
    upgrade_sql = render_constraint_migration("upgrade")
    downgrade_sql = render_constraint_migration("downgrade")

    assert "ALTER TABLE bot_runs ADD CONSTRAINT uq_bot_runs_bot_id UNIQUE (bot_id)" in upgrade_sql
    assert "ALTER TABLE bot_runs DROP CONSTRAINT uq_bot_runs_bot_id" in downgrade_sql


def test_downgrade_drops_dependents_before_reference_tables():
    sql = render_migration("downgrade")

    assert sql.index('DROP TABLE reconciliation_runs') < sql.index('DROP TABLE strategies')
    assert sql.index('DROP TABLE bot_runs') < sql.index('DROP TABLE strategies')
    assert sql.index('DROP TABLE bots') < sql.index('DROP TABLE strategy_versions')
    assert sql.index('DROP TABLE strategy_versions') < sql.index('DROP TABLE strategies')
    assert 'ALTER TABLE bot_runs DROP CONSTRAINT uq_bot_runs_bot_id' not in sql
