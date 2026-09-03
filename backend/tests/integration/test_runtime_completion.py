# pyright: reportPrivateUsage=false

"""PostgreSQL completion evidence for the PAPER 06 runtime seams."""

from __future__ import annotations

import concurrent.futures
from collections.abc import Collection, Generator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from os import environ
from threading import Barrier, Event
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, inspect, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from backend.domain import (
    Action,
    FinancialPositionState,
    Rationale,
    StrategyDecision,
    StrategyEvaluation,
    StrategyStateEnvelope,
    StrategyStatePayloadDocument,
    ValidatedParameterPayload,
)
from backend.persistence.database import (
    configure_utc_session_timezone,
    create_session_factory,
)
from backend.persistence.models import (
    PaperMutationClaimModel,
    PaperRuntimeActivationModel,
    PaperRuntimeCycleModel,
    PaperRuntimeOwnershipModel,
)
from backend.persistence.paper_execution_repository import PaperExecutionRepository
from backend.persistence.runtime_repository import (
    InvalidPaperRuntimeTransition,
    PaperRuntimeActivationAlreadyPresent,
    PaperRuntimeIdentityConflict,
    PaperRuntimeOwnerLost,
    PaperRuntimeRepository,
)
from backend.runtime import (
    PaperRuntimeActivation,
    PaperRuntimeCycle,
    PaperRuntimeCycleStatus,
    PaperRuntimeLifecycleState,
    PaperRuntimeOwnership,
    PaperRuntimeOwnershipPhase,
    runtime_evaluation_key,
    runtime_parameter_fingerprint,
)
from backend.tests.integration.test_paper_execution_repository import (
    _attempt as paper_attempt,
)
from backend.tests.integration.test_paper_execution_repository import (
    _seed_strategy as seed_paper_strategy,
)

pytestmark = pytest.mark.integration

NOW = datetime(2026, 9, 3, 12, tzinfo=UTC)
VERSION_ID = UUID("11111111-1111-1111-1111-111111111111")
OWNER_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


def has_named_constraint(names: Collection[str | None], expected: str) -> bool:
    """Accept PostgreSQL's naming-convention prefix and identifier truncation."""
    return any(name is not None and expected in name for name in names)


@pytest.fixture
def runtime_database() -> Generator[Engine]:
    value = environ.get("ATLAS_TEST_DATABASE_URL")
    if not value or not value.rsplit("/", 1)[-1].endswith("_test"):
        pytest.skip("ATLAS_TEST_DATABASE_URL must name a dedicated *_test database")
    engine = configure_utc_session_timezone(create_engine(value))
    yield engine
    engine.dispose()


def activation(activation_id: UUID | None = None) -> PaperRuntimeActivation:
    parameters = ValidatedParameterPayload.from_mapping((), {})
    return PaperRuntimeActivation(
        activation_id=activation_id or uuid4(),
        strategy_version_id=VERSION_ID,
        strategy_key="paper_fixture",
        strategy_version_number=1,
        source_fingerprint="a" * 64,
        implementation_key="paper_fixture.v1",
        validated_parameter_snapshot=parameters,
        parameter_fingerprint=runtime_parameter_fingerprint(parameters),
        risk_per_trade=Decimal("0.01"),
        provider_account_id="001-011-5838423-001",
        requested_at=NOW,
    )


def cycle(value: PaperRuntimeActivation, *, sequence: int = 1) -> PaperRuntimeCycle:
    return PaperRuntimeCycle(
        cycle_id=uuid4(),
        activation_id=value.activation_id,
        cycle_sequence=sequence,
        evaluation_key=runtime_evaluation_key(
            value.strategy_version_id, value.parameter_fingerprint
        ),
        strategy_version_id=value.strategy_version_id,
        parameter_fingerprint=value.parameter_fingerprint,
        frontier_start=NOW,
        frontier_end=NOW + timedelta(minutes=15),
        financial_position_state=FinancialPositionState.FLAT,
        account_transaction_id="42",
        account_observed_at=NOW,
        account_open_trade_count=0,
        account_open_position_count=0,
        account_pending_order_count=0,
        account_gate_fingerprint="b" * 64,
        cycle_status=PaperRuntimeCycleStatus.CLAIMED,
        claimed_at=NOW,
    )


