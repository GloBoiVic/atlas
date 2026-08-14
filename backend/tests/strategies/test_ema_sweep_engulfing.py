from datetime import UTC, datetime, timedelta
from decimal import Decimal

from backend.domain.market_data import Bar, Instrument, PriceComponent, Timeframe
from backend.domain.strategy import (
    Action,
    Direction,
    Phase,
    Position,
    StrategyContext,
    StrategyParameters,
    StrategyState,
)
from backend.strategies.contract import evaluate_strategy
from backend.strategies.ema_sweep_engulfing import EmaSweepEngulfingStrategy
from backend.strategies.indicators import atr_14


def candle(index: int, open_: str, high: str, low: str, close: str) -> Bar:
    start = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=15 * index)
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


def context(bars: tuple[Bar, ...], allowed: bool = True) -> StrategyContext:
    return StrategyContext(
        bars[-1].end_time, Instrument.EUR_USD, bars, exposure_allowed=allowed
    )


def test_long_immediate_confirmation_uses_confirmation_low_for_stop() -> None:
    history = tuple(
        candle(index, "1.1000", "1.1010", "1.0990", "1.1000") for index in range(99)
    )
    reference = candle(99, "1.1020", "1.1030", "1.0995", "1.1010")
    sweep_and_confirmation = candle(100, "1.1000", "1.1040", "1.0980", "1.1035")
    strategy = EmaSweepEngulfingStrategy()

    identified = evaluate_strategy(
        strategy, context(history + (reference,)), StrategyParameters(), StrategyState()
    )
    opened = evaluate_strategy(
        strategy,
        context(history + (reference, sweep_and_confirmation)),
        StrategyParameters(),
        identified.next_state,
    )

    assert opened.decision.action is Action.OPEN_LONG
    assert opened.decision.stop is not None
    assert opened.decision.stop.price == Decimal("1.096807397959183673469387755")
    assert opened.decision.target is not None
    assert opened.decision.target.to_json() == {
        "methodology": "R_MULTIPLE",
        "multiple": "1.7",
    }
    assert opened.next_state.phase is Phase.SEARCHING
    assert dict(opened.decision.rationale.fields) == {
        "trend_relation": "close_above_ema_100_at_reference",
        "reference_time": reference.end_time.isoformat(),
        "reference_high": "1.1030",
        "reference_low": "1.0995",
        "sweep_time": sweep_and_confirmation.end_time.isoformat(),
        "sweep_high": "1.1040",
        "sweep_low": "1.0980",
        "confirmation_time": sweep_and_confirmation.end_time.isoformat(),
        "confirmation_high": "1.1040",
        "confirmation_low": "1.0980",
        "atr": str(atr_14(history + (reference, sweep_and_confirmation))),
        "stop_buffer": "0.5",
        "stop_structure": "confirmation_low - (stop_buffer * ATR)",
        "stop_price": "1.096807397959183673469387755",
    }


def test_reference_requires_trend_and_doji_is_not_a_reference() -> None:
    history = tuple(
        candle(index, "1.1000", "1.1010", "1.0990", "1.1000") for index in range(99)
    )
    doji = candle(99, "1.1020", "1.1030", "1.0990", "1.1020")
    bearish_below_ema = candle(100, "1.0990", "1.1010", "1.0980", "1.0985")
    result = evaluate_strategy(
        EmaSweepEngulfingStrategy(),
        context(history + (doji, bearish_below_ema)),
        StrategyParameters(),
        StrategyState(),
    )
    assert result.decision.action is Action.NO_ACTION
    assert result.next_state.phase is Phase.SEARCHING


def test_short_immediate_confirmation_uses_confirmation_high_for_stop() -> None:
    history = tuple(
        candle(index, "1.1000", "1.1010", "1.0990", "1.1000") for index in range(99)
    )
    reference = candle(99, "1.0980", "1.1010", "1.0970", "1.0990")
    sweep_and_confirmation = candle(100, "1.1000", "1.1020", "1.0950", "1.0960")
    strategy = EmaSweepEngulfingStrategy()
    identified = evaluate_strategy(
        strategy, context(history + (reference,)), StrategyParameters(), StrategyState()
    )
    opened = evaluate_strategy(
        strategy,
        context(history + (reference, sweep_and_confirmation)),
        StrategyParameters(),
        identified.next_state,
    )
    assert opened.decision.action is Action.OPEN_SHORT
    assert opened.decision.stop is not None
    assert opened.decision.stop.price == Decimal("1.103244897959183673469387755")
    assert dict(opened.decision.rationale.fields)["trend_relation"] == (
        "close_below_ema_100_at_reference"
    )


