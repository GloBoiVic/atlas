from urllib.parse import urlparse

import pytest
from pydantic import SecretStr
from sqlalchemy import select, text

from backend.config import Settings
from backend.persistence.database import (
    check_database,
    configure_utc_session_timezone,
    create_database_engine,
    create_session_factory,
)

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def database_url() -> str:
    import os

    value = os.environ.get("ATLAS_TEST_DATABASE_URL")
    if not value:
        pytest.fail("ATLAS_TEST_DATABASE_URL is required for integration tests")
    database = urlparse(value).path.rsplit("/", 1)[-1]
    if not database.endswith("_test"):
        pytest.fail("integration tests require a database name ending in _test")
    return value


def test_real_connection_and_session(database_url: str) -> None:
    settings = Settings(
        database_url=SecretStr(database_url), database_connect_timeout_seconds=7
    )
    engine = create_database_engine(settings)
    try:
        assert settings.database_connect_timeout_seconds == 7
        check_database(engine)
        factory = create_session_factory(engine)
        with factory() as session:
            assert session.execute(select(1)).scalar_one() == 1
    finally:
        engine.dispose()


def test_utc_policy_covers_fresh_reused_reconnected_and_timestamptz(
    database_url: str,
) -> None:
    settings = Settings(database_url=SecretStr(database_url))
    engine = create_database_engine(settings)
    try:
        factory = create_session_factory(engine)
        with factory() as session:
            assert session.scalar(text("SHOW TIME ZONE")) == "UTC"
            value = session.scalar(
                text("SELECT TIMESTAMPTZ '2026-01-01 12:00:00+00'")
            )
            assert value.tzinfo is not None
            assert value.utcoffset().total_seconds() == 0
        with factory() as session, session.begin():
            assert session.scalar(select(1)) == 1

        # A committed session change must not leak through the pool.
        with engine.begin() as connection:
            connection.execute(text("SET SESSION TIME ZONE 'America/Chicago'"))
        with factory() as session:
            assert (
                session.scalar(text("SELECT current_setting('TimeZone')")) == "UTC"
            )

        configure_utc_session_timezone(engine)
        configure_utc_session_timezone(engine)
        engine.dispose()
        with factory() as session:
            assert (
                session.scalar(text("SELECT current_setting('TimeZone')")) == "UTC"
            )
    finally:
        engine.dispose()