def setup_running(
    factory: sessionmaker[Session],
    runtime_repository: PaperRuntimeRepository,
    value: PaperRuntimeActivation,
    *,
    seed_strategy: bool = True,
) -> PaperRuntimeOwnership:
    owner = PaperRuntimeOwnership(
        owner_id=OWNER_ID,
        activation_id=value.activation_id,
        owner_generation=1,
        acquired_at=NOW,
        heartbeat_at=NOW,
        phase=PaperRuntimeOwnershipPhase.RUNNING,
    )
    with factory.begin() as session:
        if seed_strategy:
            seed_paper_strategy(session)
        runtime_repository.create_activation(session, value)
        runtime_repository.transition_activation(
            session, value.activation_id, PaperRuntimeLifecycleState.STARTING
        )
        runtime_repository.transition_activation(
            session, value.activation_id, PaperRuntimeLifecycleState.RUNNING
        )
        runtime_repository.record_ownership_after_lock(session, owner)
    return owner


def test_runtime_schema_exposes_constraints_and_immutable_configuration(
    runtime_database: Engine,
) -> None:
    factory = create_session_factory(runtime_database)
    repository = PaperRuntimeRepository()
    value = activation()
    setup_running(factory, repository, value)

    activation_checks = {
        item["name"]
        for item in inspect(runtime_database).get_check_constraints(
            "paper_runtime_activations"
        )
    }
    cycle_checks = {
        item["name"]
        for item in inspect(runtime_database).get_check_constraints(
            "paper_runtime_cycles"
        )
    }
    ownership_checks = {
        item["name"]
        for item in inspect(runtime_database).get_check_constraints(
            "paper_runtime_ownership"
        )
    }
    assert all(
        has_named_constraint(activation_checks, expected)
        for expected in {
            "paper_runtime_provider",
            "paper_runtime_environment",
            "paper_runtime_risk_positive_finite",
            "paper_runtime_lifecycle_state",
            "paper_runtime_parameters_o",
        }
    )
    assert all(
        has_named_constraint(cycle_checks, expected)
        for expected in {
            "paper_runtime_cycle_sequence",
            "paper_runtime_cycle_position_state",
            "paper_runtime_cycle_position_counts",
            "paper_runtime_cycle_status",
            "paper_runtime_cycle_evaluation_bounded",
        }
    )
    assert all(
        has_named_constraint(ownership_checks, expected)
        for expected in {
            "paper_runtime_ownership_slot",
            "paper_runtime_owner_generation",
            "paper_runtime_ownership_phase",
        }
    )
    assert {
        "uq_paper_runtime_cycles_evaluation_frontier",
        "uq_paper_runtime_cycles_activation_sequence",
        "uq_paper_runtime_cycles_activation_frontier",
    } <= {
        item["name"]
        for item in inspect(runtime_database).get_unique_constraints(
            "paper_runtime_cycles"
        )
    }

    with factory() as session:
        with pytest.raises(SQLAlchemyError):
            session.execute(
                update(PaperRuntimeActivationModel)
                .where(PaperRuntimeActivationModel.activation_id == value.activation_id)
                .values(strategy_key="tampered")
            )
        session.rollback()
        with pytest.raises(SQLAlchemyError):
            session.execute(
                update(PaperRuntimeOwnershipModel).values(phase="NOT_A_PHASE")
            )
            session.rollback()
            with pytest.raises(SQLAlchemyError):
                activation_row = session.get(
                    PaperRuntimeActivationModel, value.activation_id
                )
                assert activation_row is not None
                session.delete(activation_row)
                session.flush()
            session.rollback()


def test_concurrent_activation_requests_have_one_winner_and_exact_replay_conflict(
    runtime_database: Engine,
) -> None:
    factory = create_session_factory(runtime_database)
    repository = PaperRuntimeRepository()
    first = activation()
    second = activation()
    with factory.begin() as session:
        seed_paper_strategy(session)

    barrier = Barrier(2)

    def create(value: PaperRuntimeActivation) -> str:
        try:
            with factory() as session:
                barrier.wait()
                repository.create_activation(session, value)
                session.commit()
            return "created"
        except PaperRuntimeActivationAlreadyPresent:
            return "occupied"

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(create, (first, second)))
    assert sorted(results) == ["created", "occupied"]

    with factory() as session:
        durable = repository.get_active_activation(session)
        assert durable is not None
        assert durable.activation_id in {first.activation_id, second.activation_id}
        with pytest.raises(PaperRuntimeIdentityConflict):
            repository.create_activation(
                session,
                replace_activation_risk(durable.activation_id, first, Decimal("0.02")),
            )


def replace_activation_risk(
    activation_id: UUID, value: PaperRuntimeActivation, risk: Decimal
) -> PaperRuntimeActivation:
    return replace(value, activation_id=activation_id, risk_per_trade=risk)


