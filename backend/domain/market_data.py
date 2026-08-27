"""Canonical market observations accepted by the Phase 1 strategy boundary."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID


class DomainError(ValueError):
    """Base class for actionable domain failures."""


class InputError(DomainError):
    """Invalid market data at the strategy input boundary."""


class Instrument(StrEnum):
    EUR_USD = "EUR/USD"


class Provider(StrEnum):
    OANDA = "OANDA"


class Timeframe(StrEnum):
    M1 = "1m"
    M15 = "15m"


class PriceComponent(StrEnum):
    MID = "MID"
    BID = "BID"
    ASK = "ASK"


ALIGNMENT_CONVENTION = "UTC_HALF_OPEN_V1"
SESSION_POLICY = "OANDA_FX_NY_V1"
FINGERPRINT_SCHEMA = "ATLAS_DATASET_SHA256_V1"
SNAPSHOT_SCHEMA_V1 = "ATLAS_HISTORICAL_SNAPSHOT_V1"
SNAPSHOT_SCHEMA_V2 = "ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2"
FINGERPRINT_SCHEMA_V2 = "ATLAS_DATASET_SHA256_V2"
NATIVE_M15_CONTRACT_V1 = "OANDA_M15_NATIVE_UTC_V1"
NATIVE_M1_EXECUTION_CONTRACT_V1 = "OANDA_M1_NATIVE_BID_ASK_UTC_V1"
GAP_POLICY_V1 = "ATLAS_HISTORICAL_GAP_POLICY_V1"


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


def _sha256(value: str, name: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or value != value.lower()
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise InputError(f"{name} must be a lowercase SHA-256")
    return value


@dataclass(frozen=True, slots=True)
class VenueInstrument:
    instrument: Instrument
    provider: Provider
    provider_symbol: str

    def __post_init__(self) -> None:
        if type(self.instrument) is not Instrument:
            raise InputError("instrument must be an Instrument")
        if type(self.provider) is not Provider:
            raise InputError("provider must be a Provider")
        if type(self.provider_symbol) is not str:
            raise InputError("provider_symbol must be a string")
        if (
            self.instrument is not Instrument.EUR_USD
            or self.provider is not Provider.OANDA
            or self.provider_symbol != "EUR_USD"
        ):
            raise InputError("unsupported Instrument/provider mapping")

    def to_json(self) -> dict[str, str]:
        return {
            "instrument": self.instrument.value,
            "provider": self.provider.value,
            "provider_symbol": self.provider_symbol,
        }


@dataclass(frozen=True, slots=True)
class Bar:
    """A completed canonical candle."""

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
    provider: Provider = Provider.OANDA
    volume: Decimal | None = None

    def __post_init__(self) -> None:
        if self.instrument is not Instrument.EUR_USD:
            raise InputError("only EUR/USD is supported")
        if type(self.provider) is not Provider:
            raise InputError("provider must be a Provider")
        if type(self.timeframe) is not Timeframe:
            raise InputError("timeframe must be a Timeframe")
        if type(self.price_component) is not PriceComponent:
            raise InputError("price_component must be a PriceComponent")
        if type(self.complete) is not bool:
            raise InputError("complete must be bool")
        start = _utc(self.start_time, "start_time")
        end = _utc(self.end_time, "end_time")
        if not self.complete:
            raise InputError("strategy input bars must be complete")
        minutes = 1 if self.timeframe is Timeframe.M1 else 15
        if end - start != timedelta(minutes=minutes):
            raise InputError("bar interval does not match timeframe")
        if start.second or start.microsecond or start.minute % minutes:
            raise InputError("bar must be aligned to its timeframe")
        if end <= start:
            raise InputError("bar interval must be positive")
        prices = {
            name: _decimal(getattr(self, name), name)
            for name in ("open", "high", "low", "close")
        }
        if any(
            value.is_nan() or value.is_infinite() or value <= 0
            for value in prices.values()
        ):
            raise InputError("OHLC values must be finite and positive")
        if prices["high"] < max(prices["open"], prices["close"]):
            raise InputError("high must contain open and close")
        if prices["low"] > min(prices["open"], prices["close"]):
            raise InputError("low must contain open and close")
        if self.volume is not None:
            volume = _decimal(self.volume, "volume")
            if volume.is_nan() or volume.is_infinite() or volume < 0:
                raise InputError("volume must be finite and non-negative")

    def to_json(self) -> dict[str, Any]:
        return {
            "instrument": self.instrument.value,
            "provider": self.provider.value,
            "timeframe": self.timeframe.value,
            "price_component": self.price_component.value,
            "start_time": self.start_time.isoformat().replace("+00:00", "Z"),
            "end_time": self.end_time.isoformat().replace("+00:00", "Z"),
            "open": str(self.open),
            "high": str(self.high),
            "low": str(self.low),
            "close": str(self.close),
            "volume": str(self.volume) if self.volume is not None else None,
            "complete": True,
        }


@dataclass(frozen=True, slots=True)
class DatasetSnapshot:
    id: UUID
    venue_instrument: VenueInstrument
    base_resolution: Timeframe
    components: tuple[PriceComponent, ...]
    coverage_start: datetime
    coverage_end: datetime
    alignment_convention: str
    session_policy: str
    fingerprint_schema: str
    fingerprint: str
    integrity_summary: dict[str, Any]
    created_at: datetime
    snapshot_schema: str = SNAPSHOT_SCHEMA_V1

    def __post_init__(self) -> None:
        if (
            type(self.id) is not UUID
            or type(self.venue_instrument) is not VenueInstrument
        ):
            raise InputError("snapshot identity fields have invalid types")
        if self.snapshot_schema not in (SNAPSHOT_SCHEMA_V1, SNAPSHOT_SCHEMA_V2):
            raise InputError("unsupported snapshot schema")
        expected = (
            (
                Timeframe.M1,
                (PriceComponent.ASK, PriceComponent.BID, PriceComponent.MID),
            ),
            (Timeframe.M15, (PriceComponent.MID,)),
        )
        allowed = (
            expected[0]
            if self.snapshot_schema == SNAPSHOT_SCHEMA_V1
            else expected[1]
        )
        if (
            self.base_resolution is not allowed[0]
            or type(self.components) is not tuple
            or self.components != allowed[1]
        ):
            raise InputError("snapshot resolution/components do not match schema")
        if any(type(component) is not PriceComponent for component in self.components):
            raise InputError("snapshot components must be PriceComponents")
        start = _utc(self.coverage_start, "coverage_start")
        end = _utc(self.coverage_end, "coverage_end")
        if (
            end <= start
            or start.second
            or start.microsecond
            or end.second
            or end.microsecond
        ):
            raise InputError(
                "snapshot coverage must be a positive minute-aligned range"
            )
        if self.alignment_convention != ALIGNMENT_CONVENTION:
            raise InputError("unsupported alignment convention")
        if self.session_policy != SESSION_POLICY:
            raise InputError("unsupported session policy")
        expected_fingerprint = (
            FINGERPRINT_SCHEMA
            if self.snapshot_schema == SNAPSHOT_SCHEMA_V1
            else FINGERPRINT_SCHEMA_V2
        )
        if self.fingerprint_schema != expected_fingerprint:
            raise InputError("unsupported fingerprint schema")
        _sha256(self.fingerprint, "fingerprint")
        if type(self.integrity_summary) is not dict:
            raise InputError("integrity_summary must be a JSON object")
        if self.integrity_summary.get("status") != "VALID":
            raise InputError("snapshot integrity status must be VALID")
        policy_version = self.integrity_summary.get("policy_version")
        if (
            self.snapshot_schema == SNAPSHOT_SCHEMA_V2
            and policy_version != GAP_POLICY_V1
        ):
            raise InputError("V2 snapshot must declare the historical gap policy")
        if (
            self.snapshot_schema == SNAPSHOT_SCHEMA_V1
            and policy_version is not None
            and policy_version != self.session_policy
        ):
            raise InputError(
                "snapshot integrity policy version does not match session policy"
            )
        _utc(self.created_at, "created_at")

    def to_json(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "venue_instrument": self.venue_instrument.to_json(),
            "base_resolution": self.base_resolution.value,
            "components": [component.value for component in self.components],
            "coverage_start": self.coverage_start.isoformat().replace("+00:00", "Z"),
            "coverage_end": self.coverage_end.isoformat().replace("+00:00", "Z"),
            "alignment_convention": self.alignment_convention,
            "session_policy": self.session_policy,
            "fingerprint_schema": self.fingerprint_schema,
            "fingerprint": self.fingerprint,
            "integrity_summary": self.integrity_summary.copy(),
            "created_at": self.created_at.isoformat().replace("+00:00", "Z"),
            "snapshot_schema": self.snapshot_schema,
        }
