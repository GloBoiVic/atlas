"""Canonical market observations accepted by the Phase 1 strategy boundary."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Any


class DomainError(ValueError):
    """Base class for actionable domain failures."""


class InputError(DomainError):
    """Invalid market data at the strategy input boundary."""


class Instrument(StrEnum):
    EUR_USD = "EUR/USD"


class Timeframe(StrEnum):
    M15 = "15m"


class PriceComponent(StrEnum):
    MID = "MID"


def _decimal(value: Decimal, name: str) -> Decimal:
    if type(value) is not Decimal:  # bool and float must not cross this boundary
        raise InputError(f"{name} must be a Decimal")
    return value


def _utc(value: datetime, name: str) -> datetime:
    if type(value) is not datetime or value.tzinfo is None:
        raise InputError(f"{name} must be timezone-aware UTC")
    if value.utcoffset() != timedelta(0):
        raise InputError(f"{name} must be UTC")
    return value


@dataclass(frozen=True, slots=True)
class Bar:
    """A completed, canonical EUR/USD MID 15-minute candle."""

    instrument: Instrument
    timeframe: Timeframe
    price_component: PriceComponent
    start_time: datetime
    end_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    complete: bool = True

    def __post_init__(self) -> None:
        if self.instrument is not Instrument.EUR_USD:
            raise InputError("only EUR/USD is supported")
        if self.timeframe is not Timeframe.M15:
            raise InputError("only 15m bars are supported")
        if self.price_component is not PriceComponent.MID:
            raise InputError("only MID bars are supported")
        if type(self.complete) is not bool:
            raise InputError("complete must be bool")
        start = _utc(self.start_time, "start_time")
        end = _utc(self.end_time, "end_time")
        if not self.complete:
            raise InputError("strategy input bars must be complete")
        if (
            end - start != timedelta(minutes=15)
            or start.minute % 15 != 0
            or start.second
            or start.microsecond
        ):
            raise InputError("bar must be an aligned 15-minute interval")
        if end <= start:
            raise InputError("bar interval must be positive")
        prices = {
            name: _decimal(getattr(self, name), name)
            for name in ("open", "high", "low", "close")
        }
        if any(value.is_nan() or value.is_infinite() for value in prices.values()):
            raise InputError("OHLC values must be finite")
        if prices["high"] < max(prices["open"], prices["close"]):
            raise InputError("high must contain open and close")
        if prices["low"] > min(prices["open"], prices["close"]):
            raise InputError("low must contain open and close")

    def to_json(self) -> dict[str, Any]:
        return {
            "instrument": self.instrument.value,
            "timeframe": self.timeframe.value,
            "price_component": self.price_component.value,
            "start_time": self.start_time.isoformat().replace("+00:00", "Z"),
            "end_time": self.end_time.isoformat().replace("+00:00", "Z"),
            "open": str(self.open),
            "high": str(self.high),
            "low": str(self.low),
            "close": str(self.close),
            "complete": True,
        }
