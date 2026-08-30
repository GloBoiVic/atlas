"""Immutable, serializable primitives at the public Strategy boundary."""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Any, Protocol, cast
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
    """Strategy phases, including read-only legacy schema compatibility."""

    SEARCHING = "SEARCHING"
    REFERENCE_IDENTIFIED = "REFERENCE_IDENTIFIED"
    # Legacy schema-1 state compatibility; the registered V2 Strategy never
    # emits or consumes this phase.
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    ARMED = "ARMED"


class TargetMethodology(StrEnum):
    R_MULTIPLE = "R_MULTIPLE"


class EntryPolicy(StrEnum):
    """Opening policies; IMMEDIATE remains supported by the current V2 path."""

    IMMEDIATE = "IMMEDIATE"
    PRICE_TRIGGERED = "PRICE_TRIGGERED"


@dataclass(frozen=True, slots=True)
class MarketSpecification:
    """Validated calculation facts supplied to a Strategy."""

    instrument: Instrument
    pip_size: Decimal

    def __post_init__(self) -> None:
        if type(self.instrument) is not Instrument:
            raise InputError("market instrument must be an Instrument")
        try:
            value = _dec(self.pip_size, "pip_size")
        except (TypeError, ValueError) as error:
            raise InputError(str(error)) from error
        if value <= 0:
            raise InputError("pip_size must be positive")

    def to_json(self) -> dict[str, str]:
        return {"instrument": self.instrument.value, "pip_size": str(self.pip_size)}


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
        return {
            "timestamp": self.timestamp.isoformat().replace("+00:00", "Z"),
            **{
                name: str(getattr(self, name))
                for name in ("open", "high", "low", "close")
            },
        }


@dataclass(frozen=True, slots=True)
class SetupFacts:
    reference: CandleFacts
    sweep: CandleFacts
    confirmation: CandleFacts
    trend_relation: str
    atr: Decimal
    stop_price: Decimal
    trigger_price: Decimal
    ema_at_reference: Decimal | None = None
    stop_methodology: str = "confirmation_extreme ± (stop_buffer × ATR14)"
    trigger_basis: str = "ASK for LONG / BID for SHORT"
    window_policy: str = (
        "W1-W5 received completed analytical bars; no wall-clock expiry"
    )
    evidence_version: str = "REFERENCE_STRATEGY_EVIDENCE_V2"
    same_candle_sweep_confirmation: bool = True

    def __post_init__(self) -> None:
        if any(
            type(value) is not CandleFacts
            for value in (self.reference, self.sweep, self.confirmation)
        ):
            raise InputError("setup candle facts must be CandleFacts")
        if type(self.trend_relation) is not str or not self.trend_relation:
            raise InputError("trend_relation must be a non-empty string")
        for name in ("atr", "stop_price", "trigger_price"):
            _dec(getattr(self, name), name)
        if self.ema_at_reference is not None:
            _dec(self.ema_at_reference, "ema_at_reference")
        if type(self.same_candle_sweep_confirmation) is not bool:
            raise InputError("same_candle_sweep_confirmation must be a bool")

    def to_json(self) -> dict[str, Any]:
        result = {
            "reference": self.reference.to_json(),
            "sweep": self.sweep.to_json(),
            "confirmation": self.confirmation.to_json(),
            "trend_relation": self.trend_relation,
            "ema_at_reference": str(self.ema_at_reference)
            if self.ema_at_reference is not None
            else None,
            "atr": str(self.atr),
            "stop_price": str(self.stop_price),
            "stop_methodology": self.stop_methodology,
            "trigger_price": str(self.trigger_price),
            "trigger_basis": self.trigger_basis,
            "window_policy": self.window_policy,
            "evidence_version": self.evidence_version,
            "same_candle_sweep_confirmation": self.same_candle_sweep_confirmation,
        }
        return result


EvidencePrimitive = str | int | bool | Decimal | datetime


