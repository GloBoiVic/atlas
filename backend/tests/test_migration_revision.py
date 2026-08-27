import ast
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_alembic_revision_ids_fit_default_version_column() -> None:
    config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
    config.set_main_option("script_location", "backend/persistence/migrations")
    scripts = ScriptDirectory.from_config(config)

    assert all(len(script.revision) <= 32 for script in scripts.walk_revisions())
    assert scripts.get_heads() == ["0018_acquisition_windows"]


def test_native_resolution_migration_uses_logical_constraint_names() -> None:
    path = (
        Path(__file__).parents[1]
        / "persistence/migrations/versions/0015_native_market_bar_resolutions.py"
    )
    tree = ast.parse(path.read_text())
    dropped_names = [
        call.args[0].value
        for call in ast.walk(tree)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Attribute)
        and call.func.attr == "drop_constraint"
        and call.args
        and isinstance(call.args[0], ast.Constant)
    ]

    assert dropped_names == [
        "m1_only",
        "exact_one_minute",
        "minute_aligned_start",
        "exact_native_interval",
        "native_aligned_start",
        "supported_resolution",
    ]
