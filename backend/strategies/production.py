"""Explicit production Strategy composition.

Source files are archived exactly once while composing the process. Evaluation
uses the resulting immutable registry and never performs filesystem discovery.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from backend.domain.strategy import (
    Action,
    Direction,
    EntryPolicy,
    ParameterError,
    PendingEntryHandoff,
    Phase,
    StateError,
    StrategyContext,
    StrategyEvaluation,
    StrategyParameters,
    StrategyParameterSet,
    StrategyState,
    StrategyStateEnvelope,
    StrategyStatePayloadDocument,
    ValidatedParameterPayload,
)

from .candle_confirmation_break import CandleConfirmationBreakStrategy
from .contract import StrategyRegistration
from .ema_sweep_confirmation_break import EmaSweepConfirmationBreakStrategy
from .registry import StrategyRegistry


class EmaSweepConfirmationBreakCompatibilityAdaptor:
    """Compose the generic boundary around the frozen legacy EMA source."""

    definition = EmaSweepConfirmationBreakStrategy.definition
    _codec_key = "ema_sweep_confirmation_break.v2"
    _payload_version = 1
    _state_keys = tuple(
        sorted(
            (
                "direction",
                "reference_high",
                "reference_low",
                "reference_time",
                "sweep_time",
                "phase",
                "window_bars",
                "watch_bars",
                "confirmation_time",
                "trigger_price",
            )
        )
    )

    def __init__(self) -> None:
        self._implementation = EmaSweepConfirmationBreakStrategy()

    @classmethod
    def initial_state(cls) -> StrategyStateEnvelope:
        return StrategyStateEnvelope(
            state_schema_version=cls.definition.state_schema_version,
            last_evaluated_bar_end=None,
            payload=StrategyStatePayloadDocument.from_mapping(
                cls._codec_key, cls._payload_version, cls._empty_fields()
            ),
        )

    @classmethod
    def _empty_fields(cls) -> dict[str, str | int | bool | None | datetime]:
        return {
            "phase": Phase.SEARCHING.value,
            "direction": None,
            "reference_high": None,
            "reference_low": None,
            "reference_time": None,
            "sweep_time": None,
            "window_bars": 0,
            "watch_bars": 0,
            "confirmation_time": None,
            "trigger_price": None,
        }

    @staticmethod
    def _optional_text(value: object, name: str) -> str | None:
        if value is not None and type(value) is not str:
            raise StateError(f"EMA state {name} must be a string or null")
        return value

    @staticmethod
    def _optional_timestamp(value: object, name: str) -> datetime | None:
        if value is None:
            return None
        if type(value) is datetime:
            timestamp = value
        elif type(value) is str:
            try:
                timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as error:
                raise StateError(
                    f"EMA state {name} must be a UTC timestamp or null"
                ) from error
        else:
            raise StateError(f"EMA state {name} must be a UTC timestamp or null")
        if timestamp.tzinfo is None or timestamp.utcoffset() != timedelta(0):
            raise StateError(f"EMA state {name} must be a UTC timestamp or null")
        return timestamp.astimezone(UTC)

    @staticmethod
    def _optional_decimal(value: object, name: str) -> Decimal | None:
        if value is None:
            return None
        if type(value) is not str:
            raise StateError(f"EMA state {name} must be a decimal string or null")
        try:
            return Decimal(value)
        except ArithmeticError as error:
            raise StateError(f"EMA state {name} is not a decimal") from error

    @classmethod
    def _legacy_state(cls, envelope: StrategyStateEnvelope) -> StrategyState:
        if envelope.state_schema_version != cls.definition.state_schema_version:
            raise StateError("EMA state schema version does not match Strategy")
        payload = envelope.payload
        if payload.codec_key != cls._codec_key:
            raise StateError("EMA state codec does not match Strategy")
        if payload.payload_version != cls._payload_version:
            raise StateError("EMA state payload version does not match Strategy")
        if tuple(key for key, _ in payload.fields) != cls._state_keys:
            raise StateError("EMA state payload fields do not match Strategy")

        raw_phase = payload.get("phase")
        raw_direction = payload.get("direction")
        raw_reference_high = payload.get("reference_high")
        raw_reference_low = payload.get("reference_low")
        raw_trigger = payload.get("trigger_price")
        raw_window = payload.get("window_bars")
        raw_watch = payload.get("watch_bars")
        if type(raw_phase) is not str:
            raise StateError("EMA state phase is invalid")
        if raw_direction is not None and type(raw_direction) is not str:
            raise StateError("EMA state direction is invalid")
        try:
            phase = Phase(raw_phase)
            direction = (
                Direction(raw_direction)
                if raw_direction is not None
                else None
            )
        except (TypeError, ValueError) as error:
            raise StateError("EMA state enum is invalid") from error
        if type(raw_window) is not int or type(raw_watch) is not int:
            raise StateError("EMA state bar counts are invalid")
        try:
            return StrategyState(
                schema_version=cls.definition.state_schema_version,
                phase=phase,
                direction=direction,
                reference_high=cls._optional_decimal(
                    raw_reference_high, "reference_high"
                ),
                reference_low=cls._optional_decimal(raw_reference_low, "reference_low"),
                reference_time=cls._optional_timestamp(
                    payload.get("reference_time"), "reference_time"
                ),
                sweep_time=cls._optional_timestamp(
                    payload.get("sweep_time"), "sweep_time"
                ),
                window_bars=raw_window,
                watch_bars=raw_watch,
                confirmation_time=cls._optional_timestamp(
                    payload.get("confirmation_time"), "confirmation_time"
                ),
                trigger_price=cls._optional_decimal(raw_trigger, "trigger_price"),
                last_evaluated_bar_end=envelope.last_evaluated_bar_end,
            )
        except (ArithmeticError, TypeError, ValueError) as error:
            raise StateError("EMA state payload contains invalid values") from error

    @classmethod
    def _envelope(
        cls,
        state: StrategyState,
        pending: PendingEntryHandoff | None,
        exposure_allowed: bool,
    ) -> StrategyStateEnvelope:
        fields: dict[str, str | int | bool | None | datetime] = {
            "phase": state.phase.value,
            "direction": state.direction.value if state.direction else None,
            "reference_high": (
                str(state.reference_high) if state.reference_high is not None else None
            ),
            "reference_low": (
                str(state.reference_low) if state.reference_low is not None else None
            ),
            "reference_time": state.reference_time,
            "sweep_time": state.sweep_time,
            "window_bars": state.window_bars,
            "watch_bars": state.watch_bars,
            "confirmation_time": state.confirmation_time,
            "trigger_price": (
                str(state.trigger_price) if state.trigger_price is not None else None
            ),
        }
        return StrategyStateEnvelope(
            state_schema_version=cls.definition.state_schema_version,
            last_evaluated_bar_end=state.last_evaluated_bar_end,
            payload=StrategyStatePayloadDocument.from_mapping(
                cls._codec_key, cls._payload_version, fields
            ),
            pending_entry=pending,
            exposure_allowed=exposure_allowed,
        )

    @classmethod
    def _pending_for_state(
        cls,
        state: StrategyState,
        pending: PendingEntryHandoff | None,
    ) -> PendingEntryHandoff | None:
        if state.phase is not Phase.ARMED:
            if pending is not None:
                raise StateError("EMA pending handoff requires an armed state")
            return None
        if (
            state.direction is None
            or state.trigger_price is None
            or state.confirmation_time is None
        ):
            raise StateError("EMA armed state cannot produce a pending handoff")
        if pending is None:
            raise StateError(
                "EMA armed state is missing its persisted stop methodology"
            )
        if (
            pending.direction is not state.direction
            or pending.trigger_price != state.trigger_price
            or pending.decision_frontier != state.confirmation_time
            or pending.eligibility_limit != 5
            or pending.consumed_count != state.watch_bars
        ):
            raise StateError("EMA pending handoff is inconsistent with state")
        return pending

    @classmethod
    def parse_parameters(
        cls, payload: ValidatedParameterPayload
    ) -> StrategyParameters:
        if type(payload) is not ValidatedParameterPayload:
            raise ParameterError("EMA parameters require a validated payload")
        ema_period = payload.get("ema_period")
        atr_period = payload.get("atr_period")
        stop_buffer = payload.get("stop_buffer")
        target_r = payload.get("target_r")
        expiry_window = payload.get("expiry_window")
        if (
            type(ema_period) is not int
            or type(atr_period) is not int
            or type(stop_buffer) is not str
            or type(target_r) is not str
            or type(expiry_window) is not int
        ):
            raise ParameterError("EMA parameter payload has invalid primitive values")
        parameters = StrategyParameters(
            ema_period=ema_period,
            atr_period=atr_period,
            stop_buffer=Decimal(stop_buffer),
            target_r=Decimal(target_r),
            expiry_window=expiry_window,
        )
        return parameters

    def evaluate(
        self,
        context: StrategyContext,
        parameters: StrategyParameterSet,
        state: StrategyStateEnvelope,
    ) -> StrategyEvaluation:
        if type(parameters) is not StrategyParameters:
            raise ParameterError("EMA Strategy requires its compatibility parameters")
        if type(state) is not StrategyStateEnvelope:
            raise StateError("EMA Strategy requires StrategyStateEnvelope")
        legacy_state = self._legacy_state(state)
        pending = self._pending_for_state(legacy_state, state.pending_entry)
        result = self._implementation.evaluate(context, parameters, legacy_state)
        if result.decision.action in (Action.OPEN_LONG, Action.OPEN_SHORT):
            decision = result.decision
            if (
                decision.entry_policy is not EntryPolicy.PRICE_TRIGGERED
                or decision.direction is None
                or decision.trigger_price is None
                or decision.trigger_price_basis is None
                or decision.decision_time is None
                or decision.expiry_bars is None
                or decision.stop is None
            ):
                raise StateError("EMA opening decision has invalid handoff fields")
            pending = PendingEntryHandoff(
                policy=decision.entry_policy,
                direction=decision.direction,
                trigger_price=decision.trigger_price,
                trigger_price_basis=decision.trigger_price_basis,
                decision_frontier=decision.decision_time,
                decision_time=decision.decision_time,
                eligibility_limit=decision.expiry_bars,
                stop_price=decision.stop.price,
                stop_methodology=(
                    decision.setup_facts.stop_methodology
                    if decision.setup_facts is not None
                    else "confirmation_extreme ± (stop_buffer × ATR14)"
                ),
            )
        elif result.next_state.phase is not Phase.ARMED:
            pending = None
        return StrategyEvaluation(
            result.decision,
            self._envelope(result.next_state, pending, context.exposure_allowed),
        )


def create_production_strategy_registry(root: Path | None = None) -> StrategyRegistry:
    repository_root = root or Path(__file__).resolve().parents[2]
    registry = StrategyRegistry()
    registry.register(
        StrategyRegistration(
            EmaSweepConfirmationBreakStrategy.definition,
            EmaSweepConfirmationBreakCompatibilityAdaptor(),
        ),
        repository_root,
    )
    registry.register(
        StrategyRegistration(
            CandleConfirmationBreakStrategy.definition,
            CandleConfirmationBreakStrategy(),
        ),
        repository_root,
    )
    return registry


__all__ = [
    "EmaSweepConfirmationBreakCompatibilityAdaptor",
    "create_production_strategy_registry",
]
