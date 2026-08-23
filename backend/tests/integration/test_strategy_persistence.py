from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from backend.domain.market_data import Timeframe
from backend.domain.strategy import ParameterSchema, StrategyVersion
from backend.persistence.database import (
    configure_utc_session_timezone,
    create_session_factory,
)
from backend.persistence.strategy_repository import StrategyRepository
from backend.strategies.fingerprint import SourceArchive, archive_source

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def persistence_database(database_url: str):
    engine = configure_utc_session_timezone(create_engine(database_url))
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    config = Config(str(Path(__file__).parents[3] / "alembic.ini"))
    config.set_main_option("script_location", "backend/persistence/migrations")
    import os

    os.environ["ATLAS_DATABASE_URL"] = database_url
    command.upgrade(config, "head")
    yield engine
    command.downgrade(config, "base")
    engine.dispose()


@pytest.fixture(scope="module")
def database_url():
    import os

    value = os.environ.get("ATLAS_TEST_DATABASE_URL")
    if not value:
        pytest.fail("ATLAS_TEST_DATABASE_URL is required for integration tests")
    return value


def _version(fingerprint: str, identifier: UUID | None = None) -> StrategyVersion:
    return StrategyVersion(
        id=identifier or uuid4(),
        strategy_key="test_strategy",
        version_number=1,
        source_fingerprint=fingerprint,
        implementation_key="test_strategy.v1",
        parameter_schema=(
            ParameterSchema("period", "Period", "integer", 14, False, 1, 100, "period"),
        ),
        primary_timeframe=Timeframe.M15,
        warm_up_bars=100,
        state_schema_version=1,
        created_at=datetime.now(UTC),
    )


def _archive() -> SourceArchive:
    return archive_source(
        Path(__file__).parents[3], ("backend/strategies/fingerprint.py",)
    )


def test_create_read_uuid_utc_jsonb_and_idempotency(
    persistence_database: Engine,
) -> None:
    factory = create_session_factory(persistence_database)
    repository = StrategyRepository()
    archive = _archive()
    version = _version(archive.fingerprint)
    with factory.begin() as session:
        first = repository.create_version(
            session,
            version,
            strategy_name="Test",
            strategy_description="Test strategy",
            capabilities=("LONG",),
            source_archive=archive,
            git_sha="a" * 40,
        )
        second = repository.create_version(
            session,
            _version(archive.fingerprint),
            strategy_name="Ignored",
            strategy_description="Ignored",
            source_archive=archive,
        )
        assert first.id == second.id
        assert first.version_number == 1
        assert first.source_manifest[0]["byte_length"] > 0
        assert first.exact_source_snapshot["backend/strategies/fingerprint.py"]
        assert first.created_at.tzinfo is not None
        assert first.strategy_id is not None


def test_changed_fingerprint_gets_next_version_and_mismatch_is_rejected(
    persistence_database: Engine,
) -> None:
    factory = create_session_factory(persistence_database)
    repository = StrategyRepository()
    archive = _archive()
    with factory.begin() as session:
        repository.create_version(
            session,
            _version(archive.fingerprint),
            strategy_name="Test",
            strategy_description="Test",
            source_archive=archive,
        )
        changed = SourceArchive((), "a" * 64)
        next_version = repository.create_version(
            session,
            _version("a" * 64),
            strategy_name="Test",
            strategy_description="Test",
            source_archive=changed,
        )
        assert next_version.version_number == 2
        with pytest.raises(ValueError, match="does not match"):
            repository.create_version(
                session,
                _version("b" * 64),
                strategy_name="Test",
                strategy_description="Test",
                source_archive=changed,
            )


def test_constraints_and_strategy_version_append_only_trigger(
    persistence_database: Engine,
) -> None:
    factory = create_session_factory(persistence_database)
    repository = StrategyRepository()
    archive = _archive()
    with factory.begin() as session:
        row = repository.create_version(
            session,
            _version(archive.fingerprint),
            strategy_name="Test",
            strategy_description="Test",
            source_archive=archive,
        )
        with pytest.raises(SQLAlchemyError):
            with session.begin_nested():
                session.execute(
                    text(
                        "UPDATE strategy_versions SET implementation_key = 'changed' "
                        "WHERE id = :id"
                    ),
                    {"id": row.id},
                )
        with pytest.raises(SQLAlchemyError):
            with session.begin_nested():
                session.execute(
                    text("DELETE FROM strategy_versions WHERE id = :id"),
                    {"id": row.id},
                )
        with pytest.raises(IntegrityError):
            with session.begin_nested():
                session.execute(
                    text("DELETE FROM strategies WHERE id = :id"),
                    {"id": row.strategy_id},
                )