def test_concurrent_cycle_reservation_returns_one_durable_frontier(
    runtime_database: Engine,
) -> None:
    factory = create_session_factory(runtime_database)
    repository = PaperRuntimeRepository()
    value = activation()
    owner = setup_running(factory, repository, value)
    candidate = cycle(value)
    barrier = Barrier(2)

    def reserve() -> UUID:
        with factory() as session:
            with session.begin():
                barrier.wait()
                row = repository.reserve_cycle(
                    session,
                    candidate,
                    owner_id=owner.owner_id,
                    owner_generation=owner.owner_generation,
                )
                return row.cycle_id

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(reserve) for _ in range(2)]
        results = [future.result() for future in futures]
    assert results == [candidate.cycle_id, candidate.cycle_id]
    with factory() as session:
        assert (
            session.scalar(
                select(PaperRuntimeCycleModel.cycle_id).where(
                    PaperRuntimeCycleModel.frontier_end == candidate.frontier_end
                )
            )
            == candidate.cycle_id
        )


def test_owner_generation_loss_fences_cycle_reservation(
    runtime_database: Engine,
) -> None:
    factory = create_session_factory(runtime_database)
    repository = PaperRuntimeRepository()
    value = activation()
    owner = setup_running(factory, repository, value)
    candidate = cycle(value)
    replacement = PaperRuntimeOwnership(
        owner_id=uuid4(),
        activation_id=value.activation_id,
        owner_generation=2,
        acquired_at=NOW,
        heartbeat_at=NOW,
        phase=PaperRuntimeOwnershipPhase.RUNNING,
    )
    with factory.begin() as session:
        repository.record_ownership_after_lock(session, replacement)

    with factory.begin() as session:
        with pytest.raises(PaperRuntimeOwnerLost):
            repository.reserve_cycle(
                session,
                candidate,
                owner_id=owner.owner_id,
                owner_generation=owner.owner_generation,
            )


def test_runtime_entry_boundary_commits_or_rolls_back_all_four_authorities(
    runtime_database: Engine,
) -> None:
    factory = create_session_factory(runtime_database)
    runtime_repository = PaperRuntimeRepository()
    paper_repository = PaperExecutionRepository()
    value = activation()
    owner = setup_running(factory, runtime_repository, value)
    candidate = cycle(value)
    attempt = paper_attempt()
    state_after = StrategyStateEnvelope(
        1,
        candidate.frontier_end,
        StrategyStatePayloadDocument.from_mapping("paper_fixture.v1", 1, {}),
    )
    evaluation = StrategyEvaluation(
        StrategyDecision(Action.NO_ACTION, Rationale("RUNTIME_ENTRY_FIXTURE")),
        state_after,
    )

    with pytest.raises(RuntimeError, match="atomic boundary rollback"):
        with factory.begin() as session:
            reserved = runtime_repository.reserve_cycle(
                session,
                candidate,
                owner_id=owner.owner_id,
                owner_generation=owner.owner_generation,
            )
            runtime_repository.transition_cycle(
                session,
                reserved.cycle_id,
                PaperRuntimeCycleStatus.EVALUATING,
                owner_id=owner.owner_id,
                owner_generation=owner.owner_generation,
            )
            paper_repository.persist_entry_claim(
                session,
                attempt,
                provider_endpoint_key="OANDA_ENTRY_POST",
                normalized_request_fingerprint="c" * 64,
            )
            runtime_repository.persist_cycle_evaluation(
                session,
                reserved.cycle_id,
                state_after=state_after,
                strategy_evaluation_snapshot=evaluation,
                decision_snapshot=evaluation.decision,
                cycle_status=PaperRuntimeCycleStatus.ENTRY_CLAIMED,
                owner_id=owner.owner_id,
                owner_generation=owner.owner_generation,
                attempt_id=attempt.attempt_id,
            )
            raise RuntimeError("atomic boundary rollback")

    with factory() as session:
        assert (
            runtime_repository.get_activation(session, value.activation_id) is not None
        )
        assert runtime_repository.get_cycle(session, candidate.cycle_id) is None
        assert paper_repository.get_attempt(session, attempt.attempt_id) is None
        assert (
            session.scalar(
                select(PaperMutationClaimModel.claim_id).where(
                    PaperMutationClaimModel.attempt_id == attempt.attempt_id
                )
            )
            is None
        )

    with factory.begin() as session:
        reserved = runtime_repository.reserve_cycle(
            session,
            candidate,
            owner_id=owner.owner_id,
            owner_generation=owner.owner_generation,
        )
        runtime_repository.transition_cycle(
            session,
            reserved.cycle_id,
            PaperRuntimeCycleStatus.EVALUATING,
            owner_id=owner.owner_id,
            owner_generation=owner.owner_generation,
        )
        paper_repository.persist_entry_claim(
            session,
            attempt,
            provider_endpoint_key="OANDA_ENTRY_POST",
            normalized_request_fingerprint="c" * 64,
        )
        persisted = runtime_repository.persist_cycle_evaluation(
            session,
            reserved.cycle_id,
            state_after=state_after,
            strategy_evaluation_snapshot=evaluation,
            decision_snapshot=evaluation.decision,
            cycle_status=PaperRuntimeCycleStatus.ENTRY_CLAIMED,
            owner_id=owner.owner_id,
            owner_generation=owner.owner_generation,
            attempt_id=attempt.attempt_id,
        )
        assert persisted.attempt_id == attempt.attempt_id

    with factory() as session:
        activation_row = runtime_repository.get_activation(session, value.activation_id)
        cycle_row = runtime_repository.get_cycle(session, candidate.cycle_id)
        assert activation_row is not None
        assert activation_row.last_cycle_id == candidate.cycle_id
        assert cycle_row is not None
        assert cycle_row.cycle_status == PaperRuntimeCycleStatus.ENTRY_CLAIMED.value
        assert paper_repository.get_attempt(session, attempt.attempt_id) is not None