@dataclass(frozen=True, slots=True)
class StrategyEvidence:
    """Opaque, bounded evidence owned by the producing Strategy."""

    schema_key: str
    version: int
    fields: tuple[tuple[str, EvidencePrimitive], ...] = ()

    def __post_init__(self) -> None:
        if type(self.schema_key) is not str or not self.schema_key:
            raise InputError("evidence schema_key must be a non-empty string")
        if (
            len(self.schema_key) > 64
            or type(self.version) is not int
            or self.version <= 0
        ):
            raise InputError("evidence schema or version is invalid")
        if type(self.fields) is not tuple or len(self.fields) > 32:
            raise InputError("evidence must contain at most 32 fields")
        keys: set[str] = set()
        for field in self.fields:
            if type(field) is not tuple or len(field) != 2:
                raise InputError("evidence fields must be key/value pairs")
            key, value = field
            if type(key) is not str or not key or len(key) > 64 or key in keys:
                raise InputError("evidence field keys must be unique and bounded")
            keys.add(key)
            if type(value) not in (str, int, bool, Decimal, datetime):
                raise InputError("evidence fields must be flat typed values")
            if type(value) is Decimal and not value.is_finite():
                raise InputError("evidence decimals must be finite")
            if type(value) is datetime:
                _utc(value, key)
            if type(value) is str and len(value) > 256:
                raise InputError("evidence strings must be at most 256 characters")
        if len(self.canonical_bytes) > 8192:
            raise InputError("evidence exceeds 8192 bytes")

    @classmethod
    def from_mapping(
        cls, schema_key: str, version: int, fields: Mapping[str, EvidencePrimitive]
    ) -> "StrategyEvidence":
        if type(fields) is not dict:
            raise InputError("evidence fields must be an object")
        typed_fields = cast(dict[str, EvidencePrimitive], fields)
        return cls(schema_key, version, tuple(typed_fields.items()))

    def _wire_value(self, value: EvidencePrimitive) -> str | int | bool:
        if type(value) is datetime:
            return value.isoformat().replace("+00:00", "Z")
        if type(value) is Decimal:
            return str(value)
        return cast(str | int | bool, value)

    def to_json(self) -> dict[str, Any]:
        return {
            "schema_key": self.schema_key,
            "version": self.version,
            "fields": {key: self._wire_value(value) for key, value in self.fields},
        }

    @property
    def canonical_bytes(self) -> bytes:
        return _canonical_json(self.to_json()).encode("utf-8")


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


class StrategyParameterSet(Protocol):
    """Typed, immutable values owned by an individual Strategy."""

    def to_json(self) -> dict[str, Any]: ...


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
        if len(self.key) > 64:
            raise ParameterError("parameter key must be at most 64 characters")
        if self.type not in {"integer", "decimal", "boolean", "string", "enum"}:
            raise ParameterError("unsupported parameter primitive type")
        if type(self.nullable) is not bool or type(self.allowed_values) is not tuple:
            raise ParameterError("parameter descriptor fields have invalid types")
        if any(type(value) is not str for value in self.allowed_values):
            raise ParameterError("allowed_values must contain strings")
        if len(set(self.allowed_values)) != len(self.allowed_values):
            raise ParameterError("allowed_values must not contain duplicates")
        for name in ("default", "minimum", "maximum"):
            value = getattr(self, name)
            if value is not None and type(value) not in (int, str, bool):
                raise ParameterError(f"{name} must be an explicit JSON primitive")
        if self.default is None and not self.nullable:
            raise ParameterError("non-nullable parameters require a default")
        if self.type == "integer":
            for name in ("default", "minimum", "maximum"):
                value = getattr(self, name)
                if value is not None and type(value) is not int:
                    raise ParameterError(f"{name} must be an integer")
        elif self.type == "decimal":
            for name in ("default", "minimum", "maximum"):
                value = getattr(self, name)
                if value is not None:
                    if type(value) is not str:
                        raise ParameterError(f"{name} must be a decimal string")
                    try:
                        decimal = Decimal(value)
                    except Exception as error:
                        raise ParameterError(
                            f"{name} must be a decimal string"
                        ) from error
                    if not decimal.is_finite():
                        raise ParameterError(f"{name} must be finite")
        elif self.type == "boolean":
            if self.allowed_values:
                raise ParameterError("boolean parameters cannot declare allowed values")
            if any(
                getattr(self, name) is not None
                and type(getattr(self, name)) is not bool
                for name in ("default", "minimum", "maximum")
            ):
                raise ParameterError("boolean bounds must be absent")
        else:
            if self.minimum is not None or self.maximum is not None:
                raise ParameterError("string parameters cannot declare numeric bounds")
            for name in ("default",):
                value = getattr(self, name)
                if value is not None and type(value) is not str:
                    raise ParameterError(f"{name} must be a string")
        if self.type == "enum" and not self.allowed_values:
            raise ParameterError("enum parameters require allowed values")
        if self.type != "enum" and self.allowed_values:
            raise ParameterError("allowed values require an enum parameter")
        if self.minimum is not None and self.maximum is not None:
            try:
                if Decimal(str(self.minimum)) > Decimal(str(self.maximum)):
                    raise ParameterError("minimum must not exceed maximum")
            except (ValueError, ArithmeticError) as error:
                raise ParameterError("parameter bounds must be comparable") from error
        if self.default is not None and self.type in {"integer", "decimal"}:
            try:
                default = Decimal(str(self.default))
            except (ValueError, ArithmeticError) as error:
                raise ParameterError("default and bounds must be comparable") from error
            if self.minimum is not None and default < Decimal(str(self.minimum)):
                raise ParameterError("default must not be below minimum")
            if self.maximum is not None and default > Decimal(str(self.maximum)):
                raise ParameterError("default must not exceed maximum")
        if (
            self.default is not None
            and self.allowed_values
            and self.default not in self.allowed_values
        ):
            raise ParameterError("default must be one of allowed values")

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

    @classmethod
    def from_json(cls, value: Mapping[str, Any]) -> "ParameterSchema":
        """Restore a persisted descriptor without Strategy-specific knowledge."""

        if type(value) is not dict:
            raise ParameterError("parameter descriptor must be an object")
        payload = cast(dict[str, object], value)
        required = {
            "key", "label", "type", "default", "nullable", "min", "max",
            "description", "allowed_values",
        }
        if set(payload) != required:
            raise ParameterError("parameter descriptor has unexpected fields")
        raw_allowed = payload["allowed_values"]
        if type(raw_allowed) is not list:
            raise ParameterError("allowed_values must be a list")
        raw_allowed_items = cast(list[object], raw_allowed)
        allowed_values: list[str] = []
        for item in raw_allowed_items:
            if type(item) is not str:
                raise ParameterError("allowed_values must contain strings")
            allowed_values.append(item)

        def primitive(name: str) -> int | str | bool | None:
            raw = payload[name]
            if raw is not None and type(raw) not in (int, str, bool):
                raise ParameterError(f"{name} must be an explicit JSON primitive")
            return cast(int | str | bool | None, raw)

        key = payload["key"]
        label = payload["label"]
        kind = payload["type"]
        description = payload["description"]
        nullable = payload["nullable"]
        if any(type(item) is not str for item in (key, label, kind, description)):
            raise ParameterError("parameter descriptor text fields must be strings")
        if type(nullable) is not bool:
            raise ParameterError("parameter descriptor nullable must be boolean")
        return cls(
            key=cast(str, key),
            label=cast(str, label),
            type=cast(str, kind),
            default=primitive("default"),
            nullable=nullable,
            minimum=primitive("min"),
            maximum=primitive("max"),
            description=cast(str, description),
            allowed_values=tuple(allowed_values),
        )


