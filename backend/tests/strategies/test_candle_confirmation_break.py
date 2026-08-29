from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from backend.domain.market_data import Bar, Instrument, PriceComponent, Timeframe
from backend.domain.strategy import (
    Action,
    EntryPolicy,
    ParameterError,
    PositionState,
    StrategyContext,
    StrategyStateEnvelope,
    StrategyStatePayloadDocument,
    ValidatedParameterPayload,
)
from backend.strategies.candle_confirmation_break import (
    CANDLE_CONFIRMATION_BREAK_EVIDENCE_SCHEMA,
    CandleConfirmationBreakStrategy,
    CandleConfirmationParameters,
)
from backend.strategies.contract import (
    Strategy,
    StrategyContractError,
    StrategyEvaluationError,
    evaluate_strategy,
    initial_strategy_state,
)
from backend.strategies.production import create_production_strategy_registry

ROOT = Path(__file__).parents[3]
START = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
SCHEMA = CandleConfirmationBreakStrategy.definition.parameter_schema


def candle(
    index: int,
    *,
    open_price: str,
    high: str,
    low: str,
    close: str,
) -> Bar:
    start = START + timedelta(minutes=15 * index)
    return Bar(
        Instrument.EUR_USD,
        Timeframe.M15,
        PriceComponent.MID,
        start,
        start + timedelta(minutes=15),
        Decimal(open_price),
        Decimal(high),
        Decimal(low),
        Decimal(close),
    )


def parameters(**values: object) -> ValidatedParameterPayload:
    return ValidatedParameterPayload.with_defaults(SCHEMA, values)


def candidate_state(
    frontier: datetime | None, started_at: datetime | str
) -> StrategyStateEnvelope:
    return StrategyStateEnvelope(
        1,
        frontier,
        StrategyStatePayloadDocument.from_mapping(
            "candle_confirmation_break.v1",
            1,
            {
                "candidate_direction": "LONG",
                "confirmation_count": 1,
                "candidate_started_at": started_at,
            },
        ),
    )


def context(bars: tuple[Bar, ...], *, exposure_allowed: bool = True) -> StrategyContext:
    return StrategyContext(
        bars[-1].end_time,
        Instrument.EUR_USD,
        bars,
        PositionState.FLAT,
        exposure_allowed,
    )


def test_definition_declares_only_candidate_parameters_and_registration() -> None:
    definition = CandleConfirmationBreakStrategy.definition
    assert definition.strategy_key == "candle_confirmation_break"
    assert definition.implementation_key == "candle_confirmation_break.v1"
    assert definition.required_historical_context_bars == 1
    assert definition.capabilities == ("LONG", "SHORT", "STOP_LOSS", "TAKE_PROFIT")
    assert tuple(item.key for item in definition.parameter_schema) == (
        "confirmation_bars",
        "stop_buffer_pips",
        "target_r",
    )

    entries = {
        entry.definition.strategy_key: entry
        for entry in create_production_strategy_registry(ROOT).catalog()
    }
    entry = entries["candle_confirmation_break"]
    assert entry.implementation is not None
    assert entry.source_archive.manifest == ((
        "backend/strategies/candle_confirmation_break.py",
        (ROOT / "backend/strategies/candle_confirmation_break.py").stat().st_size,
    ),)


def test_parameters_parse_boundaries_and_reject_ema_shape() -> None:
    parsed = CandleConfirmationBreakStrategy.parse_parameters(
        parameters(confirmation_bars=1, stop_buffer_pips="100", target_r="0.5")
    )
    assert parsed == CandleConfirmationParameters(1, Decimal("100"), Decimal("0.5"))
    assert parsed.to_json() == {
        "confirmation_bars": 1,
        "stop_buffer_pips": "100",
        "target_r": "0.5",
    }

    with pytest.raises(ParameterError):
        ValidatedParameterPayload.with_defaults(
            SCHEMA, {"ema_period": 100}
        )
    with pytest.raises(ParameterError):
        ValidatedParameterPayload.from_mapping(
            SCHEMA,
            {"confirmation_bars": 4, "stop_buffer_pips": "20", "target_r": "1.5"},
        )
    with pytest.raises(ParameterError):
        ValidatedParameterPayload.from_mapping(
            SCHEMA,
            {"confirmation_bars": 2, "stop_buffer_pips": "0.99", "target_r": "1.5"},
        )
    with pytest.raises(ParameterError):
        ValidatedParameterPayload.from_mapping(
            SCHEMA,
            {"confirmation_bars": 2, "stop_buffer_pips": "20", "target_r": "5.01"},
        )


