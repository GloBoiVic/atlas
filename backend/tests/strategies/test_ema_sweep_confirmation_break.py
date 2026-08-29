from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from backend.domain.market_data import Bar, Instrument, PriceComponent, Timeframe
from backend.domain.strategy import (
    Action,
    Phase,
    StrategyContext,
    StrategyParameters,
    StrategyState,
)
from backend.strategies.contract import StrategyContractError, evaluate_strategy
from backend.strategies.production import create_production_strategy_registry


def test_production_registry_exposes_only_current_reference_strategy() -> None:
    registry = create_production_strategy_registry(Path(__file__).parents[3])
    entries = tuple(registry.catalog())
    assert len(entries) == 1
    assert entries[0].definition.strategy_key == "ema_sweep_confirmation_break"
    assert entries[0].definition.name == "EMA Sweep Confirmation Break"
    assert entries[0].definition.implementation_key == "ema_sweep_confirmation_break.v2"
    assert entries[0].definition.state_schema_version == 2


def test_authoritative_strategy_rejects_legacy_state_schema() -> None:
    registry = create_production_strategy_registry(Path(__file__).parents[3])
    implementation = next(registry.catalog()).implementation
    with pytest.raises(StrategyContractError):
        evaluate_strategy(
            implementation,
            StrategyContext(
                datetime(2026, 1, 1, 10, 0, tzinfo=UTC), Instrument.EUR_USD, ()
            ),
            StrategyParameters(),
            StrategyState(schema_version=1),
        )


def _bar(index: int, open_: str, high: str, low: str, close: str) -> Bar:
    start = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=index * 15)
    return Bar(
        Instrument.EUR_USD,
        Timeframe.M15,
        PriceComponent.MID,
        start,
        start + timedelta(minutes=15),
        Decimal(open_),
        Decimal(high),
        Decimal(low),
        Decimal(close),
    )


def test_registered_strategy_evaluate_arms_at_zero_and_expires_after_w5() -> None:
    registry = create_production_strategy_registry(Path(__file__).parents[3])
    implementation = next(registry.catalog()).implementation
    history = tuple(
        _bar(index, "1.1000", "1.1010", "1.0990", "1.1000") for index in range(99)
    )
    reference = _bar(99, "1.1020", "1.1030", "1.0995", "1.1010")
    confirmation = _bar(100, "1.1000", "1.1040", "1.0980", "1.1035")

    identified = evaluate_strategy(
        implementation,
        StrategyContext(reference.end_time, Instrument.EUR_USD, history + (reference,)),
        StrategyParameters(),
        StrategyState(schema_version=2),
    )
    armed = evaluate_strategy(
        implementation,
        StrategyContext(
            confirmation.end_time,
            Instrument.EUR_USD,
            history + (reference, confirmation),
        ),
        StrategyParameters(),
        identified.next_state,
    )
    assert armed.decision.action is Action.OPEN_LONG
    assert armed.next_state.phase is Phase.ARMED
    assert armed.next_state.watch_bars == 0
    assert armed.next_state.schema_version == 2
    assert armed.decision.setup_facts is not None
    facts = armed.decision.setup_facts
    assert facts.reference.timestamp == reference.end_time
    assert facts.sweep.timestamp == confirmation.end_time
    assert facts.confirmation.timestamp == confirmation.end_time
    assert facts.sweep == facts.confirmation
    assert facts.ema_at_reference is not None
    assert facts.atr == Decimal("0.002385204081632653061224489796")
    assert facts.stop_methodology == "confirmation_low - (0.5 × ATR14)"
    assert facts.stop_price == Decimal("1.096807397959183673469387755")
    assert facts.trigger_price == confirmation.high
    assert facts.trigger_basis == "ASK"
    assert facts.window_policy == (
        "W1-W5 received completed analytical bars; no wall-clock expiry"
    )
    assert facts.evidence_version == "REFERENCE_STRATEGY_EVIDENCE_V2"
    assert facts.same_candle_sweep_confirmation is True
    assert armed.next_state.sweep_time == armed.next_state.confirmation_time
    assert armed.decision.expiry_time is None

    watch = tuple(
        _bar(index, "1.1000", "1.1010", "1.0990", "1.1000")
        for index in range(101, 106)
    )
    working = armed.next_state
    watched = None
    for expected_watch_count, bar in enumerate(watch, start=1):
        watched = evaluate_strategy(
            implementation,
            StrategyContext(
                bar.end_time,
                Instrument.EUR_USD,
                history + (reference, confirmation) + watch[:expected_watch_count],
            ),
            StrategyParameters(),
            working,
        )
        working = watched.next_state
        assert watched.next_state.watch_bars == expected_watch_count
    assert watched is not None
    w5 = watched
    assert w5.next_state.phase is Phase.ARMED
    assert w5.next_state.watch_bars == 5
    w6 = _bar(106, "1.1000", "1.1010", "1.0990", "1.1000")
    expired = evaluate_strategy(
        implementation,
        StrategyContext(
            w6.end_time,
            Instrument.EUR_USD,
            history + (reference, confirmation) + watch + (w6,),
        ),
        StrategyParameters(),
        w5.next_state,
    )
    assert expired.next_state.phase is Phase.SEARCHING
