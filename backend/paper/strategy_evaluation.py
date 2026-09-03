"""Compose one current analytical frontier with the verified Strategy boundary.

This operation is deliberately read-only and one-shot.  It resolves the exact
persisted StrategyVersion, prepares caller-held Strategy state when necessary,
and delegates every Strategy call to the checked public contract.  It does not
make Risk, execution, accounting, persistence-write, or broker decisions.
"""

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, cast
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
    CurrentAnalyticalFrontier,
    NativeM15Source,
    load_current_analytical_frontier,
)

if TYPE_CHECKING:
    from .persistence_contracts import PaperStrategyEvaluationReceipt


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
    frontier: CurrentAnalyticalFrontier | None = None,
) -> StrategyEvaluation:
    """Evaluate one current completed frontier, preserving the PAPER 04 seam."""
    _, _, evaluation = _evaluate_current_paper_strategy(
        session,
        strategy_version_id=strategy_version_id,
        parameter_values=parameter_values,
        state=state,
        financial_position_state=financial_position_state,
        now=now,
        strategy_repository=strategy_repository,
        strategy_registry=strategy_registry,
        analytical_source=analytical_source,
        market_specification=market_specification,
        frontier=frontier,
    )
    return evaluation


def evaluate_current_paper_strategy_receipt(
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
    frontier: CurrentAnalyticalFrontier | None = None,
) -> "PaperStrategyEvaluationReceipt":
    """Return the exact version/parameters alongside their produced decision.

    This is the execution-oriented handoff.  The returned receipt is produced
    by the same validation and evaluation operation as
    :func:`evaluate_current_paper_strategy`; callers cannot provide an
    unrelated ``StrategyDecision`` as a provenance sidecar.
    """
    version, parameters, evaluation = _evaluate_current_paper_strategy(
        session,
        strategy_version_id=strategy_version_id,
        parameter_values=parameter_values,
        state=state,
        financial_position_state=financial_position_state,
        now=now,
        strategy_repository=strategy_repository,
        strategy_registry=strategy_registry,
        analytical_source=analytical_source,
        market_specification=market_specification,
        frontier=frontier,
    )
    from .persistence_contracts import PaperStrategyEvaluationReceipt

    return PaperStrategyEvaluationReceipt.from_verified(version, parameters, evaluation)


def evaluate_paper_strategy_frontier(
    session: Session,
    *,
    strategy_version_id: UUID,
    parameter_values: Mapping[str, object],
    state: StrategyStateEnvelope | None,
    financial_position_state: FinancialPositionState,
    now: datetime,
    frontier: CurrentAnalyticalFrontier,
    strategy_repository: StrategyRepository,
    strategy_registry: StrategyRegistry,
    analytical_source: NativeM15Source,
    market_specification: MarketSpecification,
) -> StrategyEvaluation:
    """Evaluate one already-validated immutable analytical frontier.

    Runtime code reads and reserves a frontier before asking the Strategy to
    evaluate it.  This seam receives that exact object instead of reading the
    provider again, so the receipt cannot silently refer to a different bar
    than the durable runtime cycle.
    """
    _, _, evaluation = _evaluate_current_paper_strategy(
        session,
        strategy_version_id=strategy_version_id,
        parameter_values=parameter_values,
        state=state,
        financial_position_state=financial_position_state,
        now=now,
        strategy_repository=strategy_repository,
        strategy_registry=strategy_registry,
        analytical_source=analytical_source,
        market_specification=market_specification,
        frontier=frontier,
    )
    return evaluation


def evaluate_paper_strategy_frontier_receipt(
    session: Session,
    *,
    strategy_version_id: UUID,
    parameter_values: Mapping[str, object],
    state: StrategyStateEnvelope | None,
    financial_position_state: FinancialPositionState,
    now: datetime,
    frontier: CurrentAnalyticalFrontier,
    strategy_repository: StrategyRepository,
    strategy_registry: StrategyRegistry,
    analytical_source: NativeM15Source,
    market_specification: MarketSpecification,
) -> "PaperStrategyEvaluationReceipt":
    """Return a verified Strategy receipt for an exact reserved frontier."""
    version, parameters, evaluation = _evaluate_current_paper_strategy(
        session,
        strategy_version_id=strategy_version_id,
        parameter_values=parameter_values,
        state=state,
        financial_position_state=financial_position_state,
        now=now,
        strategy_repository=strategy_repository,
        strategy_registry=strategy_registry,
        analytical_source=analytical_source,
        market_specification=market_specification,
        frontier=frontier,
    )
    from .persistence_contracts import PaperStrategyEvaluationReceipt

    return PaperStrategyEvaluationReceipt.from_verified(version, parameters, evaluation)


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


def _evaluate_current_paper_strategy(
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
    frontier: CurrentAnalyticalFrontier | None = None,
) -> tuple[StrategyVersion, ValidatedParameterPayload, StrategyEvaluation]:
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
    if frontier is None:
        frontier = load_current_analytical_frontier(
            analytical_source,
            now=now,
            warm_up_m15_bars=warm_up_bars,
        )
    else:
        _validate_supplied_frontier(frontier, now=now)
        if len(frontier.context_bars) < warm_up_bars + 1:
            raise PaperStrategyEvaluationError(
                "supplied analytical frontier does not contain required context"
            )
        if (
            state is not None
            and state.last_evaluated_bar_end is not None
            and state.last_evaluated_bar_end >= frontier.current_frontier
        ):
            raise PaperStrategyEvaluationError(
                "supplied analytical frontier does not advance Strategy state"
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

    evaluation = evaluate_strategy(
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
    return version, parameters, evaluation


def _validate_supplied_frontier(
    frontier: CurrentAnalyticalFrontier, *, now: datetime
) -> None:
    """Guard the explicit handoff from runtime data acquisition to Strategy."""
    if type(frontier) is not CurrentAnalyticalFrontier:
        raise PaperStrategyEvaluationError("frontier must be CurrentAnalyticalFrontier")
    if (
        type(now) is not datetime
        or now.tzinfo is None
        or now.utcoffset() != timedelta(0)
    ):
        raise PaperStrategyEvaluationError("evaluation clock must be UTC")
    try:
        frontier.validate()
    except Exception as error:
        raise PaperStrategyEvaluationError(
            "supplied analytical frontier is invalid"
        ) from error
    if frontier.current_frontier > now.astimezone(UTC):
        raise PaperStrategyEvaluationError(
            "supplied analytical frontier is in the future"
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
    "evaluate_current_paper_strategy_receipt",
    "evaluate_paper_strategy_frontier",
    "evaluate_paper_strategy_frontier_receipt",
]