def test_setup_counts_received_bars_w1_to_w5_and_never_reuses_w5() -> None:
    history = tuple(
        candle(index, "1.1000", "1.1010", "1.0990", "1.1000") for index in range(99)
    )
    reference = candle(99, "1.1020", "1.1030", "1.0995", "1.1010")
    state = evaluate_strategy(
        EmaSweepEngulfingStrategy(),
        context(history + (reference,)),
        StrategyParameters(),
        StrategyState(),
    ).next_state
    received = tuple(
        candle(index, "1.1000", "1.1010", "1.0990", "1.1000")
        for index in (101, 103, 104, 108, 109)
    )
    result = evaluate_strategy(
        EmaSweepEngulfingStrategy(),
        context(history + (reference,) + received),
        StrategyParameters(),
        state,
    )
    assert result.next_state.phase is Phase.SEARCHING
    assert result.next_state.last_evaluated_bar_end == received[-1].end_time

    next_reference = candle(110, "1.1020", "1.1030", "1.0995", "1.1010")
    resumed = evaluate_strategy(
        EmaSweepEngulfingStrategy(),
        context(history + (reference,) + received + (next_reference,)),
        StrategyParameters(),
        result.next_state,
    )
    assert resumed.next_state.phase is Phase.REFERENCE_IDENTIFIED
    assert resumed.next_state.reference_time == next_reference.end_time


def test_active_setup_restart_and_repeated_input_are_identical() -> None:
    history = tuple(
        candle(index, "1.1000", "1.1010", "1.0990", "1.1000") for index in range(99)
    )
    reference = candle(99, "1.1020", "1.1030", "1.0995", "1.1010")
    sweep = candle(100, "1.1000", "1.1010", "1.0980", "1.1005")
    confirmation = candle(101, "1.1000", "1.1040", "1.0995", "1.1035")
    strategy = EmaSweepEngulfingStrategy()
    reference_state = evaluate_strategy(
        strategy, context(history + (reference,)), StrategyParameters(), StrategyState()
    ).next_state
    active_state = evaluate_strategy(
        strategy,
        context(history + (reference, sweep)),
        StrategyParameters(),
        reference_state,
    ).next_state
    first = evaluate_strategy(
        strategy,
        context(history + (reference, sweep, confirmation)),
        StrategyParameters(),
        active_state,
    )
    second = evaluate_strategy(
        strategy,
        context(history + (reference, sweep, confirmation)),
        StrategyParameters(),
        active_state,
    )
    assert first.to_json() == second.to_json()
    assert first.decision.action is Action.OPEN_LONG


def test_safety_gate_clears_active_state_even_for_empty_context() -> None:
    active = StrategyState(
        phase=Phase.AWAITING_CONFIRMATION,
        direction=Direction.LONG,
        reference_high=Decimal("1.10"),
        reference_low=Decimal("1.09"),
        reference_time=datetime(2026, 1, 1, tzinfo=UTC),
        sweep_time=datetime(2026, 1, 1, 0, 15, tzinfo=UTC),
        window_bars=1,
    )
    context_without_bars = StrategyContext(
        datetime(2026, 1, 1, tzinfo=UTC),
        Instrument.EUR_USD,
        (),
        exposure_allowed=False,
    )
    result = EmaSweepEngulfingStrategy().evaluate(
        context_without_bars, StrategyParameters(), active
    )
    assert result.decision.action is Action.NO_ACTION
    assert result.next_state == StrategyState()


def test_exposure_gate_clears_setup_without_advancing_it() -> None:
    state = StrategyState(
        phase=Phase.AWAITING_CONFIRMATION,
        direction=Direction.LONG,
        reference_high=Decimal("1.10"),
        reference_low=Decimal("1.09"),
        reference_time=datetime(2026, 1, 1, tzinfo=UTC),
        sweep_time=datetime(2026, 1, 1, 0, 15, tzinfo=UTC),
        window_bars=1,
    )
    bar = candle(2, "1.1000", "1.1010", "1.0990", "1.1005")
    result = EmaSweepEngulfingStrategy().evaluate(
        context((candle(1, "1.1000", "1.1010", "1.0990", "1.1000"), bar), False),
        StrategyParameters(),
        state,
    )

    assert result.decision.action is Action.NO_ACTION
    assert result.next_state.phase is Phase.SEARCHING
    assert result.next_state.last_evaluated_bar_end == bar.end_time