def _canonical_decimal(value: str, name: str) -> str:
    if type(value) is not str:
        raise ParameterError(f"{name} must be a canonical decimal string")
    try:
        decimal = Decimal(value)
    except Exception as error:
        raise ParameterError(f"{name} must be a decimal string") from error
    if not decimal.is_finite():
        raise ParameterError(f"{name} must be finite")
    if decimal == 0:
        return "0"
    result = format(decimal.normalize(), "f")
    return result if "." not in result else result.rstrip("0").rstrip(".")


@dataclass(frozen=True, slots=True)
class ValidatedParameterPayload:
    """Bounded, exact-schema primitive parameters passed to a Strategy parser."""

    _schema: tuple[ParameterSchema, ...]
    _values: tuple[tuple[str, int | str | bool | None], ...]

    def __post_init__(self) -> None:
        if type(self._schema) is not tuple or len(self._schema) > 32:
            raise ParameterError("parameter schema must contain at most 32 fields")
        if any(type(item) is not ParameterSchema for item in self._schema):
            raise ParameterError("parameter schema must contain descriptors")
        keys = tuple(item.key for item in self._schema)
        if len(set(keys)) != len(keys):
            raise ParameterError("parameter schema keys must be unique")
        if (
            type(self._values) is not tuple
            or any(
                type(item) is not tuple or len(item) != 2 for item in self._values
            )
            or tuple(key for key, _ in self._values) != keys
        ):
            raise ParameterError("parameter payload must match the exact schema")
        for descriptor, (key, value) in zip(self._schema, self._values, strict=True):
            if key != descriptor.key:
                raise ParameterError("parameter payload must match the exact schema")
            _validate_parameter_value(descriptor, value)
        encoded = self.to_json()
        if len(_canonical_json(encoded).encode("utf-8")) > 4096:
            raise ParameterError("parameter payload exceeds 4096 bytes")

    @classmethod
    def from_mapping(
        cls,
        schema: tuple[ParameterSchema, ...],
        values: Mapping[str, object],
    ) -> "ValidatedParameterPayload":
        if type(schema) is not tuple or len(schema) > 32:
            raise ParameterError("parameter schema must contain at most 32 fields")
        if type(values) not in (dict,):
            raise ParameterError("parameter payload must be an object")
        descriptors = {item.key: item for item in schema}
        if len(descriptors) != len(schema):
            raise ParameterError("parameter schema keys must be unique")
        if set(values) != set(descriptors):
            raise ParameterError("parameter payload keys must exactly match schema")
        normalized: list[tuple[str, int | str | bool | None]] = []
        for descriptor in schema:
            value = values[descriptor.key]
            normalized.append(
                (descriptor.key, _validate_parameter_value(descriptor, value))
            )
        return cls(schema, tuple(normalized))

    @classmethod
    def with_defaults(
        cls,
        schema: tuple[ParameterSchema, ...],
        values: Mapping[str, object],
    ) -> "ValidatedParameterPayload":
        """Materialize declared defaults before exact-schema validation."""

        if type(values) is not dict:
            raise ParameterError("parameter payload must be an object")
        typed_values = cast(dict[str, object], values)
        merged: dict[str, object] = {
            descriptor.key: descriptor.default for descriptor in schema
        }
        merged.update(typed_values)
        return cls.from_mapping(schema, merged)

    def get(self, key: str) -> int | str | bool | None:
        for candidate, value in self._values:
            if candidate == key:
                return value
        raise ParameterError(f"unknown parameter key: {key}")

    def to_json(self) -> dict[str, int | str | bool | None]:
        return dict(self._values)

    @property
    def canonical_bytes(self) -> bytes:
        return _canonical_json(self.to_json()).encode("utf-8")


