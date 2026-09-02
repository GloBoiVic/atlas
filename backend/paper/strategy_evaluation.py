"""Compose one current analytical frontier with the verified Strategy boundary.

This operation is deliberately read-only and one-shot.  It resolves the exact
persisted StrategyVersion, prepares caller-held Strategy state when necessary,
and delegates every Strategy call to the checked public contract.  It does not
make Risk, execution, accounting, persistence-write, or broker decisions.
"""

from collections.abc import Mapping
from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy.orm import Session

from backend.domain import (
    FinancialPositionState,
    Instrument,
    MarketSpecification,
    ParameterSchema,
    PositionState,
    PriceComponent,
    StrategyContext,
    StrategyEvaluation,
    StrategyStateEnvelope,
    StrategyVersion,
    Timeframe,
    ValidatedParameterPayload,
)
from backend.integrations.oanda.capabilities import (
    OANDA_CAPABILITY,
    validate_market_specification,
)
from backend.persistence.strategy_repository import (
    StrategyRepository,
    version_to_domain,
)
from backend.strategies import (
    evaluate_strategy,
    initial_strategy_state,
    validate_state,
)
from backend.strategies.contract import StrategyDefinition
from backend.strategies.registry import StrategyRegistry

from .current_analytical_frontier import (
    NativeM15Source,
    load_current_analytical_frontier,
)


class PaperStrategyEvaluationError(ValueError):
    """The PAPER Strategy-only operation cannot proceed safely."""


def _strategy_position(value: FinancialPositionState) -> PositionState:
    """Translate financial exposure into the distinct Strategy position type."""
    if value is FinancialPositionState.FLAT:
        return PositionState.FLAT
    if value is FinancialPositionState.LONG:
        return PositionState.LONG
    if value is FinancialPositionState.SHORT:
        return PositionState.SHORT
    raise PaperStrategyEvaluationError("financial position state is invalid")


def _metadata_mismatches(
    version: StrategyVersion, definition: StrategyDefinition
) -> tuple[str, ...]:
    checks = (
        ("parameter_schema", version.parameter_schema, definition.parameter_schema),
        ("primary_timeframe", version.primary_timeframe, definition.primary_timeframe),
        (
            "required_historical_context_bars",
            version.required_historical_context_bars,
            definition.required_historical_context_bars,
        ),
        (
            "state_schema_version",
            version.state_schema_version,
            definition.state_schema_version,
        ),
    )
    return tuple(name for name, persisted, local in checks if persisted != local)


def _validated_parameters(
    values: object, schema: tuple[ParameterSchema, ...]
) -> ValidatedParameterPayload:
    if not isinstance(values, Mapping):
        raise PaperStrategyEvaluationError("parameter_values must be a mapping")
    return ValidatedParameterPayload.from_mapping(
        schema,
        dict(cast(Mapping[str, object], values)),
    )


def _require_current_analytical_contract(definition: StrategyDefinition) -> None:
    """Reject local code whose declared input is outside the current provider."""
    if (
        definition.required_instrument is not Instrument.EUR_USD
        or definition.required_resolution is not Timeframe.M15
        or definition.required_price_component is not PriceComponent.MID
        or definition.primary_timeframe is not Timeframe.M15
        or definition.completed_only is not True
        or not OANDA_CAPABILITY.supports(
            definition.required_resolution, definition.required_price_component
        )
    ):
        raise PaperStrategyEvaluationError(
            "Strategy analytical contract is not supported by OANDA EUR/USD M15 MID"
        )


