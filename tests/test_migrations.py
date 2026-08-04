import inspect
from importlib.util import module_from_spec, spec_from_file_location
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

from alembic.migration import MigrationContext
from alembic.operations import Operations

MIGRATIONS_PATH = Path(__file__).parents[1] / "alembic/versions"
MIGRATION_PATH = MIGRATIONS_PATH / "002_bot_supervisor_schema.py"
CONSTRAINT_MIGRATION_PATH = MIGRATIONS_PATH / "003_bot_run_unique_constraint.py"
DROP_MIGRATION_PATH = MIGRATIONS_PATH / "004_drop_bot_runs.py"
UUID_MIGRATION_PATH = MIGRATIONS_PATH / "005_uuid_identity_migration.py"
INSTRUMENTS_MIGRATION_PATH = MIGRATIONS_PATH / "006_create_instruments_and_candles.py"
EXECUTION_MIGRATION_PATH = MIGRATIONS_PATH / "007_execution_state.py"


def load_migration(path: Path = MIGRATION_PATH):  # type: ignore[no-untyped-def]
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


def render_drop_migration(operation: str) -> str:
    output = StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql",
        opts={"as_sql": True, "output_buffer": output},
    )
    operations = Operations(context)
    migration = load_migration(DROP_MIGRATION_PATH)
    original_op = migration.op
    had_context = hasattr(migration, "context")
    original_context = getattr(migration, "context", None)
    migration.op = operations
    migration.context = SimpleNamespace(is_offline_mode=lambda: True)
    try:
        getattr(migration, operation)()
    finally:
        migration.op = original_op
        if had_context:
            migration.context = original_context
        else:
            del migration.context
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


def test_drop_migration_follows_constraint():
    migration = load_migration(DROP_MIGRATION_PATH)

    assert migration.revision == "004"
    assert migration.down_revision == "003"
    assert callable(migration.upgrade)
    assert callable(migration.downgrade)


def test_drop_migration_upgrade_drops_bot_runs():
    sql = render_drop_migration("upgrade")

    assert "DROP TABLE bot_runs" in sql


def test_drop_migration_downgrade_recreates_bot_runs():
    sql = render_drop_migration("downgrade")

    assert "CREATE TABLE bot_runs" in sql
    assert 'FOREIGN KEY(bot_id) REFERENCES bots (id) ON DELETE CASCADE' in sql
    assert "uq_bot_runs_bot_id" in sql


# --- migration 005 — UUID identity migration ---


def test_uuid_migration_follows_drop_bot_runs():
    migration = load_migration(UUID_MIGRATION_PATH)

    assert migration.revision == "005"
    assert migration.down_revision == "004"
    assert callable(migration.upgrade)
    assert callable(migration.downgrade)


def test_uuid_migration_lists_fk_columns_and_constraints():
    migration = load_migration(UUID_MIGRATION_PATH)
    fk_columns = migration._FK_COLUMNS

    assert fk_columns == (
        ("strategy_versions", "strategy_id"),
        ("bots", "account_id"),
        ("bots", "strategy_id"),
        ("bots", "strategy_version_id"),
        ("reconciliation_runs", "account_id"),
        ("reconciliation_runs", "bot_id"),
    )

    drop_source = inspect.getsource(migration._drop_foreign_keys)
    create_source = inspect.getsource(migration._create_foreign_keys)
    for table, column in fk_columns:
        constraint_name = f"{table}_{column}_fkey"
        assert constraint_name in drop_source
        assert constraint_name in create_source


def test_uuid_migration_lists_all_migrated_pk_tables():
    migration = load_migration(UUID_MIGRATION_PATH)

    assert "accounts" in migration._PK_TABLES
    assert "strategies" in migration._PK_TABLES
    assert "strategy_versions" in migration._PK_TABLES
    assert "bots" in migration._PK_TABLES
    assert "reconciliation_runs" in migration._PK_TABLES
    assert len(migration._PK_TABLES) == 5


