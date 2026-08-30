from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from backend.domain.market_data import Bar, Instrument, PriceComponent, Timeframe
from backend.domain.strategy import (
    Action,
    MarketSpecification,
    Phase,
    StrategyContext,
    StrategyParameters,
    StrategyState,
    StrategyStateEnvelope,
)
from backend.strategies.contract import (
    Strategy,
    StrategyContractError,
    evaluate_strategy,
    initial_strategy_state,
)
from backend.strategies.production import create_production_strategy_registry

MARKET = MarketSpecification(Instrument.EUR_USD, Decimal("0.0001"))


def test_production_registry_exposes_current_reference_strategy() -> None:
    registry = create_production_strategy_registry(Path(__file__).parents[3])
    entry = registry.get(
        "ema_sweep_confirmation_break",
        implementation_key="ema_sweep_confirmation_break.v2",
    )
    assert entry.definition.strategy_key == "ema_sweep_confirmation_break"
    assert entry.definition.name == "EMA Sweep Confirmation Break"
    assert entry.definition.implementation_key == "ema_sweep_confirmation_break.v2"
    assert entry.definition.state_schema_version == 2


def test_authoritative_strategy_rejects_legacy_state_schema() -> None:
    registry = create_production_strategy_registry(Path(__file__).parents[3])
    implementation = registry.get(
        "ema_sweep_confirmation_break",
        implementation_key="ema_sweep_confirmation_break.v2",
    ).implementation
    with pytest.raises(StrategyContractError):
        evaluate_strategy(
            implementation,
            StrategyContext(
                datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
                Instrument.EUR_USD,
                (),
                market=MARKET,
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
    implementation = registry.get(
        "ema_sweep_confirmation_break",
        implementation_key="ema_sweep_confirmation_break.v2",
    ).implementation
    history = tuple(
        _bar(index, "1.1000", "1.1010", "1.0990", "1.1000") for index in range(99)
    )
    reference = _bar(99, "1.1020", "1.1030", "1.0995", "1.1010")
    confirmation = _bar(100, "1.1000", "1.1040", "1.0980", "1.1035")
    initial = initial_strategy_state(implementation)
    assert isinstance(initial, StrategyStateEnvelope)

    identified = evaluate_strategy(
        implementation,
        StrategyContext(
            reference.end_time,
            Instrument.EUR_USD,
            history + (reference,),
            market=MARKET,
        ),
        StrategyParameters(),
        initial,
    )
    armed = evaluate_strategy(
        implementation,
        StrategyContext(
            confirmation.end_time,
            Instrument.EUR_USD,
            history + (reference, confirmation),
            market=MARKET,
        ),
        StrategyParameters(),
        identified.next_state,
    )
    assert armed.decision.action is Action.OPEN_LONG
    assert armed.next_state.payload.get("phase") == Phase.ARMED.value
    assert armed.next_state.payload.get("watch_bars") == 0
    assert armed.next_state.state_schema_version == 2
    assert armed.next_state.pending_entry is not None
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
    assert armed.next_state.payload.get("sweep_time") == confirmation.end_time
    assert armed.next_state.payload.get("confirmation_time") == confirmation.end_time
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
                market=MARKET,
            ),
            StrategyParameters(),
            working,
        )
        working = watched.next_state
        assert working.pending_entry is not None
        working = replace(
            working,
            pending_entry=replace(
                working.pending_entry, consumed_count=expected_watch_count
            ),
        )
        assert watched.next_state.payload.get("watch_bars") == expected_watch_count
    assert watched is not None
    w5 = working
    assert w5.payload.get("phase") == Phase.ARMED.value
    assert w5.payload.get("watch_bars") == 5
    assert w5.pending_entry is not None
    w6 = _bar(106, "1.1000", "1.1010", "1.0990", "1.1000")
    expired = evaluate_strategy(
        implementation,
        StrategyContext(
            w6.end_time,
            Instrument.EUR_USD,
            history + (reference, confirmation) + watch + (w6,),
            market=MARKET,
        ),
        StrategyParameters(),
            w5,
    )
    assert expired.next_state.payload.get("phase") == Phase.SEARCHING.value
    assert expired.next_state.pending_entry is None


