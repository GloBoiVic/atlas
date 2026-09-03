from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from backend.domain import (
    Action,
    Direction,
    FinancialPositionState,
    Rationale,
    StopProposal,
    StrategyDecision,
    StrategyEvaluation,
    StrategyStateEnvelope,
    StrategyStatePayloadDocument,
    StrategyVersion,
    TargetProposal,
    ValidatedParameterPayload,
)
from backend.paper.current_analytical_frontier import CurrentAnalyticalFrontier
from backend.paper.persistence_contracts import PaperStrategyEvaluationReceipt
from backend.runtime import (
    PaperRuntimeAccountObservation,
    PaperRuntimeActivation,
    PaperRuntimeCycle,
    PaperRuntimeCycleAuthority,
    PaperRuntimeFrontierAlreadyConsumed,
    PaperRuntimeFrontierDuplicate,
    PaperRuntimeFrontierGap,
    PaperRuntimeLifecycleState,
    PaperRuntimeStateAuthorityError,
    PaperRuntimeUnsupportedStrategyAction,
    runtime_parameter_fingerprint,
)

NOW = datetime(2026, 9, 2, 12, 15, tzinfo=UTC)
ACTIVATION_ID = UUID("11111111-1111-1111-1111-111111111111")
VERSION_ID = UUID("22222222-2222-2222-2222-222222222222")


def activation(
    *,
    state: object | None = None,
    last_frontier: datetime | None = None,
    last_cycle_id: UUID | None = None,
) -> PaperRuntimeActivation:
    parameters = ValidatedParameterPayload.from_mapping((), {})
    return PaperRuntimeActivation(
        activation_id=ACTIVATION_ID,
        strategy_version_id=VERSION_ID,
        strategy_key="fixture",
        strategy_version_number=1,
        source_fingerprint="a" * 64,
        implementation_key="fixture.v1",
        validated_parameter_snapshot=parameters,
        parameter_fingerprint=runtime_parameter_fingerprint(parameters),
        risk_per_trade=Decimal("0.01"),
        provider_account_id="001-002-003-004",
        requested_at=NOW,
        lifecycle_state=PaperRuntimeLifecycleState.RUNNING,
        strategy_state=state,  # type: ignore[arg-type]
        last_frontier_end=last_frontier,
        last_cycle_id=last_cycle_id,
    )


def frontier(previous: datetime | None = None) -> CurrentAnalyticalFrontier:
    from backend.domain import Bar, Instrument, PriceComponent, Timeframe

    start = NOW - timedelta(minutes=15)
    prior_start = start - timedelta(minutes=15)
    bars = (
        Bar(
            Instrument.EUR_USD,
            Timeframe.M15,
            PriceComponent.MID,
            prior_start,
            start,
            Decimal("1.1"),
            Decimal("1.11"),
            Decimal("1.09"),
            Decimal("1.1"),
        ),
        Bar(
            Instrument.EUR_USD,
            Timeframe.M15,
            PriceComponent.MID,
            start,
            NOW,
            Decimal("1.1"),
            Decimal("1.11"),
            Decimal("1.09"),
            Decimal("1.1"),
        ),
    )
    return CurrentAnalyticalFrontier(
        acquisition_cutoff=NOW,
        requested_start=prior_start,
        requested_end=NOW,
        bars=bars,
        current_bar=bars[-1],
        eligible_windows=((prior_start, start), (start, NOW)),
        previous_frontier=previous if previous is not None else start,
    )


def observation(
    state: FinancialPositionState = FinancialPositionState.FLAT,
    *,
    attributable: bool = True,
) -> PaperRuntimeAccountObservation:
    exposed = state is not FinancialPositionState.FLAT
    return PaperRuntimeAccountObservation(
        provider_account_id="001-002-003-004",
        account_transaction_id="42",
        observed_at=NOW,
        financial_position_state=state,
        open_trade_count=1 if exposed else 0,
        open_position_count=1 if exposed else 0,
        pending_order_count=0,
        attributable=attributable,
    )


class _ReservationRepository:
    def get_cycle_by_evaluation_frontier(
        self, _session: object, _evaluation_key: str, _frontier_end: datetime
    ) -> None:
        return None

    def next_cycle_sequence(self, _session: object, _activation_id: UUID) -> int:
        return 1

    def reserve_cycle(
        self, _session: object, cycle: PaperRuntimeCycle, **_kwargs: object
    ) -> PaperRuntimeCycle:
        return cycle


class _ConsumedRepository:
    def get_cycle_by_evaluation_frontier(
        self, _session: object, _evaluation_key: str, _frontier_end: datetime
    ) -> object:
        return SimpleNamespace(activation_id=uuid4())


def test_account_observation_binds_flat_and_directional_state() -> None:
    assert observation().to_json()["financial_position_state"] == "FLAT"
    assert (
        observation(FinancialPositionState.LONG).to_json()["financial_position_state"]
        == "LONG"
    )
    assert (
        observation(FinancialPositionState.SHORT).to_json()["financial_position_state"]
        == "SHORT"
    )
    assert len(observation().fingerprint) == 64


