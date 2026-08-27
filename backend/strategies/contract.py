"""The pure public contract implemented by Atlas Strategies.

This module deliberately contains no discovery, persistence, configuration, or
runtime concerns.  ``evaluate_strategy`` is the single checked entry point for
callers which do not want to rely on an implementation's own validation.
"""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from backend.domain.market_data import InputError, Instrument, PriceComponent, Timeframe
from backend.domain.strategy import (
    EvaluationError,
    ParameterSchema,
    StrategyContext,
    StrategyEvaluation,
    StrategyParameters,
    StrategyState,
)


class StrategyContractError(InputError):
    """A Strategy or its supplied boundary values violate the contract."""


class DuplicateBarEvaluationError(StrategyContractError):
    """The supplied current bar has already crossed the state frontier."""


class StrategyEvaluationError(EvaluationError):
    """An implementation failed unexpectedly or returned an invalid result."""


@dataclass(frozen=True, slots=True)
class StrategyDefinition:
    """Immutable metadata advertised by one executable Strategy."""

    strategy_key: str
    name: str
    description: str
    parameter_schema: tuple[ParameterSchema, ...]
    primary_timeframe: Timeframe = Timeframe.M15
    context_timeframes: tuple[Timeframe, ...] = ()
    capabilities: tuple[str, ...] = ()
    required_historical_context_bars: int = 100
    state_schema_version: int = 1
    source_files: tuple[str, ...] = ()
    implementation_key: str = ""
    required_instrument: Instrument = Instrument.EUR_USD
    required_resolution: Timeframe = Timeframe.M15
    required_price_component: PriceComponent = PriceComponent.MID
    completed_only: bool = True

    @property
    def warm_up_bars(self) -> int:
        """Deprecated compatibility read for older runtime callers."""
        return self.required_historical_context_bars


@dataclass(frozen=True, slots=True)
class StrategyRegistration:
    """An explicit pairing of a definition and its local implementation."""

    definition: StrategyDefinition
    implementation: "Strategy"


@runtime_checkable
class Strategy(Protocol):
    """Pure Strategy interface shared by Experiment, PAPER, and LIVE."""

    definition: StrategyDefinition

    def evaluate(
        self,
        context: StrategyContext,
        parameters: StrategyParameters,
        state: StrategyState,
    ) -> StrategyEvaluation: ...


def _text(value: object, field: str) -> None:
    if type(value) is not str or not value:
        raise StrategyContractError(f"{field} must be a non-empty string")


def validate_registration(registration: StrategyRegistration) -> None:
    """Validate registration metadata without importing or executing code."""

    if type(registration) is not StrategyRegistration:
        raise StrategyContractError("registration must be a StrategyRegistration")
    definition = registration.definition
    if type(definition) is not StrategyDefinition:
        raise StrategyContractError("registration definition has an invalid type")
    _text(definition.strategy_key, "strategy_key")
    _text(definition.name, "name")
    _text(definition.description, "description")
    _text(definition.implementation_key, "implementation_key")
    if type(definition.parameter_schema) is not tuple or any(
        type(item) is not ParameterSchema for item in definition.parameter_schema
    ):
        raise StrategyContractError(
            "parameter_schema must contain ParameterSchema values"
        )
    keys = [item.key for item in definition.parameter_schema]
    if len(keys) != len(set(keys)):
        raise StrategyContractError("parameter_schema keys must be unique")
    if definition.primary_timeframe is not definition.required_resolution:
        raise StrategyContractError(
            "primary timeframe must match analytical resolution"
        )
    if definition.required_resolution is not Timeframe.M15:
        raise StrategyContractError("only 15m is supported")
    if (
        type(definition.context_timeframes) is not tuple
        or definition.context_timeframes
    ):
        raise StrategyContractError("Phase 1 does not support context timeframes")
    if type(definition.capabilities) is not tuple or any(
        type(value) is not str or not value for value in definition.capabilities
    ):
        raise StrategyContractError("capabilities must be a tuple of non-empty strings")
    if (
        type(definition.required_historical_context_bars) is not int
        or definition.required_historical_context_bars < 0
    ):
        raise StrategyContractError(
            "required_historical_context_bars must be a nonnegative integer"
        )
    if (
        type(definition.state_schema_version) is not int
        or definition.state_schema_version <= 0
    ):
        raise StrategyContractError("state_schema_version must be positive")
    if type(definition.source_files) is not tuple or any(
        (
            type(path) is not str
            or not path
            or path.startswith("/")
            or "\\" in path
            or any(part in ("", ".", "..") for part in path.split("/"))
            or not path.startswith("backend/")
        )
        for path in definition.source_files
    ):
        raise StrategyContractError(
            "source_files must be relative POSIX paths under backend/"
        )
    if len(set(definition.source_files)) != len(definition.source_files):
        raise StrategyContractError("source_files must not contain duplicates")
    if type(definition.required_instrument) is not Instrument:
        raise StrategyContractError("required_instrument must be an Instrument")
    if type(definition.required_resolution) is not Timeframe:
        raise StrategyContractError("required_resolution must be a Timeframe")
    if type(definition.required_price_component) is not PriceComponent:
        raise StrategyContractError("required_price_component must be a PriceComponent")
    if type(definition.completed_only) is not bool or not definition.completed_only:
        raise StrategyContractError("Strategies require completed-only analytical bars")
    implementation = registration.implementation
    if not callable(getattr(implementation, "evaluate", None)):
        raise StrategyContractError("implementation must implement Strategy")
    if getattr(implementation, "definition", None) != definition:
        raise StrategyContractError(
            "implementation definition does not match registration"
        )


