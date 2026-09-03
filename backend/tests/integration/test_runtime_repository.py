"""PostgreSQL evidence for the PAPER 06 runtime persistence boundary."""

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from os import environ
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

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
from backend.persistence.models import StrategyModel, StrategyVersionModel
from backend.persistence.runtime_repository import (
    PaperRuntimeActivationAlreadyPresent,
    PaperRuntimeCycleConflict,
    PaperRuntimeIdentityConflict,
    PaperRuntimeOwnerLost,
    PaperRuntimeRepository,
)
from backend.risk import RiskConfig
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
from backend.runtime.activation import (
    _activation_from_row,  # pyright: ignore[reportPrivateUsage]
)

pytestmark = pytest.mark.integration

NOW = datetime(2026, 9, 2, 12, tzinfo=UTC)
VERSION_ID = UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture
def runtime_database() -> Generator[Engine]:
    value = environ.get("ATLAS_TEST_DATABASE_URL")
    if not value or not value.rsplit("/", 1)[-1].endswith("_test"):
        pytest.skip("ATLAS_TEST_DATABASE_URL must name a dedicated *_test database")
    engine = configure_utc_session_timezone(create_engine(value))
    yield engine
    engine.dispose()


def seed_strategy(session: Session) -> None:
    strategy = StrategyModel(
        id=uuid4(),
        strategy_key="runtime_fixture",
        name="Runtime fixture",
        description="PAPER runtime persistence fixture",
    )
    session.add(strategy)
    session.add(
        StrategyVersionModel(
            id=VERSION_ID,
            strategy_id=strategy.id,
            version_number=1,
            source_fingerprint="a" * 64,
            implementation_key="runtime_fixture.v1",
            parameter_schema=[],
            context_timeframes=[],
            capabilities=[],
            source_manifest=[],
            exact_source_snapshot={},
            primary_timeframe="15m",
            required_historical_context_bars=0,
            state_schema_version=1,
            strategy=strategy,
        )
    )
    session.flush()


def activation(
    activation_id: UUID | None = None,
    *,
    risk_per_trade: Decimal = Decimal("0.01"),
) -> PaperRuntimeActivation:
    parameters = ValidatedParameterPayload.from_mapping((), {})
    return PaperRuntimeActivation(
        activation_id=activation_id or uuid4(),
        strategy_version_id=VERSION_ID,
        strategy_key="runtime_fixture",
        strategy_version_number=1,
        source_fingerprint="a" * 64,
        implementation_key="runtime_fixture.v1",
        validated_parameter_snapshot=parameters,
        parameter_fingerprint=runtime_parameter_fingerprint(parameters),
        risk_per_trade=risk_per_trade,
        provider_account_id="001-002-003-004",
        requested_at=NOW,
    )


