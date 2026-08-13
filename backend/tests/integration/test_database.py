from urllib.parse import urlparse

import pytest
from pydantic import SecretStr
from sqlalchemy import select

from backend.config import Settings
from backend.persistence.database import (
    check_database,
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