def _validate_parameter_value(
    descriptor: ParameterSchema, value: object
) -> int | str | bool | None:
    if value is None:
        if not descriptor.nullable:
            raise ParameterError(f"{descriptor.key} is not nullable")
        return None
    if descriptor.type == "integer":
        if type(value) is not int:
            raise ParameterError(f"{descriptor.key} must be an integer")
        normalized: int | str | bool = value
    elif descriptor.type == "decimal":
        normalized = _canonical_decimal(value, descriptor.key)  # type: ignore[arg-type]
    elif descriptor.type == "boolean":
        if type(value) is not bool:
            raise ParameterError(f"{descriptor.key} must be a boolean")
        normalized = value
    else:
        if type(value) is not str:
            raise ParameterError(f"{descriptor.key} must be a string")
        normalized = value
    if descriptor.allowed_values and normalized not in descriptor.allowed_values:
        raise ParameterError(f"{descriptor.key} is not an allowed value")
    if descriptor.minimum is not None and Decimal(str(normalized)) < Decimal(
        str(descriptor.minimum)
    ):
        raise ParameterError(f"{descriptor.key} is below its minimum")
    if descriptor.maximum is not None and Decimal(str(normalized)) > Decimal(
        str(descriptor.maximum)
    ):
        raise ParameterError(f"{descriptor.key} exceeds its maximum")
    return normalized


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@dataclass(frozen=True, slots=True)
class StrategyContext:
    evaluation_time: datetime
    instrument: Instrument
    bars: tuple[Bar, ...]
    market: MarketSpecification
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
        market = self.market
        if type(market) is not MarketSpecification:
            raise InputError("StrategyContext market is missing or invalid")
        if market.instrument is not self.instrument:
            raise InputError("StrategyContext market does not match its instrument")
        if any(bar.instrument is not self.instrument for bar in self.bars):
            raise InputError("StrategyContext bars must match its instrument")
        for previous, current in zip(self.bars, self.bars[1:], strict=False):
            if current.start_time <= previous.start_time:
                raise InputError("bars must be strictly ordered and unique")
        if any(bar.end_time > self.evaluation_time for bar in self.bars):
            raise InputError("bars must end at or before evaluation_time")

    def to_json(self) -> dict[str, Any]:
        market = self.market
        return {
            "evaluation_time": self.evaluation_time.isoformat().replace("+00:00", "Z"),
            "instrument": self.instrument.value,
            "bars": [bar.to_json() for bar in self.bars],
            "position": self.position.value,
            "exposure_allowed": self.exposure_allowed,
            "market": market.to_json(),
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
    """Immutable Strategy output with retained proposal compatibility fields.

    ``expiry_time`` remains a persisted legacy-compatible field. V2 execution
    eligibility is owned by StrategyState and the runner's explicit handoff;
    this field is not an execution clock.
    """

    action: Action
    rationale: Rationale
    direction: Direction | None = None
    decision_time: datetime | None = None
    stop: StopProposal | None = None
    target: TargetProposal | None = None
    entry_policy: EntryPolicy = EntryPolicy.IMMEDIATE
    trigger_price: Decimal | None = None
    trigger_price_basis: PriceComponent | None = None
    # Retained immutable proposal compatibility; V2 does not use expiry_time
    # for execution eligibility and expiry_bars is persisted proposal metadata.
    expiry_time: datetime | None = None
    expiry_bars: int | None = None
    setup_facts: SetupFacts | None = None
    evidence: StrategyEvidence | None = None

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
        if (
            self.trigger_price_basis is not None
            and type(self.trigger_price_basis) is not PriceComponent
        ):
            raise InputError("trigger_price_basis must be a PriceComponent")
        if self.expiry_time is not None:
            _utc(self.expiry_time, "expiry_time")
        if self.expiry_bars is not None and (
            type(self.expiry_bars) is not int or self.expiry_bars <= 0
        ):
            raise InputError("expiry_bars must be a positive integer")
        if self.setup_facts is not None and type(self.setup_facts) is not SetupFacts:
            raise InputError("setup_facts must be SetupFacts")
        if self.evidence is not None and type(self.evidence) is not StrategyEvidence:
            raise InputError("evidence must be StrategyEvidence")
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
                value is not None
                for value in (
                    self.trigger_price,
                    self.trigger_price_basis,
                    self.expiry_time,
                    self.expiry_bars,
                )
            ):
                raise InputError(
                    "immediate entries cannot contain trigger or expiry fields"
                )
            if self.entry_policy is EntryPolicy.PRICE_TRIGGERED:
                if (
                    self.trigger_price is None
                    or self.trigger_price_basis is None
                    or self.expiry_bars is None
                ):
                    raise InputError(
                        "price-triggered entries require trigger and expiry bars"
                    )
                expected_basis = (
                    PriceComponent.ASK
                    if self.direction is Direction.LONG
                    else PriceComponent.BID
                )
                if self.trigger_price_basis is not expected_basis:
                    raise InputError("trigger price basis must match direction")
                if (
                    self.expiry_time is not None
                    and self.expiry_time <= self.decision_time
                ):
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
            "trigger_price": str(self.trigger_price)
            if self.trigger_price is not None
            else None,
            "trigger_price_basis": self.trigger_price_basis.value
            if self.trigger_price_basis
            else None,
            "expiry_time": self.expiry_time.isoformat().replace("+00:00", "Z")
            if self.expiry_time
            else None,
            "expiry_bars": self.expiry_bars,
            "setup_facts": self.setup_facts.to_json() if self.setup_facts else None,
            "evidence": self.evidence.to_json() if self.evidence else None,
            "rationale": self.rationale.to_json(),
        }