def test_stop_before_claim_and_after_claim_have_deterministic_row_lock_order(
    runtime_database: Engine,
) -> None:
    factory = create_session_factory(runtime_database)
    repository = PaperRuntimeRepository()
    value = activation()
    owner = setup_running(factory, repository, value)

    stop_locked = Event()
    entry_attempted = Event()
    stop_result: list[str] = []
    entry_result: list[str] = []

    def stop_wins() -> None:
        with factory() as session:
            with session.begin():
                repository.get_activation(session, value.activation_id, for_update=True)
                stop_locked.set()
                assert entry_attempted.wait(5)
                row = repository.transition_activation(
                    session,
                    value.activation_id,
                    PaperRuntimeLifecycleState.STOP_REQUESTED,
                    reason_code="OPERATOR_STOP",
                )
                stop_result.append(row.lifecycle_state)

    def entry_loses() -> None:
        assert stop_locked.wait(5)
        entry_attempted.set()
        with factory() as session:
            try:
                with session.begin():
                    repository.assert_entry_authority(
                        session,
                        value.activation_id,
                        owner_id=owner.owner_id,
                        owner_generation=owner.owner_generation,
                    )
            except InvalidPaperRuntimeTransition:
                entry_result.append("fenced")

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(stop_wins), executor.submit(entry_loses)]
        for future in futures:
            future.result()
    assert stop_result == [PaperRuntimeLifecycleState.STOP_REQUESTED.value]
    assert entry_result == ["fenced"]

    with factory() as session:
        activation_row = repository.get_activation(session, value.activation_id)
        assert activation_row is not None
        assert (
            activation_row.lifecycle_state
            == PaperRuntimeLifecycleState.STOP_REQUESTED.value
        )


def test_entry_claim_commit_wins_before_stop_and_remains_durable(
    runtime_database: Engine,
) -> None:
    factory = create_session_factory(runtime_database)
    runtime_repository = PaperRuntimeRepository()
    paper_repository = PaperExecutionRepository()
    value = activation()
    owner = setup_running(factory, runtime_repository, value)
    attempt = paper_attempt()
    entry_locked = Event()
    stop_started = Event()
    stop_result: list[str] = []

    def entry_wins() -> None:
        with factory() as session:
            with session.begin():
                runtime_repository.assert_entry_authority(
                    session,
                    value.activation_id,
                    owner_id=owner.owner_id,
                    owner_generation=owner.owner_generation,
                )
                paper_repository.persist_entry_claim(
                    session,
                    attempt,
                    provider_endpoint_key="OANDA_ENTRY_POST",
                    normalized_request_fingerprint="d" * 64,
                )
                entry_locked.set()
                assert stop_started.wait(5)

    def stop_after_claim() -> None:
        assert entry_locked.wait(5)
        stop_started.set()
        with factory.begin() as session:
            row = runtime_repository.request_stop(
                session,
                value.activation_id,
                reason_code="OPERATOR_STOP",
            )
            stop_result.append(row.lifecycle_state)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(entry_wins), executor.submit(stop_after_claim)]
        for future in futures:
            future.result()
    assert stop_result == [PaperRuntimeLifecycleState.STOP_REQUESTED.value]

    with factory() as session:
        assert (
            session.scalar(
                select(PaperMutationClaimModel.claim_id).where(
                    PaperMutationClaimModel.attempt_id == attempt.attempt_id
                )
            )
            is not None
        )
        activation_row = runtime_repository.get_activation(session, value.activation_id)
        assert activation_row is not None
        assert (
            activation_row.lifecycle_state
            == PaperRuntimeLifecycleState.STOP_REQUESTED.value
        )
