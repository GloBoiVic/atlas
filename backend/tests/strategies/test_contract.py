from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from backend.domain.market_data import Bar, Instrument, PriceComponent, Timeframe
from backend.domain.strategy import (
    Action,
    Rationale,
    StrategyContext,
    StrategyDecision,
    StrategyEvaluation,
    StrategyParameters,
    StrategyState,
)
from backend.strategies.contract import (
    DuplicateBarEvaluationError,
    Strategy,
    StrategyContractError,
    StrategyDefinition,
    StrategyEvaluationError,
    StrategyRegistration,
    evaluate_strategy,
    validate_context,
)


def definition() -> StrategyDefinition:
    return StrategyDefinition(
        "example",
        "Example",
        "Contract fixture",
        (),
        implementation_key="example",
    )


class ExampleStrategy:
    def __init__(self) -> None:
        self.definition = definition()

    def evaluate(
        self,
        context: StrategyContext,
        parameters: StrategyParameters,
        state: StrategyState,
    ) -> StrategyEvaluation:
        return StrategyEvaluation(
            decision=StrategyDecision(Action.NO_ACTION, Rationale("TEST")),
            next_state=state,
        )


def bar(at: datetime) -> Bar:
    return Bar(
        Instrument.EUR_USD,
        Timeframe.M15,
        PriceComponent.MID,
        at,
        at + timedelta(minutes=15),
        Decimal("1.1000"),
        Decimal("1.1100"),
        Decimal("1.0900"),
        Decimal("1.1050"),
    )


def test_registration_is_immutable_and_runtime_checkable() -> None:
    implementation = ExampleStrategy()
    registration = StrategyRegistration(implementation.definition, implementation)
    assert isinstance(implementation, Strategy)
    with pytest.raises(AttributeError):
        registration.definition = definition()  # type: ignore[misc]


def test_context_requires_warmup_when_exposure_is_allowed() -> None:
    candle = bar(datetime(2026, 1, 1, 10, 0, tzinfo=UTC))
    context = StrategyContext(candle.end_time, Instrument.EUR_USD, (candle,))
    with pytest.raises(StrategyContractError, match="warm-up"):
        validate_context(context, StrategyState(), definition())


def test_non_ema_strategy_uses_declared_analytical_metadata() -> None:
    candle = bar(datetime(2026, 1, 1, 10, 0, tzinfo=UTC))
    non_ema_definition = StrategyDefinition(
        "range_observer",
        "Range Observer",
        "Non-EMA contract fixture",
        (),
        required_historical_context_bars=0,
        required_instrument=Instrument.EUR_USD,
        required_resolution=Timeframe.M15,
        required_price_component=PriceComponent.MID,
        implementation_key="range_observer.v1",
    )
    validate_context(
        StrategyContext(candle.end_time, Instrument.EUR_USD, (candle,)),
        StrategyState(),
        non_ema_definition,
    )


def test_duplicate_frontier_is_typed_and_does_not_call_strategy() -> None:
    candle = bar(datetime(2026, 1, 1, 10, 0, tzinfo=UTC))
    state = StrategyState(last_evaluated_bar_end=candle.end_time)
    context = StrategyContext(
        candle.end_time, Instrument.EUR_USD, (candle,), exposure_allowed=False
    )
    implementation = ExampleStrategy()
    with pytest.raises(DuplicateBarEvaluationError):
        evaluate_strategy(implementation, context, StrategyParameters(), state)


def test_unexpected_implementation_failure_is_typed() -> None:
    class Broken(ExampleStrategy):
        def evaluate(
            self,
            context: StrategyContext,
            parameters: StrategyParameters,
            state: StrategyState,
        ) -> StrategyEvaluation:
            raise RuntimeError("failure")

    candles = tuple(
        bar(datetime(2026, 1, 1, 10, 0, tzinfo=UTC) + timedelta(minutes=15 * index))
        for index in range(100)
    )
    context = StrategyContext(candles[-1].end_time, Instrument.EUR_USD, candles)
    with pytest.raises(StrategyEvaluationError):
        evaluate_strategy(Broken(), context, StrategyParameters(), StrategyState())