def test_non_flat_position_does_not_open_or_keep_setup() -> None:
    bar = candle(0, "1.1000", "1.1010", "1.0990", "1.1005")
    result = EmaSweepEngulfingStrategy().evaluate(
        StrategyContext(
            bar.end_time,
            Instrument.EUR_USD,
            (bar,),
            position=Position.LONG,
            exposure_allowed=False,
        ),
        StrategyParameters(),
        StrategyState(),
    )
    assert result.decision.action is Action.NO_ACTION
    assert result.next_state.phase is Phase.SEARCHING


def _identified_long() -> tuple[tuple[Bar, ...], Bar, StrategyState]:
    history = tuple(
        candle(index, "1.1000", "1.1010", "1.0990", "1.1000") for index in range(99)
    )
    reference = candle(99, "1.1020", "1.1030", "1.0995", "1.1010")
    identified = evaluate_strategy(
        EmaSweepEngulfingStrategy(),
        context(history + (reference,)),
        StrategyParameters(),
        StrategyState(),
    )
    return history, reference, identified.next_state


def test_unswept_trend_reversal_does_not_invalidate_reference() -> None:
    history, reference, state = _identified_long()
    reversal = candle(100, "1.1010", "1.1020", "1.0980", "1.0990")
    result = evaluate_strategy(
        EmaSweepEngulfingStrategy(),
        context(history + (reference, reversal)),
        StrategyParameters(),
        state,
    )
    assert result.decision.action is Action.NO_ACTION
    assert result.next_state == StrategyState(
        phase=Phase.REFERENCE_IDENTIFIED,
        direction=Direction.LONG,
        reference_high=reference.high,
        reference_low=reference.low,
        reference_time=reference.end_time,
        window_bars=1,
        last_evaluated_bar_end=reversal.end_time,
    )


def test_swept_trend_reversal_does_not_invalidate_active_setup() -> None:
    history, reference, state = _identified_long()
    sweep = candle(100, "1.1000", "1.1010", "1.0980", "1.1005")
    reversal = candle(101, "1.1010", "1.1020", "1.0980", "1.0990")
    swept = evaluate_strategy(
        EmaSweepEngulfingStrategy(),
        context(history + (reference, sweep)),
        StrategyParameters(),
        state,
    )
    result = evaluate_strategy(
        EmaSweepEngulfingStrategy(),
        context(history + (reference, sweep, reversal)),
        StrategyParameters(),
        swept.next_state,
    )
    assert result.decision.action is Action.NO_ACTION
    assert result.next_state == StrategyState(
        phase=Phase.AWAITING_CONFIRMATION,
        direction=Direction.LONG,
        reference_high=reference.high,
        reference_low=reference.low,
        reference_time=reference.end_time,
        sweep_time=sweep.end_time,
        window_bars=2,
        last_evaluated_bar_end=reversal.end_time,
    )


def test_long_and_short_equality_at_reference_level_is_not_a_sweep() -> None:
    history, reference, state = _identified_long()
    long_equal = candle(100, "1.1000", "1.1040", "1.0995", "1.1035")
    long_result = evaluate_strategy(
        EmaSweepEngulfingStrategy(),
        context(history + (reference, long_equal)),
        StrategyParameters(),
        state,
    )
    assert long_result.decision.action is Action.NO_ACTION
    assert long_result.next_state.phase is Phase.REFERENCE_IDENTIFIED
    assert long_result.next_state.sweep_time is None

    short_reference = candle(99, "1.0980", "1.1010", "1.0970", "1.0990")
    short_state = evaluate_strategy(
        EmaSweepEngulfingStrategy(),
        context(history + (short_reference,)),
        StrategyParameters(),
        StrategyState(),
    ).next_state
    short_equal = candle(100, "1.1000", "1.1010", "1.0960", "1.0965")
    short_result = evaluate_strategy(
        EmaSweepEngulfingStrategy(),
        context(history + (short_reference, short_equal)),
        StrategyParameters(),
        short_state,
    )
    assert short_result.decision.action is Action.NO_ACTION
    assert short_result.next_state.phase is Phase.REFERENCE_IDENTIFIED
    assert short_result.next_state.sweep_time is None


