from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from backend.domain.market_data import Bar, Instrument, PriceComponent, Timeframe
from backend.domain.strategy import (
    Action,
    Direction,
    MarketSpecification,
    ParameterSchema,
    PositionState,
    Rationale,
    StopProposal,
    StrategyContext,
    StrategyDecision,
    StrategyEvaluation,
    StrategyParameterSet,
    StrategyStateEnvelope,
    StrategyStatePayloadDocument,
    TargetProposal,
    ValidatedParameterPayload,
)
from backend.strategies.contract import (
    DuplicateBarEvaluationError,
    Strategy,
    StrategyContractError,
    StrategyDefinition,
    StrategyEvaluationError,
    StrategyRegistration,
    evaluate_strategy,
    initial_strategy_state,
    validate_context,
)

MARKET = MarketSpecification(Instrument.EUR_USD, Decimal("0.0001"))


def definition() -> StrategyDefinition:
    return StrategyDefinition(
        "example",
        "Example",
        "Contract fixture",
        (),
        implementation_key="example",
    )


def state_envelope(
    schema_version: int = 1, frontier: datetime | None = None
) -> StrategyStateEnvelope:
    return StrategyStateEnvelope(
        schema_version,
        frontier,
        StrategyStatePayloadDocument.from_mapping("example.v1", 1, {}),
    )


class ExampleStrategy:
    def __init__(self) -> None:
        self.definition = definition()

    def evaluate(
        self,
        context: StrategyContext,
        parameters: StrategyParameterSet,
        state: StrategyStateEnvelope,
    ) -> StrategyEvaluation:
        return StrategyEvaluation(
            decision=StrategyDecision(Action.NO_ACTION, Rationale("TEST")),
            next_state=state,
        )


class UnsafeOpeningStrategy(ExampleStrategy):
    def __init__(self) -> None:
        self.definition = StrategyDefinition(
            "unsafe_example",
            "Unsafe Example",
            "Malicious contract fixture",
            (),
            required_historical_context_bars=0,
            implementation_key="unsafe_example.v1",
        )

    def evaluate(
        self,
        context: StrategyContext,
        parameters: StrategyParameterSet,
        state: StrategyStateEnvelope,
    ) -> StrategyEvaluation:
        next_state = (
            state.advance_to(context.bars[-1].end_time, context.evaluation_time)
            if context.bars
            else state
        )
        return StrategyEvaluation(
            decision=StrategyDecision(
                action=Action.OPEN_LONG,
                rationale=Rationale("MALICIOUS_GENERIC_OPEN"),
                direction=Direction.LONG,
                decision_time=context.evaluation_time,
                stop=StopProposal(Decimal("1.0900"), Direction.LONG),
                target=TargetProposal(),
            ),
            next_state=next_state,
        )


class EmptyParameters:
    def to_json(self) -> dict[str, object]:
        return {}


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
    context = StrategyContext(
        candle.end_time, Instrument.EUR_USD, (candle,), market=MARKET
    )
    with pytest.raises(StrategyContractError, match="warm-up"):
        validate_context(context, state_envelope(), definition())


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
        StrategyContext(
            candle.end_time, Instrument.EUR_USD, (candle,), market=MARKET
        ),
        state_envelope(),
        non_ema_definition,
    )


def test_duplicate_frontier_is_typed_and_does_not_call_strategy() -> None:
    candle = bar(datetime(2026, 1, 1, 10, 0, tzinfo=UTC))
    state = state_envelope(frontier=candle.end_time)
    context = StrategyContext(
        candle.end_time,
        Instrument.EUR_USD,
        (candle,),
        market=MARKET,
        exposure_allowed=False,
    )
    implementation = ExampleStrategy()
    with pytest.raises(DuplicateBarEvaluationError):
        evaluate_strategy(implementation, context, EmptyParameters(), state)


