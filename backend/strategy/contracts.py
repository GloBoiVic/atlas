"""Pure domain contracts shared by deployed strategies and the strategy engine."""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, cast
from uuid import UUID


class SignalDirection(StrEnum):
    """The trading action represented by a strategy decision."""

    BUY = "buy"
    SELL = "sell"
    CLOSE = "close"


class DataType(StrEnum):
    """Market data kinds a strategy may observe."""

    CANDLE = "candle"
    TICK = "tick"


type JsonValue = (
    None
    | str
    | int
    | bool
    | Decimal
    | dict[str, "JsonValue"]
    | list["JsonValue"]
    | tuple["JsonValue", ...]
)
type FrozenJsonValue = (
    None
    | str
    | int
    | bool
    | Decimal
    | "_FrozenJsonDict"
    | tuple["FrozenJsonValue", ...]
)


class _FrozenJsonDict(dict[str, FrozenJsonValue]):
    """Dict-compatible JSON object that rejects mutation after construction."""

    def __setitem__(self, key: str, value: Any) -> None:
        raise TypeError("metadata is immutable")

    def __delitem__(self, key: str) -> None:
        raise TypeError("metadata is immutable")

    def clear(self) -> None:
        raise TypeError("metadata is immutable")

    def pop(self, key: str, default: Any = None) -> Any:
        raise TypeError("metadata is immutable")

    def popitem(self) -> tuple[str, Any]:
        raise TypeError("metadata is immutable")

    def setdefault(self, key: str, default: Any = None) -> Any:
        raise TypeError("metadata is immutable")

    def update(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError("metadata is immutable")


def _freeze_json(value: JsonValue) -> FrozenJsonValue:
    if isinstance(value, dict):
        frozen = _FrozenJsonDict()
        dict.update(frozen, {key: _freeze_json(item) for key, item in value.items()})
        return frozen
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item) for item in value)
    return value


@dataclass(frozen=True, slots=True)
class DataRequirement:
    """A strategy's single data series requirement."""

    data_type: DataType
    timeframe: str

    def __post_init__(self) -> None:
        if not isinstance(self.data_type, DataType):
            raise TypeError("data_type must be a DataType")
        if not self.timeframe or self.timeframe.strip() != self.timeframe:
            raise ValueError("timeframe must be a non-empty value without surrounding whitespace")
        if not any(character.isdigit() for character in self.timeframe):
            raise ValueError("timeframe must contain a numeric interval")
        if not self.timeframe[-1].isalpha():
            raise ValueError("timeframe must end with a time unit")


def _validate_metadata(metadata: dict[str, Any]) -> _FrozenJsonDict:
    """Validate metadata while preserving Decimal indicator values at the domain boundary."""

    def validate(value: Any) -> None:
        if isinstance(value, Decimal):
            if not value.is_finite():
                raise ValueError("metadata Decimal values must be finite")
            return
        if value is None or isinstance(value, (str, int, bool)):
            return
        if isinstance(value, dict):
            for key, item in value.items():
                if not isinstance(key, str):
                    raise TypeError("metadata keys must be strings")
                validate(item)
            return
        if isinstance(value, (list, tuple)):
            for item in value:
                validate(item)
            return
        raise TypeError("metadata must contain JSON-compatible values or Decimal")

    validate(metadata)
    frozen = _freeze_json(cast("dict[str, JsonValue]", metadata))
    if not isinstance(frozen, _FrozenJsonDict):
        raise TypeError("metadata must be a JSON object")
    return frozen


def _validate_strength(strength: Decimal) -> None:
    if not isinstance(strength, Decimal):
        raise TypeError("strength must be a Decimal")
    if not strength.is_finite() or not Decimal("0") <= strength <= Decimal("1"):
        raise ValueError("strength must be a finite Decimal between 0 and 1")


def _validate_utc(timestamp: datetime, field_name: str) -> None:
    if timestamp.tzinfo is None or timestamp.utcoffset() != UTC.utcoffset(timestamp):
        raise ValueError(f"{field_name} must be UTC")


@dataclass(frozen=True, slots=True)
class StrategyDecision:
    """Immutable strategy output before engine-owned provenance is attached."""

    direction: SignalDirection
    strength: Decimal
    metadata: dict[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.direction, SignalDirection):
            raise TypeError("direction must be a SignalDirection")
        _validate_strength(self.strength)
        object.__setattr__(self, "metadata", _validate_metadata(self.metadata))


@dataclass(frozen=True, slots=True)
class Signal:
    """Canonical immutable signal with complete strategy provenance."""

    instrument_id: UUID
    direction: SignalDirection
    strength: Decimal
    metadata: dict[str, Any]
    candle_timestamp: datetime
    strategy_version_id: UUID
    strategy_name: str
    strategy_commit_sha: str

    def __post_init__(self) -> None:
        if not isinstance(self.instrument_id, UUID):
            raise TypeError("instrument_id must be a UUID")
        if not isinstance(self.strategy_version_id, UUID):
            raise TypeError("strategy_version_id must be a UUID")
        if not isinstance(self.direction, SignalDirection):
            raise TypeError("direction must be a SignalDirection")
        _validate_strength(self.strength)
        _validate_utc(self.candle_timestamp, "candle_timestamp")
        if not self.strategy_name or not self.strategy_commit_sha:
            raise ValueError("strategy identity must not be empty")
        object.__setattr__(self, "metadata", _validate_metadata(self.metadata))
