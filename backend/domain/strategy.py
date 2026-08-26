"""Immutable, serializable primitives at the public Strategy boundary."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Any, cast
from uuid import UUID

from .market_data import (
    Bar,
    DomainError,
    InputError,
    Instrument,
    PriceComponent,
    Timeframe,
)


class ParameterError(InputError):
    pass


class StateError(DomainError):
    pass


class VersionError(DomainError):
    pass


class EvaluationError(DomainError):
    pass


class Direction(StrEnum):
    LONG = "LONG"
    SHORT = "SHORT"


class PositionState(StrEnum):
    FLAT = "FLAT"
    LONG = "LONG"
    SHORT = "SHORT"


class Action(StrEnum):
    NO_ACTION = "NO_ACTION"
    OPEN_LONG = "OPEN_LONG"
    OPEN_SHORT = "OPEN_SHORT"
    CLOSE_POSITION = "CLOSE_POSITION"
    UPDATE_PROTECTION = "UPDATE_PROTECTION"


class Phase(StrEnum):
    SEARCHING = "SEARCHING"
    REFERENCE_IDENTIFIED = "REFERENCE_IDENTIFIED"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    ARMED = "ARMED"


class TargetMethodology(StrEnum):
    R_MULTIPLE = "R_MULTIPLE"


class EntryPolicy(StrEnum):
    IMMEDIATE = "IMMEDIATE"
    PRICE_TRIGGERED = "PRICE_TRIGGERED"


@dataclass(frozen=True, slots=True)
class CandleFacts:
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal

    def __post_init__(self) -> None:
        _utc(self.timestamp, "timestamp")
        for name in ("open", "high", "low", "close"):
            _dec(getattr(self, name), name)

    def to_json(self) -> dict[str, str]:
        return {"timestamp": self.timestamp.isoformat().replace("+00:00", "Z"), **{
            name: str(getattr(self, name)) for name in ("open", "high", "low", "close")
        }}


@dataclass(frozen=True, slots=True)
class SetupFacts:
    reference: CandleFacts
    sweep: CandleFacts
    confirmation: CandleFacts
    trend_relation: str
    atr: Decimal
    stop_price: Decimal
    trigger_price: Decimal

    def __post_init__(self) -> None:
        if any(type(value) is not CandleFacts for value in (self.reference, self.sweep, self.confirmation)):
            raise InputError("setup candle facts must be CandleFacts")
        if type(self.trend_relation) is not str or not self.trend_relation:
            raise InputError("trend_relation must be a non-empty string")
        for name in ("atr", "stop_price", "trigger_price"):
            _dec(getattr(self, name), name)

    def to_json(self) -> dict[str, Any]:
        return {"reference": self.reference.to_json(), "sweep": self.sweep.to_json(),
                "confirmation": self.confirmation.to_json(), "trend_relation": self.trend_relation,
                "atr": str(self.atr), "stop_price": str(self.stop_price),
                "trigger_price": str(self.trigger_price)}


def _utc(value: datetime, name: str) -> datetime:
    if (
        type(value) is not datetime
        or value.tzinfo is None
        or value.utcoffset() != timedelta(0)
    ):
        raise InputError(f"{name} must be timezone-aware UTC")
    return value


def _dec(value: Decimal, name: str) -> Decimal:
    if type(value) is not Decimal:
        raise InputError(f"{name} must be a Decimal")
    if not value.is_finite():
        raise InputError(f"{name} must be finite")
    return value


@dataclass(frozen=True, slots=True)
class StrategyParameters:
    ema_period: int = 100
    atr_period: int = 14
    stop_buffer: Decimal = Decimal("0.5")
    target_r: Decimal = Decimal("1.7")
    expiry_window: int = 5

    def __post_init__(self) -> None:
        for name in ("ema_period", "atr_period", "expiry_window"):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ParameterError(f"{name} must be a positive integer")
        if self.expiry_window != 5:
            raise ParameterError("Phase 1 expiry_window is fixed at five received bars")
        for name in ("stop_buffer", "target_r"):
            try:
                value = _dec(getattr(self, name), name)
            except (TypeError, ValueError) as error:
                raise ParameterError(str(error)) from error
            if value <= 0:
                raise ParameterError(f"{name} must be positive")

    def to_json(self) -> dict[str, Any]:
        return {
            "ema_period": self.ema_period,
            "atr_period": self.atr_period,
            "stop_buffer": str(self.stop_buffer),
            "target_r": str(self.target_r),
            "expiry_window": self.expiry_window,
        }


@dataclass(frozen=True, slots=True)
class ParameterSchema:
    key: str
    label: str
    type: str
    default: int | str | None
    nullable: bool
    minimum: int | str | None
    maximum: int | str | None
    description: str
    allowed_values: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if any(
            type(value) is not str
            for value in (self.key, self.label, self.type, self.description)
        ):
            raise ParameterError("parameter descriptor text fields must be strings")
        if any(
            not value for value in (self.key, self.label, self.type, self.description)
        ):
            raise ParameterError("parameter descriptor text fields must not be empty")
        if type(self.nullable) is not bool or type(self.allowed_values) is not tuple:
            raise ParameterError("parameter descriptor fields have invalid types")
        if any(type(value) is not str for value in self.allowed_values):
            raise ParameterError("allowed_values must contain strings")
        if len(set(self.allowed_values)) != len(self.allowed_values):
            raise ParameterError("allowed_values must not contain duplicates")
        for name in ("default", "minimum", "maximum"):
            value = getattr(self, name)
            if value is not None and type(value) not in (int, str):
                raise ParameterError(f"{name} must be an explicit JSON primitive")

    def to_json(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "type": self.type,
            "default": self.default,
            "nullable": self.nullable,
            "min": self.minimum,
            "max": self.maximum,
            "description": self.description,
            "allowed_values": list(self.allowed_values),
        }


@dataclass(frozen=True, slots=True)
class StrategyContext:
    evaluation_time: datetime
    instrument: Instrument
    bars: tuple[Bar, ...]
    position: PositionState = PositionState.FLAT
    exposure_allowed: bool = True

    def __post_init__(self) -> None:
        if type(self.instrument) is not Instrument:
            raise InputError("instrument must be an Instrument")
        if type(self.bars) is not tuple or any(
            type(bar) is not Bar for bar in self.bars
        ):
            raise InputError("bars must be a tuple of Bar values")
        if type(self.position) is not PositionState:
            raise InputError("position must be a PositionState")
        _utc(self.evaluation_time, "evaluation_time")
        if type(self.exposure_allowed) is not bool:
            raise InputError("exposure_allowed must be bool")
        if any(
            bar.instrument is not self.instrument
            for bar in self.bars
        ):
            raise InputError("StrategyContext bars must match its instrument")
        for previous, current in zip(self.bars, self.bars[1:], strict=False):
            if current.start_time <= previous.start_time:
                raise InputError("bars must be strictly ordered and unique")
        if any(bar.end_time > self.evaluation_time for bar in self.bars):
            raise InputError("bars must end at or before evaluation_time")

    def to_json(self) -> dict[str, Any]:
        return {
            "evaluation_time": self.evaluation_time.isoformat().replace("+00:00", "Z"),
            "instrument": self.instrument.value,
            "bars": [bar.to_json() for bar in self.bars],
            "position": self.position.value,
            "exposure_allowed": self.exposure_allowed,
        }


@dataclass(frozen=True, slots=True)
class StopProposal:
    price: Decimal
    direction: Direction

    def __post_init__(self) -> None:
        try:
            _dec(self.price, "price")
        except (TypeError, ValueError) as error:
            raise InputError(str(error)) from error
        if type(self.direction) is not Direction:
            raise InputError("direction must be a Direction")

    def to_json(self) -> dict[str, str]:
        return {"price": str(self.price), "direction": self.direction.value}


@dataclass(frozen=True, slots=True)
class TargetProposal:
    methodology: TargetMethodology = TargetMethodology.R_MULTIPLE
    multiple: Decimal = Decimal("1.7")

    def __post_init__(self) -> None:
        if type(self.methodology) is not TargetMethodology:
            raise InputError("methodology must be a TargetMethodology")
        try:
            multiple = _dec(self.multiple, "multiple")
        except (TypeError, ValueError) as error:
            raise InputError(str(error)) from error
        if self.methodology is not TargetMethodology.R_MULTIPLE or multiple <= 0:
            raise InputError("target must be a positive R_MULTIPLE")

    def resolve(self, entry: Decimal, stop: Decimal, direction: Direction) -> Decimal:
        if type(direction) is not Direction:
            raise InputError("direction must be a Direction")
        _dec(entry, "entry")
        _dec(stop, "stop")
        risk = abs(entry - stop)
        if risk <= 0:
            raise InputError("entry and stop must define positive risk")
        return (
            entry + self.multiple * risk
            if direction is Direction.LONG
            else entry - self.multiple * risk
        )

    def to_json(self) -> dict[str, str]:
        return {"methodology": self.methodology.value, "multiple": str(self.multiple)}


@dataclass(frozen=True, slots=True)
class Rationale:
    reason_code: str
    fields: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if type(self.reason_code) is not str or type(self.fields) is not tuple:
            raise InputError("rationale must contain strict immutable fields")
        if not self.reason_code:
            raise InputError("rationale reason_code must not be empty")
        if any(
            type(item) is not tuple
            or len(item) != 2
            or type(item[0]) is not str
            or type(item[1]) is not str
            for item in self.fields
        ):
            raise InputError("rationale fields must be string pairs")
        keys = [item[0] for item in self.fields]
        if len(set(keys)) != len(keys):
            raise InputError("rationale fields must not contain duplicate keys")

    def to_json(self) -> dict[str, Any]:
        return {"reason_code": self.reason_code, "fields": dict(self.fields)}


@dataclass(frozen=True, slots=True)
class StrategyDecision:
    action: Action
    rationale: Rationale
    direction: Direction | None = None
    decision_time: datetime | None = None
    stop: StopProposal | None = None
    target: TargetProposal | None = None
    entry_policy: EntryPolicy = EntryPolicy.IMMEDIATE
    trigger_price: Decimal | None = None
    trigger_price_basis: PriceComponent | None = None
    expiry_time: datetime | None = None
    expiry_bars: int | None = None
    setup_facts: SetupFacts | None = None

    def __post_init__(self) -> None:
        if type(self.action) is not Action:
            raise InputError("action must be an Action")
        if type(self.rationale) is not Rationale:
            raise InputError("rationale must be a Rationale")
        if self.direction is not None and type(self.direction) is not Direction:
            raise InputError("direction must be a Direction")
        if self.stop is not None and type(self.stop) is not StopProposal:
            raise InputError("stop must be a StopProposal")
        if self.target is not None and type(self.target) is not TargetProposal:
            raise InputError("target must be a TargetProposal")
        if type(self.entry_policy) is not EntryPolicy:
            raise InputError("entry_policy must be an EntryPolicy")
        if self.trigger_price is not None:
            _dec(self.trigger_price, "trigger_price")
        if self.trigger_price_basis is not None and type(self.trigger_price_basis) is not PriceComponent:
            raise InputError("trigger_price_basis must be a PriceComponent")
        if self.expiry_time is not None:
            _utc(self.expiry_time, "expiry_time")
        if self.expiry_bars is not None and (type(self.expiry_bars) is not int or self.expiry_bars <= 0):
            raise InputError("expiry_bars must be a positive integer")
        if self.setup_facts is not None and type(self.setup_facts) is not SetupFacts:
            raise InputError("setup_facts must be SetupFacts")
        if self.decision_time is not None:
            _utc(self.decision_time, "decision_time")
        opening = self.action in (Action.OPEN_LONG, Action.OPEN_SHORT)
        if opening:
            if self.decision_time is None:
                raise InputError("OPEN decisions require a UTC decision time")
            if self.direction is None or self.stop is None or self.target is None:
                raise InputError("OPEN decisions require direction, stop, and target")
            expected = (
                Direction.LONG if self.action is Action.OPEN_LONG else Direction.SHORT
            )
            if self.direction is not expected or self.stop.direction is not expected:
                raise InputError(
                    "OPEN action, direction, and stop direction must match"
                )
            if self.entry_policy is EntryPolicy.IMMEDIATE and any(
                value is not None for value in (self.trigger_price, self.trigger_price_basis, self.expiry_time, self.expiry_bars)
            ):
                raise InputError("immediate entries cannot contain trigger or expiry fields")
            if self.entry_policy is EntryPolicy.PRICE_TRIGGERED:
                if self.trigger_price is None or self.trigger_price_basis is None or self.expiry_time is None or self.expiry_bars is None:
                    raise InputError("price-triggered entries require trigger and expiry fields")
                expected_basis = PriceComponent.ASK if self.direction is Direction.LONG else PriceComponent.BID
                if self.trigger_price_basis is not expected_basis:
                    raise InputError("trigger price basis must match direction")
                if self.expiry_time <= self.decision_time:
                    raise InputError("expiry must be after decision time")
        elif (
            self.direction is not None
            or self.stop is not None
            or self.target is not None
        ):
            raise InputError("non-opening decisions cannot contain opening geometry")

    def to_json(self) -> dict[str, Any]:
        return {
            "action": self.action.value,
            "direction": self.direction.value if self.direction else None,
            "decision_time": self.decision_time.isoformat().replace("+00:00", "Z")
            if self.decision_time
            else None,
            "stop": self.stop.to_json() if self.stop else None,
            "target": self.target.to_json() if self.target else None,
            "entry_policy": self.entry_policy.value,
            "trigger_price": str(self.trigger_price) if self.trigger_price is not None else None,
            "trigger_price_basis": self.trigger_price_basis.value if self.trigger_price_basis else None,
            "expiry_time": self.expiry_time.isoformat().replace("+00:00", "Z") if self.expiry_time else None,
            "expiry_bars": self.expiry_bars,
            "setup_facts": self.setup_facts.to_json() if self.setup_facts else None,
            "rationale": self.rationale.to_json(),
        }


@dataclass(frozen=True, slots=True)
class StrategyState:
    schema_version: int = 1
    phase: Phase = Phase.SEARCHING
    direction: Direction | None = None
    reference_high: Decimal | None = None
    reference_low: Decimal | None = None
    reference_time: datetime | None = None
    sweep_time: datetime | None = None
    window_bars: int = 0
    watch_bars: int = 0
    confirmation_time: datetime | None = None
    trigger_price: Decimal | None = None
    last_evaluated_bar_end: datetime | None = None

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or type(self.window_bars) is not int or type(self.watch_bars) is not int:
            raise StateError("schema_version and window_bars must be integers")
        if self.schema_version != 1 or not 0 <= self.window_bars <= 5 or not 0 <= self.watch_bars <= 5:
            raise StateError("unsupported schema or window count")
        if type(self.phase) is not Phase:
            raise StateError("phase must be a Phase")
        if self.direction is not None and type(self.direction) is not Direction:
            raise StateError("direction must be a Direction")
        for name in ("reference_high", "reference_low"):
            value = getattr(self, name)
            if value is not None:
                try:
                    _dec(value, name)
                except (TypeError, ValueError) as error:
                    raise StateError(str(error)) from error
        for name in ("reference_time", "sweep_time", "confirmation_time", "last_evaluated_bar_end"):
            value = getattr(self, name)
            if value is not None:
                try:
                    _utc(value, name)
                except (TypeError, ValueError) as error:
                    raise StateError(str(error)) from error
        if self.trigger_price is not None:
            try:
                _dec(self.trigger_price, "trigger_price")
            except (TypeError, ValueError) as error:
                raise StateError(str(error)) from error
        active = self.phase is not Phase.SEARCHING
        if active != (
            self.reference_high is not None
            and self.reference_low is not None
            and self.reference_time is not None
        ):
            raise StateError("reference fields do not match phase")
        if active and self.direction is None:
            raise StateError("active state requires a direction")
        if self.phase is Phase.SEARCHING and (
            self.direction is not None
            or self.sweep_time is not None
            or self.window_bars or self.watch_bars
            or self.confirmation_time is not None or self.trigger_price is not None
        ):
            raise StateError("searching state contains setup fields")
        if self.phase is Phase.REFERENCE_IDENTIFIED and self.sweep_time is not None:
            raise StateError("reference phase cannot have a sweep")
        if self.phase is Phase.AWAITING_CONFIRMATION and (
            self.sweep_time is None or self.window_bars == 0
        ):
            raise StateError("awaiting confirmation requires a sweep")
        if self.phase is Phase.ARMED and (
            self.confirmation_time is None or self.trigger_price is None or self.watch_bars > 5
        ):
            raise StateError("armed state requires confirmation and trigger")
        if self.phase is not Phase.ARMED and (self.confirmation_time is not None or self.trigger_price is not None or self.watch_bars):
            raise StateError("watch fields require armed state")

    @classmethod
    def from_json(cls, value: Mapping[str, Any]) -> "StrategyState":
        required = {
            "schema_version",
            "phase",
            "direction",
            "reference_high",
            "reference_low",
            "reference_time",
            "sweep_time",
            "window_bars",
            "watch_bars",
            "confirmation_time",
            "trigger_price",
            "last_evaluated_bar_end",
        }
        if type(value) is not dict:
            raise StateError("state JSON must contain exactly the state fields")
        payload = cast(dict[str, Any], value)
        if set(payload) != required:
            raise StateError("state JSON must contain exactly the state fields")

        def decimal(name: str) -> Decimal | None:
            raw: Any = payload[name]
            if raw is None:
                return None
            if type(raw) is not str:
                raise StateError(f"{name} must be a Decimal string")
            try:
                return Decimal(raw)
            except Exception as error:
                raise StateError(f"invalid Decimal in {name}") from error

        def timestamp(name: str) -> datetime | None:
            raw: Any = payload[name]
            if raw is None:
                return None
            if type(raw) is not str:
                raise StateError(f"{name} must be an ISO timestamp")
            try:
                return datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError as error:
                raise StateError(f"invalid timestamp in {name}") from error

        try:
            phase = Phase(payload["phase"])
            direction = (
                Direction(payload["direction"])
                if payload["direction"] is not None
                else None
            )
        except (TypeError, ValueError) as error:
            raise StateError("invalid state enum") from error
        try:
            return cls(
                schema_version=payload["schema_version"],
                phase=phase,
                direction=direction,
                reference_high=decimal("reference_high"),
                reference_low=decimal("reference_low"),
                reference_time=timestamp("reference_time"),
                sweep_time=timestamp("sweep_time"),
                window_bars=payload["window_bars"],
                watch_bars=payload["watch_bars"],
                confirmation_time=timestamp("confirmation_time"),
                trigger_price=decimal("trigger_price"),
                last_evaluated_bar_end=timestamp("last_evaluated_bar_end"),
            )
        except StateError:
            raise
        except (TypeError, ValueError) as error:
            raise StateError("invalid state envelope") from error

    def to_json(self) -> dict[str, Any]:
        def stamp(value: datetime | None) -> str | None:
            return value.isoformat().replace("+00:00", "Z") if value else None

        return {
            "schema_version": self.schema_version,
            "phase": self.phase.value,
            "direction": self.direction.value if self.direction else None,
            "reference_high": str(self.reference_high)
            if self.reference_high is not None
            else None,
            "reference_low": str(self.reference_low)
            if self.reference_low is not None
            else None,
            "reference_time": stamp(self.reference_time),
            "sweep_time": stamp(self.sweep_time),
            "window_bars": self.window_bars,
            "watch_bars": self.watch_bars,
            "confirmation_time": stamp(self.confirmation_time),
            "trigger_price": str(self.trigger_price) if self.trigger_price is not None else None,
            "last_evaluated_bar_end": stamp(self.last_evaluated_bar_end),
        }


@dataclass(frozen=True, slots=True)
class StrategyEvaluation:
    decision: StrategyDecision
    next_state: StrategyState

    def __post_init__(self) -> None:
        if (
            type(self.decision) is not StrategyDecision
            or type(self.next_state) is not StrategyState
        ):
            raise InputError("evaluation must contain a decision and state")

    def to_json(self) -> dict[str, Any]:
        return {
            "decision": self.decision.to_json(),
            "next_state": self.next_state.to_json(),
        }


@dataclass(frozen=True, slots=True)
class StrategyVersion:
    id: UUID
    strategy_key: str
    version_number: int
    source_fingerprint: str
    implementation_key: str
    parameter_schema: tuple[ParameterSchema, ...]
    primary_timeframe: Timeframe = Timeframe.M15
    required_historical_context_bars: int = 100
    state_schema_version: int = 1
    created_at: datetime = datetime.min.replace(tzinfo=UTC)

    @property
    def warm_up_bars(self) -> int:
        """Deprecated compatibility read; persistence uses the canonical name."""
        return self.required_historical_context_bars

    def __post_init__(self) -> None:
        if (
            type(self.id) is not UUID
            or type(self.strategy_key) is not str
            or type(self.implementation_key) is not str
            or type(self.source_fingerprint) is not str
        ):
            raise VersionError("version identity fields have invalid types")
        if (
            type(self.version_number) is not int
            or type(self.required_historical_context_bars) is not int
            or type(self.state_schema_version) is not int
        ):
            raise VersionError("version fields must be integers")
        if type(self.primary_timeframe) is not Timeframe:
            raise VersionError("primary_timeframe must be a Timeframe")
        if type(self.parameter_schema) is not tuple or any(
            type(item) is not ParameterSchema for item in self.parameter_schema
        ):
            raise VersionError("parameter_schema must be a tuple of descriptors")
        if (
            self.version_number <= 0
            or self.required_historical_context_bars < 0
            or self.state_schema_version <= 0
        ):
            raise VersionError(
                "version numbers must be positive and historical context nonnegative"
            )
        if (
            len(self.source_fingerprint) != 64
            or self.source_fingerprint != self.source_fingerprint.lower()
        ):
            raise VersionError("source fingerprint must be lowercase SHA-256")
        if any(
            character not in "0123456789abcdef" for character in self.source_fingerprint
        ):
            raise VersionError("source fingerprint must be hexadecimal")
        try:
            _utc(self.created_at, "created_at")
        except (TypeError, ValueError) as error:
            raise VersionError(str(error)) from error

    def to_json(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "strategy_key": self.strategy_key,
            "version_number": self.version_number,
            "source_fingerprint": self.source_fingerprint,
            "implementation_key": self.implementation_key,
            "parameter_schema": [item.to_json() for item in self.parameter_schema],
            "primary_timeframe": self.primary_timeframe.value,
            "required_historical_context_bars": self.required_historical_context_bars,
            "state_schema_version": self.state_schema_version,
            "created_at": self.created_at.isoformat().replace("+00:00", "Z"),
        }