def test_public_boundary_rejects_unsafe_generic_open_when_exposure_is_blocked() -> None:
    evaluation_time = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
    context = StrategyContext(
        evaluation_time,
        Instrument.EUR_USD,
        (),
        market=MARKET,
        exposure_allowed=False,
    )

    with pytest.raises(StrategyContractError, match="opening"):
        evaluate_strategy(
            UnsafeOpeningStrategy(), context, EmptyParameters(), state_envelope()
        )


def test_public_boundary_rejects_unsafe_generic_open_with_existing_position() -> None:
    candle = bar(datetime(2026, 1, 1, 10, 0, tzinfo=UTC))
    context = StrategyContext(
        candle.end_time,
        Instrument.EUR_USD,
        (candle,),
        market=MARKET,
        position=PositionState.LONG,
    )

    with pytest.raises(StrategyContractError, match="opening"):
        evaluate_strategy(
            UnsafeOpeningStrategy(), context, EmptyParameters(), state_envelope()
        )


def test_future_envelope_frontier_is_rejected_without_bars() -> None:
    evaluation_time = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
    state = StrategyStateEnvelope(
        1,
        evaluation_time + timedelta(minutes=15),
        StrategyStatePayloadDocument.from_mapping("example.v1", 1, {}),
    )
    context = StrategyContext(
        evaluation_time,
        Instrument.EUR_USD,
        (),
        market=MARKET,
        exposure_allowed=False,
    )

    with pytest.raises(StrategyContractError, match="future"):
        validate_context(context, state, definition())


def test_unexpected_implementation_failure_is_typed() -> None:
    class Broken(ExampleStrategy):
        def evaluate(
            self,
            context: StrategyContext,
            parameters: StrategyParameterSet,
            state: StrategyStateEnvelope,
        ) -> StrategyEvaluation:
            raise RuntimeError("failure")

    candles = tuple(
        bar(datetime(2026, 1, 1, 10, 0, tzinfo=UTC) + timedelta(minutes=15 * index))
        for index in range(100)
    )
    context = StrategyContext(
        candles[-1].end_time, Instrument.EUR_USD, candles, market=MARKET
    )
    with pytest.raises(StrategyEvaluationError):
        evaluate_strategy(Broken(), context, EmptyParameters(), state_envelope())


def test_generic_payload_parser_and_envelope_are_the_public_seams() -> None:
    schema = (
        ParameterSchema("count", "Count", "integer", 1, False, 1, 3, "count"),
    )

    class GenericStrategy:
        definition = StrategyDefinition(
            "generic",
            "Generic",
            "Generic contract fixture",
            schema,
            required_historical_context_bars=0,
            state_schema_version=3,
            implementation_key="generic.v1",
        )

        @staticmethod
        def parse_parameters(payload: ValidatedParameterPayload):
            return type("Parameters", (), {"to_json": lambda self: payload.to_json()})()

        @classmethod
        def initial_state(cls) -> StrategyStateEnvelope:
            return StrategyStateEnvelope(
                3,
                None,
                StrategyStatePayloadDocument.from_mapping("generic.v1", 1, {}),
            )

        def evaluate(self, context, parameters, state):
            assert parameters.to_json() == {"count": 2}
            return StrategyEvaluation(
                StrategyDecision(Action.NO_ACTION, Rationale("GENERIC")),
                state.advance_to(context.bars[-1].end_time, context.evaluation_time),
            )

    implementation = GenericStrategy()
    state = initial_strategy_state(implementation)
    candle = bar(datetime(2026, 1, 1, 10, 0, tzinfo=UTC))
    result = evaluate_strategy(
        implementation,
        StrategyContext(
            candle.end_time, Instrument.EUR_USD, (candle,), market=MARKET
        ),
        ValidatedParameterPayload.from_mapping(schema, {"count": 2}),
        state,
    )
    assert isinstance(result.next_state, StrategyStateEnvelope)
    assert result.next_state.last_evaluated_bar_end == candle.end_time