@dataclass(frozen=True, slots=True)
class StrategyState:
    """Immutable state supporting V2 plus read-only schema-1 compatibility.

    New registered V2 execution requires schema 2 through the Strategy
    contract. Schema 1, ``window_bars``, and ``AWAITING_CONFIRMATION`` remain
    only so existing serialized state can be validated/read without changing
    persisted facts.
    """

    # The default is retained for generic/legacy domain compatibility; the
    # production V2 runner supplies the persisted StrategyVersion schema.
    schema_version: int = 1
    phase: Phase = Phase.SEARCHING
    direction: Direction | None = None
    reference_high: Decimal | None = None
    reference_low: Decimal | None = None
    reference_time: datetime | None = None
    sweep_time: datetime | None = None
    # Legacy schema-1 counter; V2 uses watch_bars instead.
    window_bars: int = 0
    watch_bars: int = 0
    confirmation_time: datetime | None = None
    trigger_price: Decimal | None = None
    last_evaluated_bar_end: datetime | None = None

    def __post_init__(self) -> None:
        if (
            type(self.schema_version) is not int
            or type(self.window_bars) is not int
            or type(self.watch_bars) is not int
        ):
            raise StateError("schema_version and bar counts must be integers")
        if self.schema_version not in (1, 2):
            raise StateError("unsupported schema")
        if not 0 <= self.window_bars <= 5 or not 0 <= self.watch_bars <= 5:
            raise StateError("unsupported window or watch count")
        if self.schema_version == 1 and self.watch_bars:
            raise StateError("schema 1 does not support watch bars")
        if self.schema_version == 2 and self.window_bars:
            raise StateError("schema 2 does not support window bars")
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
        for name in (
            "reference_time",
            "sweep_time",
            "confirmation_time",
            "last_evaluated_bar_end",
        ):
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
            or self.window_bars
            or self.watch_bars
            or self.confirmation_time is not None
            or self.trigger_price is not None
        ):
            raise StateError("searching state contains setup fields")
        if self.phase is Phase.ARMED:
            if self.confirmation_time is None or self.trigger_price is None:
                raise StateError("armed state requires confirmation and trigger")
            if self.schema_version == 1 and self.window_bars > 5:
                raise StateError("armed state has invalid window count")
            if self.schema_version == 2 and self.watch_bars > 5:
                raise StateError("armed state has invalid watch count")
        if (
            self.schema_version == 1
            and self.phase is Phase.REFERENCE_IDENTIFIED
            and self.sweep_time is not None
        ):
            raise StateError("reference phase cannot have a sweep")
        if self.schema_version == 1 and self.phase is Phase.AWAITING_CONFIRMATION and (
            self.sweep_time is None or self.window_bars == 0
        ):
            raise StateError("awaiting confirmation requires a sweep")
        if self.phase is not Phase.ARMED and self.schema_version == 2 and (
            self.confirmation_time is not None
            or self.trigger_price is not None
            or self.watch_bars
        ):
            raise StateError("watch fields require armed state")
        if self.phase is not Phase.ARMED and self.schema_version == 1 and (
            self.confirmation_time is not None or self.trigger_price is not None
        ):
            raise StateError("confirmation fields require armed state")

    @classmethod
    def from_json(cls, value: Mapping[str, Any]) -> "StrategyState":
        """Read a complete legacy-compatible state envelope without migration."""

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
            "trigger_price": str(self.trigger_price)
            if self.trigger_price is not None
            else None,
            "last_evaluated_bar_end": stamp(self.last_evaluated_bar_end),
        }