def test_uuid_migration_upgrade_contains_uuid_casts():
    migration = load_migration(UUID_MIGRATION_PATH)
    source = inspect.getsource(migration.upgrade)

    assert "TYPE UUID USING" in source
    assert "DROP" in source or "_drop_foreign_keys" in source


def test_uuid_migration_downgrade_contains_varchar36_casts():
    migration = load_migration(UUID_MIGRATION_PATH)
    source = inspect.getsource(migration.downgrade)

    assert "TYPE VARCHAR(36)" in source


# --- migration 006 — instruments and candles ---


def test_instruments_migration_follows_uuid():
    migration = load_migration(INSTRUMENTS_MIGRATION_PATH)

    assert migration.revision == "006"
    assert migration.down_revision == "005"
    assert callable(migration.upgrade)
    assert callable(migration.downgrade)


def test_instruments_migration_renders_tables() -> None:
    output = StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql",
        opts={"as_sql": True, "output_buffer": output},
    )
    operations = Operations(context)
    migration = load_migration(INSTRUMENTS_MIGRATION_PATH)
    original_op = migration.op
    migration.op = operations
    try:
        migration.upgrade()
    finally:
        migration.op = original_op
    sql = output.getvalue()

    # instruments table
    assert "CREATE TABLE instruments" in sql
    assert sql.count("id UUID DEFAULT gen_random_uuid() NOT NULL") == 2
    assert "UNIQUE (symbol, provider)" in sql
    assert "asset_type" in sql
    assert "constraints" in sql

    # candles table
    assert "CREATE TABLE candles" in sql
    assert "FOREIGN KEY(instrument_id) REFERENCES instruments (id)" in sql
    assert "price_basis" in sql
    assert "base_volume NUMERIC(20, 8) DEFAULT 0 NOT NULL" in sql
    assert "quote_volume" in sql
    assert "trade_count" in sql
    assert "tick_volume" in sql
    assert "is_complete" in sql

    # Uniqueness constraint
    assert "UNIQUE" in sql and "instrument_id" in sql and "price_basis" in sql

    # Lookup index
    assert "idx_candles_lookup" in sql


def test_instruments_migration_downgrade_drops_in_correct_order() -> None:
    output = StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql",
        opts={"as_sql": True, "output_buffer": output},
    )
    operations = Operations(context)
    migration = load_migration(INSTRUMENTS_MIGRATION_PATH)
    original_op = migration.op
    migration.op = operations
    try:
        migration.downgrade()
    finally:
        migration.op = original_op
    sql = output.getvalue()

    # Index must be dropped before table
    assert sql.index("DROP INDEX") < sql.index("DROP TABLE candles")
    # candles must be dropped before instruments (FK dependency)
    assert sql.index("DROP TABLE candles") < sql.index("DROP TABLE instruments")


def test_execution_migration_follows_instruments_and_has_execution_tables() -> None:
    migration = load_migration(EXECUTION_MIGRATION_PATH)

    assert migration.revision == "007"
    assert migration.down_revision == "006"
    assert callable(migration.upgrade)
    assert callable(migration.downgrade)


def test_execution_migration_contains_idempotency_and_active_position_constraints() -> None:
    output = StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql",
        opts={"as_sql": True, "output_buffer": output},
    )
    operations = Operations(context)
    migration = load_migration(EXECUTION_MIGRATION_PATH)
    original_op = migration.op
    migration.op = operations
    try:
        migration.upgrade()
    finally:
        migration.op = original_op
    sql = output.getvalue()

    assert "CREATE TABLE orders" in sql
    assert "CREATE TABLE fills" in sql
    assert "CREATE TABLE positions" in sql
    assert "CREATE TABLE trades" in sql
    assert "UNIQUE (client_order_id)" in sql
    assert "idx_fills_broker_execution" in sql
    assert "idx_one_active_net_position" in sql
    assert "status IN ('open', 'reducing')" in sql
