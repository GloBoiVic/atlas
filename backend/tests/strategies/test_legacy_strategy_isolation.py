from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from backend.domain.market_data import Instrument
from backend.domain.strategy import (
    Action,
    Direction,
    EntryPolicy,
    Phase,
    Rationale,
    StopProposal,
    StrategyContext,
    StrategyDecision,
    StrategyParameters,
    StrategyState,
    StrategyStateEnvelope,
    TargetProposal,
)
from backend.strategies.contract import StrategyContractError, evaluate_strategy
from backend.strategies.production import (
    EmaSweepConfirmationBreakCompatibilityAdaptor,
    create_production_strategy_registry,
)

ROOT = Path(__file__).parents[3]


def test_production_registry_has_registered_v2_strategies() -> None:
    registry = create_production_strategy_registry(ROOT)

    entry = registry.get(
        "ema_sweep_confirmation_break",
        implementation_key="ema_sweep_confirmation_break.v2",
    )
    assert entry.definition.implementation_key == (
        "ema_sweep_confirmation_break.v2"
    )
    assert isinstance(
        entry.implementation, EmaSweepConfirmationBreakCompatibilityAdaptor
    )
    assert registry.get(
        "candle_confirmation_break",
        implementation_key="candle_confirmation_break.v1",
    )
    production_source = (ROOT / "backend/strategies/production.py").read_text()
    assert "ema_sweep_engulfing" not in production_source


def test_v2_contract_rejects_legacy_schema_one_phase_state() -> None:
    implementation = create_production_strategy_registry(ROOT).get(
        "ema_sweep_confirmation_break",
        implementation_key="ema_sweep_confirmation_break.v2",
    ).implementation
    reference_time = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
    legacy_state = StrategyState(
        schema_version=1,
        phase=Phase.AWAITING_CONFIRMATION,
        direction=Direction.LONG,
        reference_high=Decimal("1.11"),
        reference_low=Decimal("1.08"),
        reference_time=reference_time,
        sweep_time=reference_time + timedelta(minutes=15),
        window_bars=1,
    )

    with pytest.raises(StrategyContractError):
        evaluate_strategy(
            implementation,
            StrategyContext(reference_time, Instrument.EUR_USD, ()),
            StrategyParameters(),
            legacy_state,
        )


def test_v2_contract_rejects_legacy_schema_two_state_at_public_boundary() -> None:
    implementation = create_production_strategy_registry(ROOT).get(
        "ema_sweep_confirmation_break",
        implementation_key="ema_sweep_confirmation_break.v2",
    ).implementation

    with pytest.raises(StrategyContractError):
        evaluate_strategy(
            implementation,
            StrategyContext(
                datetime(2026, 1, 1, 10, 0, tzinfo=UTC), Instrument.EUR_USD, ()
            ),
            StrategyParameters(),
            StrategyState(schema_version=2),
        )


def test_ema_adaptor_exposes_envelope_and_normalized_pending_handoff() -> None:
    adaptor = EmaSweepConfirmationBreakCompatibilityAdaptor()
    state = adaptor.initial_state()

    assert isinstance(state, StrategyStateEnvelope)
    assert state.pending_entry is None
    assert state.payload.codec_key == "ema_sweep_confirmation_break.v2"


def test_v2_runner_initializes_state_from_persisted_version_schema() -> None:
    source = (ROOT / "backend/experiments/runner.py").read_text()

    assert "initial_strategy_state(implementation)" in source
    assert "StrategyState(" not in source


def test_immediate_policy_remains_a_valid_contract_value() -> None:
    decision = StrategyDecision(
        action=Action.OPEN_LONG,
        rationale=Rationale("TEST"),
        direction=Direction.LONG,
        decision_time=datetime(2026, 1, 1, 10, 15, tzinfo=UTC),
        stop=StopProposal(Decimal("1.09"), Direction.LONG),
        target=TargetProposal(),
        entry_policy=EntryPolicy.IMMEDIATE,
    )

    assert decision.entry_policy is EntryPolicy.IMMEDIATE
    assert decision.expiry_time is None
    assert decision.expiry_bars is None
