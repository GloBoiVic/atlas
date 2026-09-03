"""Dedicated PostgreSQL migration evidence for PAPER 06 runtime tables."""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path
from urllib.parse import urlparse

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

from backend.persistence.database import configure_utc_session_timezone

pytestmark = pytest.mark.integration


@pytest.fixture
def migration_database() -> Generator[Engine]:
    value = os.environ.get("ATLAS_TEST_DATABASE_URL")
    if not value or not urlparse(value).path.rsplit("/", 1)[-1].endswith("_test"):
        pytest.skip("ATLAS_TEST_DATABASE_URL must name a dedicated *_test database")
    engine = configure_utc_session_timezone(create_engine(value))
    yield engine
    engine.dispose()


def _config(url: str) -> Config:
    config = Config(str(Path(__file__).parents[3] / "alembic.ini"))
    config.set_main_option("script_location", "backend/persistence/migrations")
    os.environ["ATLAS_DATABASE_URL"] = url
    return config


def test_runtime_migration_upgrade_prior_head_upgrade_and_checks(
    migration_database: Engine,
) -> None:
    url = os.environ["ATLAS_TEST_DATABASE_URL"]
    config = _config(url)

    command.upgrade(config, "head")
    assert {
        "paper_runtime_activations",
        "paper_runtime_cycles",
        "paper_runtime_ownership",
    } <= set(inspect(migration_database).get_table_names())
    with migration_database.connect() as connection:
        risk_column = connection.execute(
            text(
                """
                SELECT data_type, numeric_precision, numeric_scale
                FROM information_schema.columns
                WHERE table_name = 'paper_runtime_activations'
                  AND column_name = 'risk_per_trade'
                """
            )
        ).one()
        assert risk_column == ("numeric", None, None)

    command.downgrade(config, "0022_paper_persistence")
    assert not {
        "paper_runtime_activations",
        "paper_runtime_cycles",
        "paper_runtime_ownership",
    } & set(inspect(migration_database).get_table_names())

    command.upgrade(config, "head")
    command.current(config, verbose=False)
    command.check(config)
    with migration_database.connect() as connection:
        version = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
        assert version == "0023_paper_runtime_activation"