def cycle(value: PaperRuntimeActivation) -> PaperRuntimeCycle:
    return PaperRuntimeCycle(
        cycle_id=uuid4(),
        activation_id=value.activation_id,
        cycle_sequence=1,
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


def test_activation_replay_conflict_and_single_slot(runtime_database: Engine) -> None:
    factory = create_session_factory(runtime_database)
    repository = PaperRuntimeRepository()
    first = activation()
    with factory() as session:
        seed_strategy(session)
        created = repository.create_activation(session, first)
        session.commit()
        assert created.activation_id == first.activation_id

    with factory() as session:
        replay = repository.create_activation(session, first)
        assert replay.activation_id == first.activation_id
        with pytest.raises(PaperRuntimeIdentityConflict):
            repository.create_activation(
                session,
                PaperRuntimeActivation(
                    activation_id=first.activation_id,
                    strategy_version_id=first.strategy_version_id,
                    strategy_key=first.strategy_key,
                    strategy_version_number=first.strategy_version_number,
                    source_fingerprint=first.source_fingerprint,
                    implementation_key=first.implementation_key,
                    validated_parameter_snapshot=first.validated_parameter_snapshot,
                    parameter_fingerprint=first.parameter_fingerprint,
                    risk_per_trade=Decimal("0.02"),
                    provider_account_id=first.provider_account_id,
                    requested_at=NOW,
                ),
            )
        with pytest.raises(PaperRuntimeActivationAlreadyPresent):
            repository.create_activation(session, activation())


@pytest.mark.parametrize(
    "risk_per_trade",
    (Decimal("0.01"), Decimal("0.12345678901"), Decimal("0.00000000001")),
)
def test_activation_risk_round_trip_and_exact_identity_replay(
    runtime_database: Engine, risk_per_trade: Decimal
) -> None:
    factory = create_session_factory(runtime_database)
    repository = PaperRuntimeRepository()
    value = activation(risk_per_trade=risk_per_trade)

    with factory() as session:
        seed_strategy(session)
        repository.create_activation(session, value)
        session.commit()

    with factory() as session:
        row = repository.get_activation(session, value.activation_id)
        assert row is not None
        assert type(row.risk_per_trade) is Decimal
        assert row.risk_per_trade == risk_per_trade

        loaded = _activation_from_row(session, row)  # pyright: ignore[reportPrivateUsage]
        risk_config = RiskConfig(loaded.risk_per_trade)
        assert loaded.risk_per_trade == risk_per_trade
        assert risk_config.risk_per_trade == risk_per_trade

        replay = repository.create_activation(session, value)
        assert replay.activation_id == value.activation_id

        changed_risk = risk_per_trade + Decimal("0.00000000001")
        with pytest.raises(PaperRuntimeIdentityConflict):
            repository.create_activation(
                session,
                activation(
                    value.activation_id,
                    risk_per_trade=changed_risk,
                ),
            )


def test_cycle_replay_and_owner_generation_guard(runtime_database: Engine) -> None:
    factory = create_session_factory(runtime_database)
    repository = PaperRuntimeRepository()
    value = activation()
    owner = PaperRuntimeOwnership(
        owner_id=uuid4(),
        activation_id=value.activation_id,
        owner_generation=1,
        acquired_at=NOW,
        heartbeat_at=NOW,
        phase=PaperRuntimeOwnershipPhase.RUNNING,
    )
    with factory() as session:
        seed_strategy(session)
        repository.create_activation(session, value)
        repository.transition_activation(
            session, value.activation_id, PaperRuntimeLifecycleState.STARTING
        )
        repository.transition_activation(
            session, value.activation_id, PaperRuntimeLifecycleState.RUNNING
        )
        repository.record_ownership_after_lock(session, owner)
        session.commit()

    candidate = cycle(value)
    with factory() as session:
        reserved = repository.reserve_cycle(
            session,
            candidate,
            owner_id=owner.owner_id,
            owner_generation=owner.owner_generation,
        )
        session.commit()
        assert reserved.cycle_id == candidate.cycle_id

    with factory() as session:
        replay = repository.reserve_cycle(
            session,
            candidate,
            owner_id=owner.owner_id,
            owner_generation=owner.owner_generation,
        )
        assert replay.cycle_id == candidate.cycle_id
        with pytest.raises(PaperRuntimeCycleConflict):
            repository.reserve_cycle(
                session,
                PaperRuntimeCycle(
                    cycle_id=uuid4(),
                    activation_id=value.activation_id,
                    cycle_sequence=2,
                    evaluation_key=candidate.evaluation_key,
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
                ),
                owner_id=owner.owner_id,
                owner_generation=owner.owner_generation,
            )
        with pytest.raises(PaperRuntimeOwnerLost):
            repository.heartbeat_ownership(
                session,
                owner_id=owner.owner_id,
                owner_generation=2,
            )

    with factory() as session:
        repository.transition_cycle(
            session,
            candidate.cycle_id,
            PaperRuntimeCycleStatus.EVALUATING,
            owner_id=owner.owner_id,
            owner_generation=owner.owner_generation,
        )
        state = StrategyStateEnvelope(
            state_schema_version=1,
            last_evaluated_bar_end=candidate.frontier_end,
            payload=StrategyStatePayloadDocument.from_mapping("fixture", 1, {}),
        )
        decision = StrategyDecision(Action.NO_ACTION, Rationale("NO_ENTRY"))
        persisted = repository.persist_cycle_evaluation(
            session,
            candidate.cycle_id,
            state_after=state,
            strategy_evaluation_snapshot=StrategyEvaluation(decision, state),
            decision_snapshot=decision,
            cycle_status=PaperRuntimeCycleStatus.NO_ACTION,
            owner_id=owner.owner_id,
            owner_generation=owner.owner_generation,
        )
        session.commit()
        assert persisted.state_after_fingerprint is not None