def validate_strategy_contract(registration: StrategyRegistration) -> None:
    """Named contract-validation entry point for registry callers."""

    validate_registration(registration)


def validate_parameters(parameters: StrategyParameters) -> None:
    """Validate strict, typed runtime parameter values."""

    if type(parameters) is not StrategyParameters:
        raise StrategyContractError("parameters must be StrategyParameters")


def validate_state(state: StrategyState, definition: StrategyDefinition) -> None:
    """Validate state and its compatibility with the advertised schema."""

    if type(state) is not StrategyState:
        raise StrategyContractError("state must be StrategyState")
    if type(definition) is not StrategyDefinition:
        raise StrategyContractError("definition must be StrategyDefinition")
    if state.schema_version != definition.state_schema_version:
        raise StrategyContractError(
            "state schema version does not match Strategy definition"
        )


def validate_context(
    context: StrategyContext,
    state: StrategyState,
    definition: StrategyDefinition,
) -> None:
    """Validate the completed-bar frontier before an implementation runs."""

    if type(context) is not StrategyContext:
        raise StrategyContractError("context must be StrategyContext")
    validate_state(state, definition)
    if context.instrument is not definition.required_instrument:
        raise StrategyContractError("only EUR/USD is supported")
    if any(
        bar.timeframe is not definition.required_resolution
        or bar.instrument is not definition.required_instrument
        or bar.price_component is not definition.required_price_component
        for bar in context.bars
    ):
        raise StrategyContractError("strategy accepts only EUR/USD MID 15m bars")
    if context.exposure_allowed and len(context.bars) < definition.warm_up_bars:
        raise StrategyContractError("insufficient completed bars for Strategy warm-up")
    if state.last_evaluated_bar_end is not None and context.bars:
        current_end = context.bars[-1].end_time
        if current_end <= state.last_evaluated_bar_end:
            raise DuplicateBarEvaluationError(
                "completed bar is not newer than state frontier"
            )


def evaluate_strategy(
    implementation: Strategy,
    context: StrategyContext,
    parameters: StrategyParameters,
    state: StrategyState,
) -> StrategyEvaluation:
    """Run a Strategy after validation and normalize unexpected failures."""

    validate_registration(
        StrategyRegistration(implementation.definition, implementation)
    )
    validate_parameters(parameters)
    validate_context(context, state, implementation.definition)
    try:
        result = implementation.evaluate(context, parameters, state)
    except (StrategyContractError, EvaluationError, InputError):
        raise
    except Exception as error:
        raise StrategyEvaluationError(
            "Strategy evaluation failed unexpectedly"
        ) from error
    if type(result) is not StrategyEvaluation:
        raise StrategyEvaluationError("Strategy must return StrategyEvaluation")
    validate_state(result.next_state, implementation.definition)
    if (
        context.bars
        and result.next_state.last_evaluated_bar_end != context.bars[-1].end_time
    ):
        raise StrategyEvaluationError(
            "Strategy must advance its frontier to the current completed bar"
        )
    return result
