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
    TargetProposal,
)
from backend.strategies.contract import StrategyContractError, evaluate_strategy
from backend.strategies.production import create_production_strategy_registry

ROOT = Path(__file__).parents[3]


def test_production_registry_has_only_registered_v2_strategy() -> None:
    registry = create_production_strategy_registry(ROOT)

    entries = tuple(registry.catalog())
    assert len(entries) == 1
    assert entries[0].definition.implementation_key == (
        "ema_sweep_confirmation_break.v2"
    )
    assert entries[0].implementation.__class__.__module__ == (
        "backend.strategies.ema_sweep_confirmation_break"
    )
    production_source = (ROOT / "backend/strategies/production.py").read_text()
    assert "ema_sweep_engulfing" not in production_source


def test_v2_contract_rejects_legacy_schema_one_phase_state() -> None:
    implementation = next(
        create_production_strategy_registry(ROOT).catalog()
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


def test_v2_runner_initializes_state_from_persisted_version_schema() -> None:
    source = (ROOT / "backend/experiments/runner.py").read_text()

    assert "StrategyState(schema_version=version.state_schema_version)" in source
    assert "StrategyState(schema_version=1)" not in source


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
