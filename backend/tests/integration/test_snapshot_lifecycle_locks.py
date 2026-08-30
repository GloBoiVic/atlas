# ruff: noqa: F401, F811
"""Deterministic PostgreSQL proof for snapshot lifetime and lifecycle locks."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from threading import Event, Thread
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import Session

import backend.persistence.experiment_deletion as deletion_module
import backend.persistence.historical_data_load_repository as load_module
from backend.persistence.experiment_deletion import ExperimentDeletionRepository
from backend.persistence.experiment_repository import ExperimentRepository
from backend.persistence.historical_data_load_repository import (
    HistoricalDataLoadRepository,
)
from backend.persistence.lifecycle_locks import acquire_historical_load_lifecycle_lock
from backend.persistence.models import (
    DatasetSnapshotAnalyticalBarModel,
    DatasetSnapshotBarModel,
    DatasetSnapshotExecutionObservationModel,
    DatasetSnapshotGapModel,
    DatasetSnapshotModel,
    ExperimentModel,
    HistoricalDataLoadRequestModel,
)
from backend.tests.integration.test_golden_flows import _seed, database_url

pytestmark = pytest.mark.integration

_START = datetime(2026, 1, 5, 0, tzinfo=UTC)
_END = _START + timedelta(minutes=15)
_MEMBERSHIP_MODELS = (
    DatasetSnapshotBarModel,
    DatasetSnapshotAnalyticalBarModel,
    DatasetSnapshotExecutionObservationModel,
    DatasetSnapshotGapModel,
)


def _engine(database_url: str):
    from sqlalchemy import create_engine

    from backend.persistence.database import configure_utc_session_timezone

    return configure_utc_session_timezone(create_engine(database_url))


def _seed_one(session: Session) -> tuple[UUID, UUID, UUID]:
    experiment_id, snapshot_id, version_id = _seed(session, "LONG")
    session.execute(
        update(ExperimentModel)
        .where(ExperimentModel.id == experiment_id)
        .values(status="PENDING")
    )
    session.flush()
    return experiment_id, snapshot_id, version_id


def _snapshot_counts(session: Session, snapshot_id: UUID) -> dict[str, int]:
    return {
        model.__tablename__: len(
            session.scalars(
                select(model).where(model.dataset_snapshot_id == snapshot_id)
            ).all()
        )
        for model in _MEMBERSHIP_MODELS
    }


def _create_pending(
    engine: Any, version_id: UUID
) -> UUID:
    with Session(engine) as session, session.begin():
        row = HistoricalDataLoadRepository().create_pending(
            session,
            strategy_version_id=version_id,
            trading_start=_START,
            trading_end=_END,
            load_start=_START,
            load_end=_END,
        )
        return row.id


def _create_failed_without_snapshot(engine: Any, version_id: UUID) -> UUID:
    request_id = _create_pending(engine, version_id)
    with Session(engine) as session, session.begin():
        repository = HistoricalDataLoadRepository()
        assert repository.fail_if_active(
            session,
            request_id,
            category="RUNTIME",
            code="TEST_FAILURE",
            detail="Deterministic lifecycle-lock proof",
        )
    return request_id


def _finish_active_load(
    engine: Any, request_id: UUID, *, snapshot_id: UUID | None = None
) -> None:
    with Session(engine) as session, session.begin():
        HistoricalDataLoadRepository().fail_if_active(
            session,
            request_id,
            category="RUNTIME",
            code="TEST_CLEANUP",
            detail="Deterministic test cleanup",
            snapshot_id=snapshot_id,
        )


def _join(
    thread: Thread, errors: list[BaseException], *, timeout: float = 10
) -> None:
    thread.join(timeout=timeout)
    assert not thread.is_alive(), "concurrent proof did not complete"
    assert not errors, errors


def test_shared_snapshot_is_retained_with_all_memberships(
    database_url: str,
) -> None:
    engine = _engine(database_url)
    with Session(engine) as session:
        experiment_id, snapshot_id, version_id = _seed_one(session)
        first = session.get(ExperimentModel, experiment_id)
        assert first is not None
        second = ExperimentRepository().create(
            session,
            strategy_version_id=version_id,
            dataset_snapshot_id=snapshot_id,
            venue_instrument_id=first.venue_instrument_id,
            trading_start=first.trading_start,
            trading_end=first.trading_end,
            starting_capital=first.starting_capital,
            risk_per_trade=first.risk_per_trade,
            parameter_snapshot=first.parameter_snapshot,
            risk_config=first.risk_config,
            simulation_config=first.simulation_config,
            model_version=first.model_version,
        )
        ExperimentRepository().create_account_and_position(session, second)
        counts = _snapshot_counts(session, snapshot_id)
        session.commit()
        second_id = second.id

    with Session(engine) as session, session.begin():
        result = ExperimentDeletionRepository().delete(session, experiment_id)
        assert result.snapshot_deleted is False

    with Session(engine) as session:
        assert session.get(ExperimentModel, experiment_id) is None
        assert session.get(ExperimentModel, second_id) is not None
        assert session.get(DatasetSnapshotModel, snapshot_id) is not None
        assert _snapshot_counts(session, snapshot_id) == counts
    engine.dispose()


@pytest.mark.parametrize("terminal_status", ["COMPLETED", "FAILED"])
def test_terminal_load_reference_retains_snapshot(
    database_url: str, terminal_status: str
) -> None:
    engine = _engine(database_url)
    with Session(engine) as session:
        experiment_id, snapshot_id, version_id = _seed_one(session)
        counts = _snapshot_counts(session, snapshot_id)
        session.commit()

    request_id = _create_pending(engine, version_id)
    with Session(engine) as session, session.begin():
        repository = HistoricalDataLoadRepository()
        assert repository.claim(session, request_id) is not None
        if terminal_status == "COMPLETED":
            assert repository.complete(
                session,
                request_id,
                snapshot_id=snapshot_id,
                coverage_summary={"valid": True},
                experiment_validation={"valid": True},
            )
        else:
            assert repository.fail_if_active(
                session,
                request_id,
                category="MARKET_DATA",
                code="TEST_FAILURE",
                detail="Terminal retention proof",
                snapshot_id=snapshot_id,
            )

    with Session(engine) as session, session.begin():
        result = ExperimentDeletionRepository().delete(session, experiment_id)
        assert result.snapshot_deleted is False

    with Session(engine) as session:
        load = session.get(HistoricalDataLoadRequestModel, request_id)
        assert load is not None
        assert load.status == terminal_status
        assert load.snapshot_id == snapshot_id
        assert session.get(DatasetSnapshotModel, snapshot_id) is not None
        assert _snapshot_counts(session, snapshot_id) == counts
    engine.dispose()


@pytest.mark.parametrize("active_status", ["PENDING", "RUNNING"])
def test_active_load_without_snapshot_attachment_retains_snapshot(
    database_url: str, active_status: str
) -> None:
    engine = _engine(database_url)
    with Session(engine) as session:
        experiment_id, snapshot_id, version_id = _seed_one(session)
        counts = _snapshot_counts(session, snapshot_id)
        session.commit()

    request_id = _create_pending(engine, version_id)
    if active_status == "RUNNING":
        with Session(engine) as session, session.begin():
            assert HistoricalDataLoadRepository().claim(session, request_id) is not None

    try:
        with Session(engine) as session, session.begin():
            result = ExperimentDeletionRepository().delete(session, experiment_id)
            assert result.snapshot_deleted is False

        with Session(engine) as session:
            load = session.get(HistoricalDataLoadRequestModel, request_id)
            assert load is not None
            assert load.status == active_status
            assert load.snapshot_id is None
            assert session.get(DatasetSnapshotModel, snapshot_id) is not None
            assert _snapshot_counts(session, snapshot_id) == counts
    finally:
        _finish_active_load(engine, request_id)
        engine.dispose()


@pytest.mark.parametrize(
    ("activation_kind", "winner"),
    [
        ("PENDING", "activation_first"),
        ("PENDING", "deletion_first"),
        ("FAILED_RESUME", "activation_first"),
        ("FAILED_RESUME", "deletion_first"),
    ],
)
def test_lifecycle_activation_and_deletion_race_is_serialized(
    database_url: str, activation_kind: str, winner: str, monkeypatch
) -> None:
    engine = _engine(database_url)
    with Session(engine) as session:
        experiment_id, snapshot_id, version_id = _seed_one(session)
        session.commit()
    request_id = (
        _create_failed_without_snapshot(engine, version_id)
        if activation_kind == "FAILED_RESUME"
        else None
    )

    def pending(session: Session) -> UUID:
        return HistoricalDataLoadRepository().create_pending(
            session,
            strategy_version_id=version_id,
            trading_start=_START,
            trading_end=_END,
            load_start=_START,
            load_end=_END,
        ).id

    def activate(session: Session) -> UUID:
        if activation_kind == "PENDING":
            return pending(session)
        assert request_id is not None
        assert HistoricalDataLoadRepository().resume(session, request_id)
        return request_id

    deletion_result: list[Any] = []
    errors: list[BaseException] = []
    deletion_done = Event()

    def delete_worker() -> None:
        try:
            with Session(engine) as session, session.begin():
                deletion_result.append(
                    ExperimentDeletionRepository().delete(session, experiment_id)
                )
        except BaseException as error:  # report worker failures in the test thread
            errors.append(error)
        finally:
            deletion_done.set()

    activation_session: Session | None = None
    activated_request_id: UUID | None = request_id
    try:
        if winner == "activation_first":
            activation_session = Session(engine)
            activation_session.begin()
            acquire_historical_load_lifecycle_lock(activation_session)
            activated_request_id = activate(activation_session)
            activation_session.flush()

            deletion_attempted = Event()
            original_delete_lock = (
                deletion_module.acquire_historical_load_lifecycle_lock
            )

            def observe_delete_lock(session: Session) -> None:
                deletion_attempted.set()
                original_delete_lock(session)

            monkeypatch.setattr(
                deletion_module,
                "acquire_historical_load_lifecycle_lock",
                observe_delete_lock,
            )
            deletion_thread = Thread(target=delete_worker)
            deletion_thread.start()
            assert deletion_attempted.wait(timeout=10)
            assert not deletion_done.is_set()
            activation_session.commit()
            activation_session.close()
            activation_session = None
            _join(deletion_thread, errors)
        else:
            deletion_acquired = Event()
            release_deletion = Event()
            activation_attempted = Event()
            original_delete_lock = (
                deletion_module.acquire_historical_load_lifecycle_lock
            )
            original_activation_lock = (
                load_module.acquire_historical_load_lifecycle_lock
            )

            def hold_delete_lock(session: Session) -> None:
                original_delete_lock(session)
                deletion_acquired.set()
                assert release_deletion.wait(timeout=10)

            def observe_activation_lock(session: Session) -> None:
                activation_attempted.set()
                original_activation_lock(session)

            monkeypatch.setattr(
                deletion_module,
                "acquire_historical_load_lifecycle_lock",
                hold_delete_lock,
            )
            monkeypatch.setattr(
                load_module,
                "acquire_historical_load_lifecycle_lock",
                observe_activation_lock,
            )
            deletion_thread = Thread(target=delete_worker)
            deletion_thread.start()
            assert deletion_acquired.wait(timeout=10)

            activation_result: list[UUID] = []

            def activation_worker() -> None:
                try:
                    with Session(engine) as session, session.begin():
                        activation_result.append(activate(session))
                except BaseException as error:
                    errors.append(error)

            activation_thread = Thread(target=activation_worker)
            activation_thread.start()
            assert activation_attempted.wait(timeout=10)
            assert not activation_result
            assert not deletion_done.is_set()
            release_deletion.set()
            _join(deletion_thread, errors)
            _join(activation_thread, errors)
            activated_request_id = activation_result[0]

        assert len(deletion_result) == 1
        result = deletion_result[0]
        assert result.experiment_id == experiment_id
        if winner == "activation_first":
            assert result.snapshot_deleted is False
        else:
            assert result.snapshot_deleted is True
        with Session(engine) as session:
            assert session.get(ExperimentModel, experiment_id) is None
            load = session.get(HistoricalDataLoadRequestModel, activated_request_id)
            assert load is not None
            assert load.status == (
                "RUNNING" if activation_kind == "FAILED_RESUME" else "PENDING"
            )
            assert (session.get(DatasetSnapshotModel, snapshot_id) is not None) is (
                not result.snapshot_deleted
            )
    finally:
        if activation_session is not None:
            activation_session.rollback()
            activation_session.close()
        if activated_request_id is not None:
            _finish_active_load(engine, activated_request_id)
        engine.dispose()


def test_snapshot_first_attachment_and_lifecycle_lock_do_not_deadlock(
    database_url: str, monkeypatch
) -> None:
    """Deletion holds both locks while completion waits only on the snapshot row.

    This is the opposite acquisition relationship that matters here: deletion
    locks the snapshot before taking the lifecycle lock, while completion uses
    the shared snapshot-first helper and never takes the lifecycle lock.  The
    bounded two-connection race proves the relationship completes rather than
    forming a lock cycle.
    """
    engine = _engine(database_url)
    with Session(engine) as session:
        experiment_id, snapshot_id, version_id = _seed_one(session)
        session.commit()
    request_id = _create_pending(engine, version_id)
    with Session(engine) as session, session.begin():
        assert HistoricalDataLoadRepository().claim(session, request_id) is not None

    deletion_acquired = Event()
    release_deletion = Event()
    completion_started = Event()
    completion_done = Event()
    deletion_result: list[Any] = []
    completion_result: list[bool] = []
    errors: list[BaseException] = []
    original_delete_lock = deletion_module.acquire_historical_load_lifecycle_lock

    def hold_delete_lock(session: Session) -> None:
        original_delete_lock(session)
        deletion_acquired.set()
        assert release_deletion.wait(timeout=10)

    monkeypatch.setattr(
        deletion_module,
        "acquire_historical_load_lifecycle_lock",
        hold_delete_lock,
    )

    def delete_worker() -> None:
        try:
            with Session(engine) as session, session.begin():
                deletion_result.append(
                    ExperimentDeletionRepository().delete(session, experiment_id)
                )
        except BaseException as error:
            errors.append(error)

    def complete_worker() -> None:
        completion_started.set()
        try:
            with Session(engine) as session, session.begin():
                completion_result.append(
                    HistoricalDataLoadRepository().complete(
                        session,
                        request_id,
                        snapshot_id=snapshot_id,
                        coverage_summary={"valid": True},
                        experiment_validation={"valid": True},
                    )
                )
        except BaseException as error:
            errors.append(error)
        finally:
            completion_done.set()

    deletion_thread = Thread(target=delete_worker)
    deletion_thread.start()
    assert deletion_acquired.wait(timeout=10)
    completion_thread = Thread(target=complete_worker)
    completion_thread.start()
    assert completion_started.wait(timeout=10)
    assert not completion_done.wait(timeout=0.2)
    release_deletion.set()
    _join(deletion_thread, errors)
    _join(completion_thread, errors)

    assert deletion_result[0].snapshot_deleted is False
    assert completion_result == [True]
    with Session(engine) as session:
        assert session.get(ExperimentModel, experiment_id) is None
        assert session.get(DatasetSnapshotModel, snapshot_id) is not None
        load = session.get(HistoricalDataLoadRequestModel, request_id)
        assert load is not None
        assert load.status == "COMPLETED"
        assert load.snapshot_id == snapshot_id
    engine.dispose()