StatePrimitive = str | int | bool | None | datetime


@dataclass(frozen=True, slots=True)
class StrategyStatePayloadDocument:
    """The bounded wire document emitted by a Strategy state codec."""

    codec_key: str
    payload_version: int
    fields: tuple[tuple[str, StatePrimitive], ...] = ()

    def __post_init__(self) -> None:
        if (
            type(self.codec_key) is not str
            or not self.codec_key
            or len(self.codec_key) > 64
        ):
            raise StateError("state codec key must be a bounded non-empty string")
        if type(self.payload_version) is not int or self.payload_version <= 0:
            raise StateError("state payload version must be positive")
        if type(self.fields) is not tuple or len(self.fields) > 16:
            raise StateError("state payload must contain at most 16 fields")
        keys: set[str] = set()
        for field in self.fields:
            if type(field) is not tuple or len(field) != 2:
                raise StateError("state payload fields must be key/value pairs")
            key, value = field
            if type(key) is not str or not key or len(key) > 64 or key in keys:
                raise StateError("state payload field keys must be unique and bounded")
            keys.add(key)
            if type(value) not in (str, int, bool, type(None), datetime):
                raise StateError("state payload fields must be flat primitives")
            if type(value) is str and len(value) > 256:
                raise StateError("state payload strings must be at most 256 characters")
            if type(value) is datetime:
                _utc(value, key)
        if len(self.canonical_bytes) > 4096:
            raise StateError("state payload exceeds 4096 bytes")

    @classmethod
    def from_mapping(
        cls, codec_key: str, payload_version: int, fields: Mapping[str, StatePrimitive]
    ) -> "StrategyStatePayloadDocument":
        if type(fields) is not dict:
            raise StateError("state payload fields must be an object")
        # Sorting is part of the codec boundary, not Strategy methodology.
        typed_fields = cast(dict[str, StatePrimitive], fields)
        return cls(codec_key, payload_version, tuple(sorted(typed_fields.items())))

    @staticmethod
    def _wire_value(value: StatePrimitive) -> str | int | bool | None:
        if type(value) is datetime:
            return value.isoformat().replace("+00:00", "Z")
        return cast(str | int | bool | None, value)

    def to_json(self) -> dict[str, Any]:
        return {
            "codec_key": self.codec_key,
            "payload_version": self.payload_version,
            "fields": {key: self._wire_value(value) for key, value in self.fields},
        }

    @property
    def canonical_bytes(self) -> bytes:
        return _canonical_json(self.to_json()).encode("utf-8")

    def get(self, key: str) -> StatePrimitive:
        for candidate, value in self.fields:
            if candidate == key:
                return value
        raise StateError(f"unknown state payload key: {key}")

    @classmethod
    def from_json(cls, value: Mapping[str, object]) -> "StrategyStatePayloadDocument":
        if type(value) is not dict:
            raise StateError("state payload JSON has unexpected fields")
        payload = cast(dict[str, object], value)
        if set(payload) != {
            "codec_key", "payload_version", "fields"
        }:
            raise StateError("state payload JSON has unexpected fields")
        fields = payload["fields"]
        if type(fields) is not dict:
            raise StateError("state payload fields must be an object")
        codec_key = payload["codec_key"]
        payload_version = payload["payload_version"]
        if type(codec_key) is not str or type(payload_version) is not int:
            raise StateError("state payload header is invalid")
        raw_fields = cast(dict[object, object], fields)
        typed_fields: dict[str, StatePrimitive] = {}
        for key, raw in raw_fields.items():
            if type(key) is not str or type(raw) not in (
                str,
                int,
                bool,
                type(None),
                datetime,
            ):
                raise StateError("state payload fields contain invalid primitives")
            typed_fields[key] = cast(StatePrimitive, raw)
        try:
            return cls.from_mapping(
                codec_key, payload_version, typed_fields
            )
        except (KeyError, TypeError, ValueError) as error:
            raise StateError("invalid state payload") from error


