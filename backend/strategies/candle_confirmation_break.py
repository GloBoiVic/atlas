"""Candle Confirmation Break v1: a small, immediate-entry Strategy candidate."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast

from backend.domain.market_data import Bar
from backend.domain.strategy import (
    Action,
    Direction,
    EntryPolicy,
    ParameterError,
    ParameterSchema,
    PositionState,
    Rationale,
    StateError,
    StopProposal,
    StrategyContext,
    StrategyDecision,
    StrategyEvaluation,
    StrategyEvidence,
    StrategyParameterSet,
    StrategyStateEnvelope,
    StrategyStatePayloadDocument,
    TargetProposal,
    ValidatedParameterPayload,
)

from .contract import StrategyDefinition

CANDLE_CONFIRMATION_BREAK_EVIDENCE_SCHEMA = (
    "CANDLE_CONFIRMATION_BREAK_EVIDENCE_V1"
)
CANDLE_CONFIRMATION_BREAK_STATE_CODEC = "candle_confirmation_break.v1"
CANDLE_CONFIRMATION_BREAK_STATE_VERSION = 1
_STATE_KEYS = ("candidate_direction", "confirmation_count", "candidate_started_at")


DEFINITION = StrategyDefinition(
    strategy_key="candle_confirmation_break",
    name="Candle Confirmation Break",
    description="EUR/USD MID 15m consecutive candle confirmation break.",
    parameter_schema=(
        ParameterSchema(
            "confirmation_bars",
            "Confirmation bars",
            "integer",
            2,
            False,
            1,
            3,
            "Consecutive same-direction breaks required for entry",
        ),
        ParameterSchema(
            "stop_buffer_pips",
            "Stop buffer (pips)",
            "decimal",
            "20",
            False,
            "1",
            "100",
            "Absolute stop buffer in pips",
        ),
        ParameterSchema(
            "target_r",
            "Target R",
            "decimal",
            "1.5",
            False,
            "0.5",
            "5.0",
            "Target risk multiple",
        ),
    ),
    capabilities=("LONG", "SHORT", "STOP_LOSS", "TAKE_PROFIT"),
    required_historical_context_bars=1,
    state_schema_version=1,
    source_files=("backend/strategies/candle_confirmation_break.py",),
    implementation_key="candle_confirmation_break.v1",
)


@dataclass(frozen=True, slots=True)
class CandleConfirmationParameters:
    """Typed candidate parameters produced by the shared schema validator."""

    confirmation_bars: int
    stop_buffer_pips: Decimal
    target_r: Decimal

    def __post_init__(self) -> None:
        if type(self.confirmation_bars) is not int:
            raise ParameterError("confirmation_bars must be an integer")
        for name in ("stop_buffer_pips", "target_r"):
            value = getattr(self, name)
            if type(value) is not Decimal or not value.is_finite():
                raise ParameterError(f"{name} must be a finite Decimal")

    def to_json(self) -> dict[str, int | str]:
        return {
            "confirmation_bars": self.confirmation_bars,
            "stop_buffer_pips": str(self.stop_buffer_pips),
            "target_r": str(self.target_r),
        }


def _empty_payload() -> StrategyStatePayloadDocument:
    return StrategyStatePayloadDocument.from_mapping(
        CANDLE_CONFIRMATION_BREAK_STATE_CODEC,
        CANDLE_CONFIRMATION_BREAK_STATE_VERSION,
        {
            "candidate_direction": None,
            "confirmation_count": 0,
            "candidate_started_at": None,
        },
    )


def _empty_state(
    frontier: datetime | None = None, *, exposure_allowed: bool = True
) -> StrategyStateEnvelope:
    return StrategyStateEnvelope(
        DEFINITION.state_schema_version,
        frontier,
        _empty_payload(),
        pending_entry=None,
        exposure_allowed=exposure_allowed,
    )


def _utc_timestamp(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        timestamp = value
    elif type(value) is str:
        try:
            timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise StateError("candidate_started_at must be a UTC timestamp") from error
    else:
        raise StateError("candidate_started_at must be a UTC timestamp")
    if timestamp.tzinfo is None or timestamp.utcoffset() != UTC.utcoffset(timestamp):
        raise StateError("candidate_started_at must be a UTC timestamp")
    return timestamp


def _state_values(
    state: StrategyStateEnvelope,
    evaluation_time: datetime,
) -> tuple[Direction | None, int, datetime | None]:
    if state.state_schema_version != DEFINITION.state_schema_version:
        raise StateError("candidate state schema version does not match Strategy")
    payload = state.payload
    if payload.codec_key != CANDLE_CONFIRMATION_BREAK_STATE_CODEC:
        raise StateError("candidate state codec does not match Strategy")
    if payload.payload_version != CANDLE_CONFIRMATION_BREAK_STATE_VERSION:
        raise StateError("candidate state payload version does not match Strategy")
    if tuple(key for key, _ in payload.fields) != tuple(sorted(_STATE_KEYS)):
        raise StateError("candidate state payload fields do not match Strategy")

    raw_direction = payload.get("candidate_direction")
    if raw_direction is not None and type(raw_direction) is not str:
        raise StateError("candidate direction is invalid")
    try:
        direction = Direction(raw_direction) if raw_direction is not None else None
    except ValueError as error:
        raise StateError("candidate direction is invalid") from error
    raw_count = payload.get("confirmation_count")
    if type(raw_count) is not int or not 0 <= raw_count <= 3:
        raise StateError("candidate confirmation count is invalid")
    started_at = _utc_timestamp(payload.get("candidate_started_at"))
    if raw_count == 0 and (direction is not None or started_at is not None):
        raise StateError("empty candidate state contains methodology fields")
    if raw_count > 0 and (direction is None or started_at is None):
        raise StateError("candidate state direction and count do not match")
    if started_at is not None:
        if (
            state.last_evaluated_bar_end is not None
            and started_at > state.last_evaluated_bar_end
        ):
            raise StateError("candidate_started_at cannot be in the future")
        if started_at > evaluation_time:
            raise StateError("candidate_started_at cannot be in the future")
    return direction, raw_count, started_at


def _payload(
    direction: Direction | None, count: int, started_at: datetime | None
) -> StrategyStatePayloadDocument:
    return StrategyStatePayloadDocument.from_mapping(
        CANDLE_CONFIRMATION_BREAK_STATE_CODEC,
        CANDLE_CONFIRMATION_BREAK_STATE_VERSION,
        {
            "candidate_direction": direction.value if direction else None,
            "confirmation_count": count,
            "candidate_started_at": started_at,
        },
    )


def _state(
    frontier: datetime,
    direction: Direction | None,
    count: int,
    started_at: datetime | None,
    *,
    exposure_allowed: bool,
) -> StrategyStateEnvelope:
    return StrategyStateEnvelope(
        DEFINITION.state_schema_version,
        frontier,
        _payload(direction, count, started_at),
        pending_entry=None,
        exposure_allowed=exposure_allowed,
    )


class CandleConfirmationBreakStrategy:
    definition = DEFINITION

    @classmethod
    def initial_state(cls) -> StrategyStateEnvelope:
        return _empty_state()

    @classmethod
    def parse_parameters(
        cls, payload: ValidatedParameterPayload
    ) -> CandleConfirmationParameters:
        if type(payload) is not ValidatedParameterPayload:
            raise ParameterError("candle parameters require a validated payload")
        try:
            confirmation_bars = payload.get("confirmation_bars")
            stop_buffer_pips = payload.get("stop_buffer_pips")
            target_r = payload.get("target_r")
        except ParameterError:
            raise
        if (
            type(confirmation_bars) is not int
            or type(stop_buffer_pips) is not str
            or type(target_r) is not str
        ):
            raise ParameterError(
                "candle parameter payload has invalid primitive values"
            )
        return CandleConfirmationParameters(
            confirmation_bars,
            Decimal(stop_buffer_pips),
            Decimal(target_r),
        )

    def evaluate(
        self,
        context: StrategyContext,
        parameters: StrategyParameterSet,
        state: StrategyStateEnvelope,
    ) -> StrategyEvaluation:
        if type(parameters) is not CandleConfirmationParameters:
            raise ParameterError(
                "candle Strategy requires CandleConfirmationParameters"
            )
        typed_parameters = cast(CandleConfirmationParameters, parameters)
        try:
            values = cast(Mapping[str, object], typed_parameters.to_json())
            ValidatedParameterPayload.from_mapping(
                self.definition.parameter_schema, values
            )
        except Exception as error:
            raise ParameterError(
                "typed candle parameters fail the Strategy schema"
            ) from error
        if type(state) is not StrategyStateEnvelope:
            raise StateError("candle Strategy requires StrategyStateEnvelope")
        direction, count, started_at = _state_values(state, context.evaluation_time)
        current = context.bars[-1].end_time if context.bars else None

        if not context.exposure_allowed or context.position is not PositionState.FLAT:
            return StrategyEvaluation(
                StrategyDecision(Action.NO_ACTION, Rationale("EXPOSURE_NOT_ALLOWED")),
                _empty_state(current, exposure_allowed=context.exposure_allowed),
            )
        if not context.bars:
            return StrategyEvaluation(
                StrategyDecision(Action.NO_ACTION, Rationale("NO_COMPLETED_BAR")), state
            )

        new = tuple(
            bar
            for bar in context.bars
            if state.last_evaluated_bar_end is None
            or bar.end_time > state.last_evaluated_bar_end
        )
        if not new:
            return StrategyEvaluation(
                StrategyDecision(Action.NO_ACTION, Rationale("NO_NEW_BAR")), state
            )

        decision = StrategyDecision(Action.NO_ACTION, Rationale("CANDLE_NO_BREAK"))
        working_direction, working_count, working_started = direction, count, started_at
        for bar in new:
            index = context.bars.index(bar)
            if index == 0:
                working_direction, working_count, working_started = None, 0, None
                decision = StrategyDecision(
                    Action.NO_ACTION, Rationale("CANDLE_WARMING_UP")
                )
                continue

            prior = context.bars[index - 1]
            break_direction = self._break_direction(prior, bar)
            if break_direction is None:
                working_direction, working_count, working_started = None, 0, None
                decision = StrategyDecision(
                    Action.NO_ACTION, Rationale("CANDLE_NO_BREAK")
                )
                continue
            if break_direction is working_direction:
                working_count += 1
            else:
                working_direction, working_count, working_started = (
                    break_direction,
                    1,
                    bar.end_time,
                )
            if working_count >= typed_parameters.confirmation_bars:
                assert working_direction is not None
                return StrategyEvaluation(
                    self._opening_decision(
                        context,
                        prior,
                        bar,
                        working_direction,
                        working_count,
                        typed_parameters,
                    ),
                    _empty_state(
                        bar.end_time, exposure_allowed=context.exposure_allowed
                    ),
                )
            assert working_direction is not None
            decision = StrategyDecision(
                Action.NO_ACTION,
                Rationale(
                    "CANDLE_CONFIRMATION_CANDIDATE",
                    (
                        ("direction", working_direction.value),
                        ("count", str(working_count)),
                    ),
                ),
            )

        return StrategyEvaluation(
            decision,
            _state(
                new[-1].end_time,
                working_direction,
                working_count,
                working_started,
                exposure_allowed=context.exposure_allowed,
            ),
        )

    @staticmethod
    def _break_direction(prior: Bar, signal: Bar) -> Direction | None:
        if signal.close > signal.open and signal.close > prior.high:
            return Direction.LONG
        if signal.close < signal.open and signal.close < prior.low:
            return Direction.SHORT
        return None

    @staticmethod
    def _opening_decision(
        context: StrategyContext,
        prior: Bar,
        signal: Bar,
        direction: Direction,
        confirmation_count: int,
        parameters: CandleConfirmationParameters,
    ) -> StrategyDecision:
        assert context.market is not None
        stop = (
            signal.low - parameters.stop_buffer_pips * context.market.pip_size
            if direction is Direction.LONG
            else signal.high + parameters.stop_buffer_pips * context.market.pip_size
        )
        evidence = StrategyEvidence.from_mapping(
            CANDLE_CONFIRMATION_BREAK_EVIDENCE_SCHEMA,
            1,
            {
                "direction": direction.value,
                "prior_timestamp": prior.end_time,
                "prior_open": prior.open,
                "prior_high": prior.high,
                "prior_low": prior.low,
                "prior_close": prior.close,
                "signal_timestamp": signal.end_time,
                "signal_open": signal.open,
                "signal_high": signal.high,
                "signal_low": signal.low,
                "signal_close": signal.close,
                "confirmation_count": confirmation_count,
                "confirmation_bars": parameters.confirmation_bars,
                "pip_size": context.market.pip_size,
                "stop_buffer_pips": parameters.stop_buffer_pips,
                "proposed_stop": stop,
                "target_multiple": parameters.target_r,
            },
        )
        return StrategyDecision(
            Action.OPEN_LONG if direction is Direction.LONG else Action.OPEN_SHORT,
            Rationale(
                "CANDLE_CONFIRMATION_BREAK_CONFIRMED",
                (
                    ("direction", direction.value),
                    ("confirmation_count", str(confirmation_count)),
                ),
            ),
            direction=direction,
            decision_time=signal.end_time,
            stop=StopProposal(stop, direction),
            target=TargetProposal(multiple=parameters.target_r),
            entry_policy=EntryPolicy.IMMEDIATE,
            evidence=evidence,
        )


__all__ = [
    "CANDLE_CONFIRMATION_BREAK_EVIDENCE_SCHEMA",
    "CANDLE_CONFIRMATION_BREAK_STATE_CODEC",
    "CANDLE_CONFIRMATION_BREAK_STATE_VERSION",
    "CandleConfirmationBreakStrategy",
    "CandleConfirmationParameters",
    "DEFINITION",
]
