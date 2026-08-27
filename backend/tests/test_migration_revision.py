from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_alembic_revision_ids_fit_default_version_column() -> None:
    config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
    config.set_main_option("script_location", "backend/persistence/migrations")
    scripts = ScriptDirectory.from_config(config)

    assert all(len(script.revision) <= 32 for script in scripts.walk_revisions())
    assert scripts.get_heads() == ["0016_load_progress"]
