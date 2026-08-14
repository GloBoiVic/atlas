import os
from pathlib import Path
from urllib.parse import urlparse

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def migration_url() -> str:
    value = os.environ.get("ATLAS_TEST_DATABASE_URL")
    if not value:
        pytest.fail("ATLAS_TEST_DATABASE_URL is required for integration tests")
    if not urlparse(value).path.rsplit("/", 1)[-1].endswith("_test"):
        pytest.fail("migration reset requires a database name ending in _test")
    return value


def alembic_config(url: str) -> Config:
    config = Config(str(Path(__file__).parents[3] / "alembic.ini"))
    config.set_main_option("script_location", "backend/persistence/migrations")
    os.environ["ATLAS_DATABASE_URL"] = url
    return config


def test_migration_cycle(migration_url: str) -> None:
    engine = create_engine(migration_url)
    try:
        with engine.begin() as connection:
            connection.execute(text("DROP SCHEMA public CASCADE"))
            connection.execute(text("CREATE SCHEMA public"))
        config = alembic_config(migration_url)
        command.upgrade(config, "head")
        inspector = inspect(engine)
        assert inspector.get_table_names() == [
            "alembic_version",
            "strategies",
            "strategy_versions",
        ]
        command.check(config)
        command.downgrade(config, "base")
        assert inspect(engine).get_table_names() == ["alembic_version"]
        command.upgrade(config, "head")
    finally:
        engine.dispose()