def test_typed_parameters_use_the_public_schema_guard() -> None:
    strategy = CandleConfirmationBreakStrategy()
    assert isinstance(strategy, Strategy)
    prior = candle(
        0, open_price="1.1000", high="1.1050", low="1.0950", close="1.1000"
    )
    signal = candle(
        1, open_price="1.1000", high="1.1100", low="1.0980", close="1.1060"
    )
    valid = CandleConfirmationParameters(1, Decimal("20"), Decimal("1.5"))
    direct = strategy.evaluate(
        context((prior, signal)), valid, initial_strategy_state(strategy)
    )
    assert direct.decision.action is Action.OPEN_LONG
    result = evaluate_strategy(
        strategy, context((prior, signal)), valid, initial_strategy_state(strategy)
    )
    assert result.decision.action is Action.OPEN_LONG

    invalid_values = (
        CandleConfirmationParameters(4, Decimal("20"), Decimal("1.5")),
        CandleConfirmationParameters(2, Decimal("0.1"), Decimal("1.5")),
        CandleConfirmationParameters(2, Decimal("20"), Decimal("9")),
    )
    for invalid in invalid_values:
        with pytest.raises(StrategyContractError):
            evaluate_strategy(
                strategy,
                context((prior, signal)),
                invalid,
                initial_strategy_state(strategy),
            )

    with pytest.raises(ParameterError):
        strategy.evaluate(
            context((prior, signal)),
            invalid_values[0],
            initial_strategy_state(strategy),
        )


def test_two_consecutive_bullish_breaks_open_immediately_with_pip_stop_and_evidence(
) -> None:
    strategy = CandleConfirmationBreakStrategy()
    prior = candle(0, open_price="1.1000", high="1.1050", low="1.0950", close="1.1000")
    first = candle(1, open_price="1.1000", high="1.1110", low="1.0980", close="1.1080")
    second = candle(2, open_price="1.1080", high="1.1160", low="1.1060", close="1.1120")
    payload = parameters()

    armed = evaluate_strategy(
        strategy, context((prior, first)), payload, initial_strategy_state(strategy)
    )
    assert armed.decision.action is Action.NO_ACTION
    assert armed.next_state.payload.get("candidate_direction") == "LONG"
    assert armed.next_state.payload.get("confirmation_count") == 1

    result = evaluate_strategy(
        strategy, context((prior, first, second)), payload, armed.next_state
    )
    assert result.decision.action is Action.OPEN_LONG
    assert result.decision.entry_policy is EntryPolicy.IMMEDIATE
    assert result.decision.stop is not None
    assert result.decision.stop.price == Decimal("1.1040")
    assert result.decision.target is not None
    assert result.decision.target.multiple == Decimal("1.5")
    assert result.decision.setup_facts is None
    assert result.decision.evidence is not None
    assert (
        result.decision.evidence.schema_key
        == CANDLE_CONFIRMATION_BREAK_EVIDENCE_SCHEMA
    )
    assert result.decision.evidence.to_json()["fields"]["pip_size"] == "0.0001"
    assert result.decision.evidence.to_json()["fields"]["proposed_stop"] == "1.1040"
    assert result.next_state.payload.get("candidate_direction") is None
    assert result.next_state.payload.get("confirmation_count") == 0


