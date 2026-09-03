"""PostgreSQL concurrency evidence for the PAPER 06 runtime owner."""

import concurrent.futures
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from os import environ
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from backend.persistence.database import (
    configure_utc_session_timezone,
    create_session_factory,
)
from backend.persistence.runtime_repository import (
    PaperRuntimeOwnerLost,
    PaperRuntimeRepository,
)
from backend.runtime import (
    PaperRuntimeOwner,
    PaperRuntimeOwnership,
    PaperRuntimeOwnershipPhase,
)

pytestmark = pytest.mark.integration

NOW = datetime(2026, 9, 3, 12, tzinfo=UTC)


@pytest.fixture
def runtime_database() -> Generator[Engine]:
    value = environ.get("ATLAS_TEST_DATABASE_URL")
    if not value or not value.rsplit("/", 1)[-1].endswith("_test"):
        pytest.skip("ATLAS_TEST_DATABASE_URL must name a dedicated *_test database")
    engine = configure_utc_session_timezone(create_engine(value))
    yield engine
    engine.dispose()


def make_owner(engine: Engine) -> PaperRuntimeOwner:
    return PaperRuntimeOwner(
        engine,
        create_session_factory(engine),
        clock=lambda: NOW,
    )


def test_two_owners_have_one_winner_and_stale_heartbeat_cannot_take_lock(
    runtime_database: Engine,
) -> None:
    first = make_owner(runtime_database)
    second = make_owner(runtime_database)
    try:
        ownership = first.try_acquire()
        assert ownership is not None
        assert ownership.owner_generation == 1
        assert second.try_acquire() is None

        factory = create_session_factory(runtime_database)
        with factory() as session:
            row = first.heartbeat(
                session,
                heartbeat_at=NOW - timedelta(days=1),
                phase=PaperRuntimeOwnershipPhase.RUNNING,
            )
            session.commit()
            assert row.heartbeat_at == NOW - timedelta(days=1)

        # Heartbeat age is audit evidence, never takeover authority.
        assert second.try_acquire() is None

        # Explicit owner shutdown also releases the session-level lock rather
        # than returning a still-locked pooled connection to the pool.
        first.close()
        successor = second.try_acquire()
        assert successor is not None
        assert successor.owner_generation == ownership.owner_generation + 1
    finally:
        first.close()
        second.close()


def test_connection_death_releases_lock_and_successor_advances_generation(
    runtime_database: Engine,
) -> None:
    first = make_owner(runtime_database)
    second = make_owner(runtime_database)
    try:
        first_ownership = first.try_acquire()
        assert first_ownership is not None
        first.connection.invalidate()

        successor = second.try_acquire()
        assert successor is not None
        assert successor.owner_generation == first_ownership.owner_generation + 1
        assert successor.owner_id != first_ownership.owner_id
    finally:
        first.close()
        second.close()


def test_concurrent_sessions_produce_exactly_one_owner(
    runtime_database: Engine,
) -> None:
    first = make_owner(runtime_database)
    second = make_owner(runtime_database)
    barrier = Barrier(2)
    results: list[PaperRuntimeOwnership | None] = []
    errors: list[BaseException] = []

    def acquire(owner: PaperRuntimeOwner) -> None:
        try:
            barrier.wait()
            results.append(owner.try_acquire())
        except BaseException as error:  # pragma: no cover - diagnostic guard
            errors.append(error)

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(acquire, first),
                executor.submit(acquire, second),
            ]
            for future in futures:
                future.result()
        assert errors == []
        assert len(results) == 2
        assert sum(result is not None for result in results) == 1
    finally:
        first.close()
        second.close()


def test_owner_generation_zero_row_update_is_loss(runtime_database: Engine) -> None:
    owner = make_owner(runtime_database)
    repository = PaperRuntimeRepository()
    try:
        ownership = owner.try_acquire()
        assert ownership is not None

        replacement = PaperRuntimeOwnership(
            owner_id=uuid4(),
            activation_id=None,
            owner_generation=ownership.owner_generation + 1,
            acquired_at=NOW,
            heartbeat_at=NOW,
            phase=PaperRuntimeOwnershipPhase.RUNNING,
        )
        factory = create_session_factory(runtime_database)
        with factory() as session:
            repository.record_ownership_after_lock(session, replacement)
            session.commit()

        with factory() as session:
            with pytest.raises(PaperRuntimeOwnerLost):
                owner.heartbeat(session)
    finally:
        owner.close()