def test_unattributed_exposure_is_not_a_strategy_input() -> None:
    with pytest.raises(PaperRuntimeStateAuthorityError, match="unattributed"):
        PaperRuntimeAccountObservation(
            provider_account_id="001-002-003-004",
            account_transaction_id="42",
            observed_at=NOW,
            financial_position_state=FinancialPositionState.LONG,
            open_trade_count=1,
            open_position_count=1,
            pending_order_count=0,
            attributable=False,
        )


def test_frontier_progress_allows_exact_next_bar_and_rejects_duplicate_or_gap() -> None:
    authority = PaperRuntimeCycleAuthority()
    current = frontier()
    authority.validate_frontier_progress(None, current)

    previous_state = StrategyStateEnvelope(
        1,
        current.previous_frontier,
        StrategyStatePayloadDocument.from_mapping("fixture.v1", 1, {}),
    )
    authority.validate_frontier_progress(previous_state, current)

    with pytest.raises(PaperRuntimeFrontierDuplicate):
        duplicate_state = StrategyStateEnvelope(
            1,
            current.current_frontier,
            StrategyStatePayloadDocument.from_mapping("fixture.v1", 1, {}),
        )
        authority.validate_frontier_progress(
            duplicate_state,
            current,
        )

    with pytest.raises(PaperRuntimeFrontierGap):
        stale_state = StrategyStateEnvelope(
            1,
            current.requested_start,
            StrategyStatePayloadDocument.from_mapping("fixture.v1", 1, {}),
        )
        authority.validate_frontier_progress(
            stale_state,
            current,
        )


def test_cycle_reservation_binds_activation_state_and_account_evidence() -> None:
    current = frontier()
    value = activation()
    authority = PaperRuntimeCycleAuthority(
        _ReservationRepository()  # type: ignore[arg-type]
    )

    cycle = authority.build_cycle(
        value,
        current,
        observation(FinancialPositionState.LONG),
        session=object(),  # type: ignore[arg-type]
    )

    assert cycle.cycle_sequence == 1
    assert cycle.state_before is None
    assert cycle.frontier_end == current.current_frontier
    assert cycle.account_transaction_id == "42"
    assert cycle.financial_position_state is FinancialPositionState.LONG


def test_same_activation_resume_binds_the_exact_prior_state_and_frontier() -> None:
    current = frontier()
    prior_state = StrategyStateEnvelope(
        1,
        current.previous_frontier,
        StrategyStatePayloadDocument.from_mapping("fixture.v1", 1, {}),
    )
    value = activation(
        state=prior_state,
        last_frontier=current.previous_frontier,
        last_cycle_id=uuid4(),
    )

    cycle = PaperRuntimeCycleAuthority().build_cycle(
        value,
        current,
        observation(),
    )

    assert cycle.state_before == prior_state
    assert cycle.prior_frontier_end == prior_state.last_evaluated_bar_end


def test_nonflat_strategy_capital_action_is_blocked_without_execution_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current = frontier()
    value = activation()
    state_after = StrategyStateEnvelope(
        1,
        current.current_frontier,
        StrategyStatePayloadDocument.from_mapping("fixture.v1", 1, {}),
    )
    version = StrategyVersion(
        VERSION_ID,
        "fixture",
        1,
        "a" * 64,
        "fixture.v1",
        (),
    )
    receipt = PaperStrategyEvaluationReceipt.from_verified(
        version,
        ValidatedParameterPayload.from_mapping((), {}),
        StrategyEvaluation(
            StrategyDecision(
                Action.OPEN_LONG,
                Rationale("FIXTURE_OPEN"),
                direction=Direction.LONG,
                decision_time=NOW,
                stop=StopProposal(Decimal("1.09"), Direction.LONG),
                target=TargetProposal(),
            ),
            state_after,
        ),
    )

    def fake_evaluator(
        *_args: object, **_kwargs: object
    ) -> PaperStrategyEvaluationReceipt:
        return receipt

    monkeypatch.setattr(
        "backend.runtime.cycles.evaluate_paper_strategy_frontier_receipt",
        fake_evaluator,
    )

    with pytest.raises(PaperRuntimeUnsupportedStrategyAction):
        PaperRuntimeCycleAuthority().evaluate_cycle(
            object(),  # type: ignore[arg-type]
            value,
            current,
            observation(FinancialPositionState.LONG),
            strategy_repository=object(),  # type: ignore[arg-type]
            strategy_registry=object(),  # type: ignore[arg-type]
            analytical_source=object(),  # type: ignore[arg-type]
            market_specification=object(),  # type: ignore[arg-type]
            now=NOW,
        )


def test_new_session_does_not_import_prior_state_and_global_frontier_replay_waits() -> (
    None
):
    current = frontier()
    value = activation()
    authority = PaperRuntimeCycleAuthority(
        _ConsumedRepository()  # type: ignore[arg-type]
    )

    with pytest.raises(PaperRuntimeFrontierAlreadyConsumed):
        authority.build_cycle(
            value,
            current,
            observation(),
            session=object(),  # type: ignore[arg-type]
        )

    assert value.strategy_state is None