def test_strict_breaks_restart_and_clear_candidate_state() -> None:
    strategy = CandleConfirmationBreakStrategy()
    prior = candle(
        0, open_price="1.1000", high="1.1050", low="1.0950", close="1.1000"
    )
    bullish = candle(
        1, open_price="1.1000", high="1.1100", low="1.0980", close="1.1060"
    )
    bearish = candle(
        2, open_price="1.1060", high="1.1080", low="1.0900", close="1.0940"
    )
    doji = candle(
        3, open_price="1.0940", high="1.1100", low="1.0800", close="1.0940"
    )
    equality = candle(
        4, open_price="1.0940", high="1.1100", low="1.0850", close="1.1100"
    )
    payload = parameters(confirmation_bars=2)

    first = evaluate_strategy(
        strategy, context((prior, bullish)), payload, initial_strategy_state(strategy)
    )
    restarted = evaluate_strategy(
        strategy, context((prior, bullish, bearish)), payload, first.next_state
    )
    assert restarted.decision.action is Action.NO_ACTION
    assert restarted.next_state.payload.get("candidate_direction") == "SHORT"
    assert restarted.next_state.payload.get("confirmation_count") == 1

    cleared = evaluate_strategy(
        strategy,
        context((prior, bullish, bearish, doji)),
        payload,
        restarted.next_state,
    )
    assert cleared.next_state.payload.get("candidate_direction") is None
    assert cleared.next_state.payload.get("confirmation_count") == 0

    no_equality = evaluate_strategy(
        strategy,
        context((prior, bullish, bearish, doji, equality)),
        payload,
        cleared.next_state,
    )
    assert no_equality.decision.action is Action.NO_ACTION
    assert no_equality.next_state.payload.get("candidate_direction") is None


def test_short_stop_and_exposure_block_clears_without_pending_handoff() -> None:
    strategy = CandleConfirmationBreakStrategy()
    prior = candle(
        0, open_price="1.1000", high="1.1050", low="1.0950", close="1.1000"
    )
    signal = candle(
        1, open_price="1.1000", high="1.1020", low="1.0880", close="1.0920"
    )
    payload = parameters(confirmation_bars=1, stop_buffer_pips="10")
    result = evaluate_strategy(
        strategy, context((prior, signal)), payload, initial_strategy_state(strategy)
    )
    assert result.decision.action is Action.OPEN_SHORT
    assert result.decision.stop is not None
    assert result.decision.stop.price == Decimal("1.1030")
    assert result.next_state.pending_entry is None

    blocked = evaluate_strategy(
        strategy,
        context((prior, signal), exposure_allowed=False),
        payload,
        initial_strategy_state(strategy),
    )
    assert blocked.decision.action is Action.NO_ACTION
    assert blocked.next_state.last_evaluated_bar_end == signal.end_time
    assert blocked.next_state.payload.get("candidate_direction") is None


def test_candidate_state_rejects_future_timestamp_without_prior_frontier() -> None:
    strategy = CandleConfirmationBreakStrategy()
    evaluation_time = START + timedelta(minutes=15)
    state = candidate_state(None, evaluation_time + timedelta(minutes=1))
    empty_context = StrategyContext(
        evaluation_time,
        Instrument.EUR_USD,
        (),
        exposure_allowed=False,
    )

    with pytest.raises(StrategyEvaluationError):
        evaluate_strategy(strategy, empty_context, parameters(), state)


def test_candidate_state_rejects_future_timestamp_without_prior_frontier_with_bars(
) -> None:
    strategy = CandleConfirmationBreakStrategy()
    prior = candle(
        0, open_price="1.1000", high="1.1050", low="1.0950", close="1.1000"
    )
    signal = candle(
        1, open_price="1.1000", high="1.1100", low="1.0980", close="1.1060"
    )
    state = candidate_state(None, signal.end_time + timedelta(microseconds=1))

    with pytest.raises(StrategyEvaluationError):
        evaluate_strategy(strategy, context((prior, signal)), parameters(), state)


def test_candidate_state_rejects_future_timestamp_with_prior_frontier() -> None:
    strategy = CandleConfirmationBreakStrategy()
    prior = candle(
        0, open_price="1.1000", high="1.1050", low="1.0950", close="1.1000"
    )
    signal = candle(
        1, open_price="1.1000", high="1.1100", low="1.0980", close="1.1060"
    )
    state = candidate_state(
        prior.end_time, signal.end_time + timedelta(minutes=1)
    )

    with pytest.raises(StrategyEvaluationError):
        evaluate_strategy(strategy, context((prior, signal)), parameters(), state)


def test_candidate_state_rejects_future_timestamp_with_prior_frontier_without_bars(
) -> None:
    strategy = CandleConfirmationBreakStrategy()
    frontier = START + timedelta(minutes=15)
    evaluation_time = frontier + timedelta(minutes=15)
    state = candidate_state(frontier, frontier + timedelta(microseconds=1))
    empty_context = StrategyContext(
        evaluation_time,
        Instrument.EUR_USD,
        (),
        exposure_allowed=False,
    )

    with pytest.raises(StrategyEvaluationError):
        evaluate_strategy(strategy, empty_context, parameters(), state)