def test_confirmation_on_w5_opens() -> None:
    history, reference, state = _identified_long()
    received = (
        candle(100, "1.1000", "1.1010", "1.0980", "1.1005"),
        candle(101, "1.1000", "1.1010", "1.0990", "1.1005"),
        candle(102, "1.1000", "1.1010", "1.0990", "1.1005"),
        candle(103, "1.1000", "1.1010", "1.0990", "1.1005"),
        candle(104, "1.1000", "1.1040", "1.0990", "1.1035"),
    )
    result = evaluate_strategy(
        EmaSweepEngulfingStrategy(),
        context(history + (reference,) + received),
        StrategyParameters(),
        state,
    )
    assert result.decision.action is Action.OPEN_LONG
    assert result.next_state == StrategyState(
        last_evaluated_bar_end=received[-1].end_time
    )


def test_previously_swept_setup_without_confirmation_expires_on_w5() -> None:
    history, reference, state = _identified_long()
    received = (
        candle(100, "1.1000", "1.1010", "1.0980", "1.1005"),
        candle(101, "1.1000", "1.1010", "1.0990", "1.1005"),
        candle(102, "1.1000", "1.1010", "1.0990", "1.1005"),
        candle(103, "1.1000", "1.1010", "1.0990", "1.1005"),
        candle(104, "1.1000", "1.1010", "1.0990", "1.1005"),
    )
    result = evaluate_strategy(
        EmaSweepEngulfingStrategy(),
        context(history + (reference,) + received),
        StrategyParameters(),
        state,
    )
    assert result.decision.action is Action.NO_ACTION
    assert result.next_state == StrategyState(
        last_evaluated_bar_end=received[-1].end_time
    )


def test_first_sweep_on_w5_without_confirmation_expires_on_w5() -> None:
    history, reference, state = _identified_long()
    received = (
        candle(100, "1.1000", "1.1010", "1.0990", "1.1005"),
        candle(101, "1.1000", "1.1010", "1.0990", "1.1005"),
        candle(102, "1.1000", "1.1010", "1.0990", "1.1005"),
        candle(103, "1.1000", "1.1010", "1.0990", "1.1005"),
        candle(104, "1.1000", "1.1010", "1.0980", "1.1005"),
    )
    result = evaluate_strategy(
        EmaSweepEngulfingStrategy(),
        context(history + (reference,) + received),
        StrategyParameters(),
        state,
    )
    assert result.decision.action is Action.NO_ACTION
    assert result.next_state == StrategyState(
        last_evaluated_bar_end=received[-1].end_time
    )


def test_doji_neither_sweeps_nor_confirms() -> None:
    history, reference, state = _identified_long()
    doji = candle(100, "1.1000", "1.1040", "1.0980", "1.1000")
    result = evaluate_strategy(
        EmaSweepEngulfingStrategy(),
        context(history + (reference, doji)),
        StrategyParameters(),
        state,
    )
    assert result.decision.action is Action.NO_ACTION
    assert result.next_state.phase is Phase.REFERENCE_IDENTIFIED
    assert result.next_state.sweep_time is None
    assert result.next_state.window_bars == 1


def test_non_flat_reference_and_active_states_clear_without_opening() -> None:
    history, reference, reference_state = _identified_long()
    sweep = candle(100, "1.1000", "1.1010", "1.0980", "1.1005")
    active_state = evaluate_strategy(
        EmaSweepEngulfingStrategy(),
        context(history + (reference, sweep)),
        StrategyParameters(),
        reference_state,
    ).next_state
    next_bar = candle(101, "1.1000", "1.1040", "1.0990", "1.1035")
    strategy = EmaSweepEngulfingStrategy()
    for setup_state in (reference_state, active_state):
        result = strategy.evaluate(
            StrategyContext(
                next_bar.end_time,
                Instrument.EUR_USD,
                (next_bar,),
                position=Position.LONG,
            ),
            StrategyParameters(),
            setup_state,
        )
        assert result.decision.action is Action.NO_ACTION
        assert result.next_state == StrategyState(
            last_evaluated_bar_end=next_bar.end_time
        )