def evaluate_current_paper_strategy(
    session: Session,
    *,
    strategy_version_id: UUID,
    parameter_values: Mapping[str, object],
    state: StrategyStateEnvelope | None,
    financial_position_state: FinancialPositionState,
    now: datetime,
    strategy_repository: StrategyRepository,
    strategy_registry: StrategyRegistry,
    analytical_source: NativeM15Source,
    market_specification: MarketSpecification,
) -> StrategyEvaluation:
    """Evaluate exactly one current completed analytical frontier.

    ``now`` is passed only to the bounded analytical read.  Strategy clocks are
    constructed from each evaluated bar's completed ``end_time``.
    """
    if type(strategy_version_id) is not UUID:
        raise PaperStrategyEvaluationError("strategy_version_id must be a UUID")

    position = _strategy_position(financial_position_state)
    if state is None and position is not PositionState.FLAT:
        raise PaperStrategyEvaluationError(
            "initial Strategy bootstrap requires a FLAT financial position"
        )
    if state is not None and type(state) is not StrategyStateEnvelope:
        raise PaperStrategyEvaluationError("state must be a StrategyStateEnvelope")

    validate_market_specification(market_specification)

    version_row = strategy_repository.get_version(session, strategy_version_id)
    if version_row is None:
        raise PaperStrategyEvaluationError(
            f"StrategyVersion {strategy_version_id} does not exist"
        )
    version = version_to_domain(version_row)
    implementation = strategy_registry.implementation_for_version(version)

    definition = implementation.definition
    mismatches = _metadata_mismatches(version, definition)
    if mismatches:
        raise PaperStrategyEvaluationError(
            "persisted/local Strategy metadata disagrees: " + ", ".join(mismatches)
        )
    _require_current_analytical_contract(definition)

    parameters = _validated_parameters(parameter_values, version.parameter_schema)

    if state is not None:
        validate_state(state, definition)
        if state.pending_entry is not None:
            raise PaperStrategyEvaluationError(
                "restored Strategy state has an unresolved pending entry"
            )
        if state.last_evaluated_bar_end is None:
            raise PaperStrategyEvaluationError(
                "restored Strategy state must contain a prior analytical frontier"
            )

    warm_up_bars = definition.required_historical_context_bars
    if state is not None:
        # A zero-warm-up Strategy still needs one prior eligible frontier to
        # prove that a restored state advances one frontier at a time.
        warm_up_bars = max(warm_up_bars, 1)
    frontier = load_current_analytical_frontier(
        analytical_source,
        now=now,
        warm_up_m15_bars=warm_up_bars,
    )

    if state is not None:
        last_frontier = state.last_evaluated_bar_end
        if last_frontier is not None and (
            last_frontier < frontier.current_frontier
            and last_frontier != frontier.previous_frontier
        ):
            raise PaperStrategyEvaluationError(
                "restored Strategy state is not caught up to the immediately "
                "preceding analytical frontier"
            )

    if state is None:
        working_state = initial_strategy_state(implementation)
        warmup_bars = frontier.context_bars[:-1]
        for index, bar in enumerate(warmup_bars):
            evaluation = evaluate_strategy(
                implementation,
                StrategyContext(
                    evaluation_time=bar.end_time,
                    instrument=Instrument.EUR_USD,
                    bars=frontier.context_bars[: index + 1],
                    market=market_specification,
                    position=PositionState.FLAT,
                    exposure_allowed=False,
                ),
                parameters,
                working_state,
            )
            working_state = _next_state(evaluation)
    else:
        working_state = state

    return evaluate_strategy(
        implementation,
        StrategyContext(
            evaluation_time=frontier.current_bar.end_time,
            instrument=Instrument.EUR_USD,
            bars=frontier.context_bars,
            market=market_specification,
            position=position,
            exposure_allowed=True,
        ),
        parameters,
        working_state,
    )


def _next_state(evaluation: StrategyEvaluation) -> StrategyStateEnvelope:
    """Narrow the checked entry point's compatibility union for the next call."""
    if type(evaluation.next_state) is not StrategyStateEnvelope:
        raise PaperStrategyEvaluationError(
            "Strategy evaluation did not return a state envelope"
        )
    return evaluation.next_state


__all__ = [
    "PaperStrategyEvaluationError",
    "evaluate_current_paper_strategy",
]
