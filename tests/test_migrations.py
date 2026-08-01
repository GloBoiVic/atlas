from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

MIGRATION_PATH = Path(__file__).parents[1] / "alembic/versions/002_bot_supervisor_schema.py"


def test_bot_supervisor_migration_follows_initial_schema():
    spec = spec_from_file_location("bot_supervisor_migration", MIGRATION_PATH)
    assert spec is not None
    assert spec.loader is not None
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)

    assert migration.revision == "002"
    assert migration.down_revision == "001"
    assert callable(migration.upgrade)
    assert callable(migration.downgrade)