@dataclass(frozen=True, slots=True)
class PendingEntryHandoff:
    """Normalized analytical-bar clock for a price-triggered opening."""

    policy: EntryPolicy
    direction: Direction
    trigger_price: Decimal
    trigger_price_basis: PriceComponent
    decision_frontier: datetime
    decision_time: datetime
    eligibility_limit: int
    consumed_count: int = 0

    def __post_init__(self) -> None:
        if self.policy is not EntryPolicy.PRICE_TRIGGERED:
            raise StateError("pending handoffs must be price-triggered")
        if (
            type(self.direction) is not Direction
            or type(self.trigger_price_basis) is not PriceComponent
        ):
            raise StateError("pending handoff direction and basis are invalid")
        expected = (
            PriceComponent.ASK
            if self.direction is Direction.LONG
            else PriceComponent.BID
        )
        if self.trigger_price_basis is not expected:
            raise StateError("pending trigger basis must match direction")
        try:
            if _dec(self.trigger_price, "trigger_price") <= 0:
                raise StateError("trigger_price must be positive")
            _utc(self.decision_frontier, "decision_frontier")
            _utc(self.decision_time, "decision_time")
        except (TypeError, ValueError) as error:
            raise StateError(str(error)) from error
        if self.decision_time != self.decision_frontier:
            raise StateError("pending decision time must equal its frontier")
        if (
            type(self.eligibility_limit) is not int
            or not 1 <= self.eligibility_limit <= 1000
        ):
            raise StateError("eligibility limit must be between 1 and 1000")
        if (
            type(self.consumed_count) is not int
            or not 0 <= self.consumed_count <= self.eligibility_limit
        ):
            raise StateError("pending consumed count is outside its eligibility window")

    @property
    def limit(self) -> int:
        return self.eligibility_limit

    def consumed_at(self, frontier: datetime) -> "PendingEntryHandoff":
        _utc(frontier, "frontier")
        if frontier <= self.decision_frontier:
            raise StateError("pending frontier must be after the decision frontier")
        if self.consumed_count >= self.eligibility_limit:
            raise StateError("pending eligibility window is exhausted")
        return dataclass_replace(self, consumed_count=self.consumed_count + 1)

    def to_json(self) -> dict[str, Any]:
        def stamp(value: datetime) -> str:
            return value.isoformat().replace("+00:00", "Z")
        return {
            "policy": self.policy.value,
            "direction": self.direction.value,
            "trigger_price": str(self.trigger_price),
            "trigger_price_basis": self.trigger_price_basis.value,
            "decision_frontier": stamp(self.decision_frontier),
            "decision_time": stamp(self.decision_time),
            "eligibility_limit": self.eligibility_limit,
            "consumed_count": self.consumed_count,
        }

    @classmethod
    def from_json(cls, value: Mapping[str, object]) -> "PendingEntryHandoff":
        required = {
            "policy", "direction", "trigger_price", "trigger_price_basis",
            "decision_frontier", "decision_time", "eligibility_limit", "consumed_count",
        }
        if type(value) is not dict:
            raise StateError("pending handoff JSON has unexpected fields")
        payload = cast(dict[str, object], value)
        if set(payload) != required:
            raise StateError("pending handoff JSON has unexpected fields")
        try:
            if any(
                type(payload[name]) is not str
                for name in (
                    "policy",
                    "direction",
                    "trigger_price",
                    "trigger_price_basis",
                    "decision_frontier",
                    "decision_time",
                )
            ):
                raise StateError("pending handoff text fields are invalid")
            frontier = datetime.fromisoformat(
                cast(str, payload["decision_frontier"]).replace("Z", "+00:00")
            )
            decision_time = datetime.fromisoformat(
                cast(str, payload["decision_time"]).replace("Z", "+00:00")
            )
            eligibility_limit = payload["eligibility_limit"]
            consumed_count = payload["consumed_count"]
            if type(eligibility_limit) is not int or type(consumed_count) is not int:
                raise StateError("pending handoff counts are invalid")
            return cls(
                policy=EntryPolicy(cast(str, payload["policy"])),
                direction=Direction(cast(str, payload["direction"])),
                trigger_price=Decimal(cast(str, payload["trigger_price"])),
                trigger_price_basis=PriceComponent(
                    cast(str, payload["trigger_price_basis"])
                ),
                decision_frontier=frontier,
                decision_time=decision_time,
                eligibility_limit=eligibility_limit,
                consumed_count=consumed_count,
            )
        except (KeyError, TypeError, ValueError, ArithmeticError) as error:
            if isinstance(error, StateError):
                raise
            raise StateError("invalid pending handoff") from error