def _armed_ema_state() -> tuple[
    Strategy, tuple[Bar, ...], Bar, Bar, StrategyStateEnvelope
]:
    registry = create_production_strategy_registry(Path(__file__).parents[3])
    implementation = registry.get(
        "ema_sweep_confirmation_break",
        implementation_key="ema_sweep_confirmation_break.v2",
    ).implementation
    history = tuple(
        _bar(index, "1.1000", "1.1010", "1.0990", "1.1000") for index in range(99)
    )
    reference = _bar(99, "1.1020", "1.1030", "1.0995", "1.1010")
    confirmation = _bar(100, "1.1000", "1.1040", "1.0980", "1.1035")
    identified = evaluate_strategy(
        implementation,
        StrategyContext(
            reference.end_time,
            Instrument.EUR_USD,
            history + (reference,),
            market=MARKET,
        ),
        StrategyParameters(),
        initial_strategy_state(implementation),
    )
    armed = evaluate_strategy(
        implementation,
        StrategyContext(
            confirmation.end_time,
            Instrument.EUR_USD,
            history + (reference, confirmation),
            market=MARKET,
        ),
        StrategyParameters(),
        identified.next_state,
    )
    assert isinstance(armed.next_state, StrategyStateEnvelope)
    return implementation, history, reference, confirmation, armed.next_state


@pytest.mark.parametrize(
    "timestamp_field", ["reference_time", "sweep_time", "confirmation_time"]
)
def test_active_ema_timestamp_json_round_trip_continues(
    timestamp_field: str,
) -> None:
    implementation, history, reference, confirmation, armed = _armed_ema_state()
    payload_fields = armed.to_json()["payload"]["fields"]
    assert isinstance(payload_fields[timestamp_field], str)
    assert all(
        isinstance(payload_fields[field], str)
        for field in ("reference_time", "sweep_time", "confirmation_time")
    )

    restored = StrategyStateEnvelope.from_json(armed.to_json())
    next_bar = _bar(101, "1.1000", "1.1010", "1.0990", "1.1000")
    continued = evaluate_strategy(
        implementation,
        StrategyContext(
            next_bar.end_time,
            Instrument.EUR_USD,
            history + (reference, confirmation, next_bar),
            market=MARKET,
        ),
        StrategyParameters(),
        restored,
    )

    assert continued.decision.action is Action.NO_ACTION
    assert continued.next_state.payload.get("phase") == Phase.ARMED.value
    assert continued.next_state.payload.get("watch_bars") == 1
    for field in ("reference_time", "sweep_time", "confirmation_time"):
        restored_timestamp = continued.next_state.payload.get(field)
        assert type(restored_timestamp) is datetime
        assert restored_timestamp == armed.payload.get(field)


def test_round_tripped_ema_pending_state_continues_w1_through_w6() -> None:
    implementation, history, reference, confirmation, armed = _armed_ema_state()
    working = StrategyStateEnvelope.from_json(armed.to_json())
    watch = tuple(
        _bar(index, "1.1000", "1.1010", "1.0990", "1.1000")
        for index in range(101, 107)
    )

    for expected_watch_count, current in enumerate(watch[:5], start=1):
        continued = evaluate_strategy(
            implementation,
            StrategyContext(
                current.end_time,
                Instrument.EUR_USD,
                history + (reference, confirmation) + watch[:expected_watch_count],
                market=MARKET,
            ),
            StrategyParameters(),
            working,
        )
        assert continued.next_state.payload.get("watch_bars") == expected_watch_count
        assert continued.next_state.pending_entry is not None
        working = replace(
            continued.next_state,
            pending_entry=replace(
                continued.next_state.pending_entry,
                consumed_count=expected_watch_count,
            ),
        )
        working = StrategyStateEnvelope.from_json(working.to_json())

    expired = evaluate_strategy(
        implementation,
        StrategyContext(
            watch[5].end_time,
            Instrument.EUR_USD,
            history + (reference, confirmation) + watch,
            market=MARKET,
        ),
        StrategyParameters(),
        working,
    )
    assert expired.next_state.payload.get("phase") == Phase.SEARCHING.value
    assert expired.next_state.pending_entry is None