@pytest.mark.parametrize(
    ("frontier", "started_at", "with_bars"),
    (
        (None, "not-a-timestamp", False),
        (None, "2026-01-01T10:15:00", True),
        (START + timedelta(minutes=15), "2026-01-01T11:15:00+01:00", False),
        (START + timedelta(minutes=15), "not-a-timestamp", True),
    ),
)
def test_candidate_state_rejects_invalid_timestamp_in_all_frontier_contexts(
    frontier: datetime | None, started_at: str, with_bars: bool
) -> None:
    strategy = CandleConfirmationBreakStrategy()
    prior = candle(
        0, open_price="1.1000", high="1.1050", low="1.0950", close="1.1000"
    )
    signal = candle(
        1, open_price="1.1000", high="1.1100", low="1.0980", close="1.1060"
    )
    if with_bars:
        evaluation_context = context((prior, signal))
    else:
        evaluation_time = (
            frontier + timedelta(minutes=15)
            if frontier is not None
            else START + timedelta(minutes=15)
        )
        evaluation_context = StrategyContext(
            evaluation_time,
            Instrument.EUR_USD,
            (),
            exposure_allowed=False,
        )

    with pytest.raises(StrategyEvaluationError):
        evaluate_strategy(
            strategy,
            evaluation_context,
            parameters(),
            candidate_state(frontier, started_at),
        )


def test_candidate_state_timestamp_equal_to_restored_frontier_is_accepted() -> None:
    strategy = CandleConfirmationBreakStrategy()
    prior = candle(
        0, open_price="1.1000", high="1.1050", low="1.0950", close="1.1000"
    )
    signal = candle(
        1, open_price="1.1000", high="1.1100", low="1.0980", close="1.1060"
    )
    state = candidate_state(prior.end_time, prior.end_time)

    result = evaluate_strategy(strategy, context((prior, signal)), parameters(), state)

    assert result.decision.action is Action.OPEN_LONG


def test_candidate_state_timestamp_equal_to_evaluation_frontier_is_accepted() -> None:
    strategy = CandleConfirmationBreakStrategy()
    prior = candle(
        0, open_price="1.1000", high="1.1050", low="1.0950", close="1.1000"
    )
    signal = candle(
        1, open_price="1.1000", high="1.1100", low="1.0980", close="1.1060"
    )
    state = candidate_state(None, signal.end_time)

    result = evaluate_strategy(
        strategy,
        context((prior, signal)),
        parameters(confirmation_bars=1),
        state,
    )

    assert result.decision.action is Action.OPEN_LONG


def test_state_round_trip_continues_deterministically() -> None:
    strategy = CandleConfirmationBreakStrategy()
    prior = candle(
        0, open_price="1.1000", high="1.1050", low="1.0950", close="1.1000"
    )
    first = candle(
        1, open_price="1.1000", high="1.1100", low="1.0980", close="1.1060"
    )
    second = candle(
        2, open_price="1.1060", high="1.1150", low="1.1030", close="1.1110"
    )
    payload = parameters()
    initial = initial_strategy_state(strategy)
    first_result = evaluate_strategy(
        strategy, context((prior, first)), payload, initial
    )
    restored = StrategyStateEnvelope.from_json(first_result.next_state.to_json())

    continued = evaluate_strategy(
        strategy, context((prior, first, second)), payload, restored
    )
    replayed = evaluate_strategy(
        strategy, context((prior, first, second)), payload, first_result.next_state
    )
    assert continued.to_json() == replayed.to_json()
    assert restored.canonical_bytes == first_result.next_state.canonical_bytes


def test_candidate_state_rejects_wrong_codec() -> None:
    strategy = CandleConfirmationBreakStrategy()
    state = StrategyStateEnvelope(
        1,
        None,
        StrategyStatePayloadDocument.from_mapping(
            "not-candle-confirmation", 1,
            {
                "candidate_direction": None,
                "confirmation_count": 0,
                "candidate_started_at": None,
            },
        ),
    )
    prior = candle(
        0, open_price="1.1000", high="1.1050", low="1.0950", close="1.1000"
    )
    with pytest.raises(StrategyEvaluationError):
        evaluate_strategy(strategy, context((prior,)), parameters(), state)