@dataclass(frozen=True, slots=True)
class StrategyStateEnvelope:
    """Atlas-owned safety/frontier envelope around typed Strategy state."""

    state_schema_version: int
    last_evaluated_bar_end: datetime | None
    payload: StrategyStatePayloadDocument
    pending_entry: PendingEntryHandoff | None = None
    exposure_allowed: bool = True

    def __post_init__(self) -> None:
        if type(self.state_schema_version) is not int or self.state_schema_version <= 0:
            raise StateError("state schema version must be positive")
        if self.last_evaluated_bar_end is not None:
            try:
                _utc(self.last_evaluated_bar_end, "last_evaluated_bar_end")
            except (TypeError, ValueError) as error:
                raise StateError(str(error)) from error
        if type(self.payload) is not StrategyStatePayloadDocument:
            raise StateError("state envelope payload is invalid")
        if (
            self.pending_entry is not None
            and type(self.pending_entry) is not PendingEntryHandoff
        ):
            raise StateError("pending entry handoff is invalid")
        if type(self.exposure_allowed) is not bool:
            raise StateError("exposure_allowed must be bool")

    def validate_frontier(self, frontier: datetime, evaluation_time: datetime) -> None:
        _utc(frontier, "frontier")
        _utc(evaluation_time, "evaluation_time")
        if frontier > evaluation_time:
            raise StateError("state frontier cannot be in the future")
        if (
            self.last_evaluated_bar_end is not None
            and frontier <= self.last_evaluated_bar_end
        ):
            raise StateError("state frontier must advance strictly")

    def validate_evaluation_time(self, evaluation_time: datetime) -> None:
        """Reject a restored frontier that is ahead of the supplied clock."""

        try:
            _utc(evaluation_time, "evaluation_time")
        except (TypeError, ValueError) as error:
            raise StateError(str(error)) from error
        if (
            self.last_evaluated_bar_end is not None
            and self.last_evaluated_bar_end > evaluation_time
        ):
            raise StateError("state frontier cannot be in the future")

    def advance_to(
        self, frontier: datetime, evaluation_time: datetime
    ) -> "StrategyStateEnvelope":
        self.validate_frontier(frontier, evaluation_time)
        return dataclass_replace(self, last_evaluated_bar_end=frontier)

    def can_open(self, position: PositionState = PositionState.FLAT) -> bool:
        return self.exposure_allowed and position is PositionState.FLAT

    def to_json(self) -> dict[str, Any]:
        return {
            "state_schema_version": self.state_schema_version,
            "last_evaluated_bar_end": (
                self.last_evaluated_bar_end.isoformat().replace("+00:00", "Z")
                if self.last_evaluated_bar_end
                else None
            ),
            "payload": self.payload.to_json(),
            "pending_entry": (
                self.pending_entry.to_json() if self.pending_entry else None
            ),
            "exposure_allowed": self.exposure_allowed,
        }

    @property
    def canonical_bytes(self) -> bytes:
        return _canonical_json(self.to_json()).encode("utf-8")

    @classmethod
    def from_json(cls, value: Mapping[str, object]) -> "StrategyStateEnvelope":
        required = {
            "state_schema_version", "last_evaluated_bar_end", "payload",
            "pending_entry", "exposure_allowed",
        }
        if type(value) is not dict:
            raise StateError("state envelope JSON has unexpected fields")
        payload = cast(dict[str, object], value)
        if set(payload) != required:
            raise StateError("state envelope JSON has unexpected fields")
        raw_frontier = payload["last_evaluated_bar_end"]
        try:
            if raw_frontier is not None and type(raw_frontier) is not str:
                raise StateError("state frontier must be an ISO timestamp")
            frontier = (
                datetime.fromisoformat(raw_frontier.replace("Z", "+00:00"))
                if raw_frontier is not None else None
            )
            pending = (
                PendingEntryHandoff.from_json(
                    cast(dict[str, object], payload["pending_entry"])
                )
                if payload["pending_entry"] is not None else None
            )
            state_schema_version = payload["state_schema_version"]
            exposure_allowed = payload["exposure_allowed"]
            if (
                type(state_schema_version) is not int
                or type(exposure_allowed) is not bool
            ):
                raise StateError("state envelope header is invalid")
            return cls(
                state_schema_version=state_schema_version,
                last_evaluated_bar_end=frontier,
                payload=StrategyStatePayloadDocument.from_json(
                    cast(dict[str, object], payload["payload"])
                ),
                pending_entry=pending,
                exposure_allowed=exposure_allowed,
            )
        except (KeyError, TypeError, ValueError, ArithmeticError) as error:
            if isinstance(error, StateError):
                raise
            raise StateError("invalid state envelope") from error


def dataclass_replace(value: Any, **changes: Any) -> Any:
    """Tiny local wrapper keeping domain primitives independent of callers."""

    from dataclasses import replace

    return replace(value, **changes)


@dataclass(frozen=True, slots=True)
class StrategyEvaluation:
    decision: StrategyDecision
    next_state: StrategyState | StrategyStateEnvelope

    def __post_init__(self) -> None:
        if (
            type(self.decision) is not StrategyDecision
            or type(self.next_state) not in (StrategyState, StrategyStateEnvelope)
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
        """Deprecated read-only compatibility; persistence uses the canonical name."""
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
