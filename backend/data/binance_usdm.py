"""Contracts and deterministic parsers for Binance USDⓈ-M public streams.

This module deliberately contains no transport or task-management code.  It converts
the JSON-shaped payloads received from Binance into provider-neutral domain values at
the adapter boundary, preserving Decimal precision and UTC timestamps.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from math import isfinite
from uuid import UUID

from backend.data.models import Candle, Instrument, Tick

BINANCE_USDM_PROVIDER = "binance_usdm"
BINANCE_USDM_FSTREAM_BASE_URL = "wss://fstream.binance.com/ws"


@dataclass(frozen=True, slots=True)
class BinanceUsdMStreamingConfig:
    """Non-secret settings for Binance USDⓈ-M public WebSocket streams."""

    base_url: str = BINANCE_USDM_FSTREAM_BASE_URL
    ping_interval_seconds: float = 20.0
    ping_timeout_seconds: float = 20.0
    close_timeout_seconds: float = 10.0

    def __post_init__(self) -> None:
        if self.base_url != BINANCE_USDM_FSTREAM_BASE_URL:
            raise ValueError("Binance USDⓈ-M base_url must be the public fstream endpoint")
        if any(
            value <= 0
            for value in (
                self.ping_interval_seconds,
                self.ping_timeout_seconds,
                self.close_timeout_seconds,
            )
        ):
            raise ValueError("Binance USDⓈ-M stream timeouts must be positive")
        if any(
            not isfinite(value)
            for value in (
                self.ping_interval_seconds,
                self.ping_timeout_seconds,
                self.close_timeout_seconds,
            )
        ):
            raise ValueError("Binance USDⓈ-M stream timeouts must be finite")


@dataclass(frozen=True, slots=True)
class BookTicker:
    """Best executable bid/ask update from ``@bookTicker``."""

    instrument_id: UUID
    timestamp: datetime
    bid: Decimal
    ask: Decimal


@dataclass(frozen=True, slots=True)
class MarkPriceUpdate:
    """Mark, index, and funding context from ``@markPrice@1s``."""

    instrument_id: UUID
    timestamp: datetime
    mark_price: Decimal
    index_price: Decimal
    funding_rate: Decimal
    next_funding_time: datetime


def parse_binance_usdm_kline(
    payload: Mapping[str, object], instrument: Instrument, timeframe: str
) -> Candle:
    """Parse one Binance USDⓈ-M kline envelope into a normalized candle."""
    _require_provider(instrument)
    _check_event_type(payload, "kline")
    if not timeframe:
        raise ValueError("Binance USDⓈ-M kline timeframe must not be empty")
    kline = _mapping(payload.get("k"), "kline payload")
    open_time = _timestamp(kline.get("t"), "kline open time")
    close_time = _timestamp(kline.get("T"), "kline close time")
    is_complete = _boolean(kline.get("x"), "kline completion flag")
    open_price = _positive_decimal(kline.get("o"), "open")
    high = _positive_decimal(kline.get("h"), "high")
    low = _positive_decimal(kline.get("l"), "low")
    close = _positive_decimal(kline.get("c"), "close")
    base_volume = _non_negative_decimal(kline.get("v"), "base volume")
    quote_volume = _non_negative_decimal(kline.get("q"), "quote volume")
    taker_buy_base = _non_negative_decimal(kline.get("V"), "taker buy base volume")
    taker_buy_quote = _non_negative_decimal(kline.get("Q"), "taker buy quote volume")
    trade_count = _non_negative_int(kline.get("n"), "trade count")
    if high < max(open_price, close) or low > min(open_price, close):
        raise ValueError("Binance USDⓈ-M kline OHLC bounds are invalid")
    if close_time < open_time:
        raise ValueError("Binance USDⓈ-M kline close time precedes open time")
    return Candle(
        instrument_id=instrument.id,
        provider=BINANCE_USDM_PROVIDER,
        timeframe=timeframe,
        open_time=open_time,
        close_time=close_time,
        price_basis="trade",
        open=open_price,
        high=high,
        low=low,
        close=close,
        base_volume=base_volume,
        quote_volume=quote_volume,
        trade_count=trade_count,
        taker_buy_base_volume=taker_buy_base,
        taker_buy_quote_volume=taker_buy_quote,
        is_complete=is_complete,
    )


def parse_binance_usdm_agg_trade(payload: Mapping[str, object], instrument: Instrument) -> Tick:
    """Parse one Binance USDⓈ-M aggregate trade into the existing Tick contract."""
    _require_provider(instrument)
    _check_event_type(payload, "aggTrade")
    return Tick(
        instrument_id=instrument.id,
        timestamp=_timestamp(payload.get("T"), "aggregate trade time"),
        price=_positive_decimal(payload.get("p"), "aggregate trade price"),
        base_volume=_non_negative_decimal(payload.get("q"), "aggregate trade quantity"),
    )


def parse_binance_usdm_book_ticker(
    payload: Mapping[str, object], instrument: Instrument
) -> BookTicker:
    """Parse one Binance USDⓈ-M best-bid/best-ask update."""
    _require_provider(instrument)
    _check_event_type(payload, "bookTicker")
    bid = _positive_decimal(payload.get("b"), "bid price")
    ask = _positive_decimal(payload.get("a"), "ask price")
    if bid > ask:
        raise ValueError("Binance USDⓈ-M book ticker is crossed")
    return BookTicker(
        instrument_id=instrument.id,
        timestamp=_timestamp(payload.get("E"), "book ticker event time"),
        bid=bid,
        ask=ask,
    )


def parse_binance_usdm_mark_price(
    payload: Mapping[str, object], instrument: Instrument
) -> MarkPriceUpdate:
    """Parse one Binance USDⓈ-M mark-price context update."""
    _require_provider(instrument)
    _check_event_type(payload, "markPriceUpdate")
    return MarkPriceUpdate(
        instrument_id=instrument.id,
        timestamp=_timestamp(payload.get("E"), "mark price event time"),
        mark_price=_positive_decimal(payload.get("p"), "mark price"),
        index_price=_positive_decimal(payload.get("i"), "index price"),
        funding_rate=_finite_decimal(payload.get("r"), "funding rate"),
        next_funding_time=_timestamp(payload.get("T"), "next funding time"),
    )


def _require_provider(instrument: Instrument) -> None:
    if instrument.provider != BINANCE_USDM_PROVIDER:
        raise ValueError(f"instrument provider must be {BINANCE_USDM_PROVIDER!r}")


def _check_event_type(payload: Mapping[str, object], expected: str) -> None:
    event_type = payload.get("e")
    if event_type is not None and event_type != expected:
        raise ValueError(f"unexpected Binance USDⓈ-M event type: {event_type!r}")


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return value


def _boolean(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean")
    return value


def _timestamp(value: object, name: str) -> datetime:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer millisecond timestamp")
    try:
        return datetime.fromtimestamp(value / 1000, tz=UTC)
    except (OverflowError, OSError, ValueError) as error:
        raise ValueError(f"{name} is invalid") from error


def _finite_decimal(value: object, name: str) -> Decimal:
    if value is None or isinstance(value, bool):
        raise ValueError(f"{name} is missing")
    try:
        decimal = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError(f"{name} is invalid") from None
    if not decimal.is_finite():
        raise ValueError(f"{name} must be finite")
    return decimal


def _positive_decimal(value: object, name: str) -> Decimal:
    decimal = _finite_decimal(value, name)
    if decimal <= 0:
        raise ValueError(f"{name} must be positive")
    return decimal


def _non_negative_decimal(value: object, name: str) -> Decimal:
    decimal = _finite_decimal(value, name)
    if decimal < 0:
        raise ValueError(f"{name} cannot be negative")
    return decimal


def _non_negative_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


from backend.data.binance_usdm_stream import BinanceUsdMStreamingProvider  # noqa: E402

__all__ = [
    "BINANCE_USDM_FSTREAM_BASE_URL",
    "BINANCE_USDM_PROVIDER",
    "BinanceUsdMStreamingConfig",
    "BinanceUsdMStreamingProvider",
    "BookTicker",
    "MarkPriceUpdate",
    "parse_binance_usdm_agg_trade",
    "parse_binance_usdm_book_ticker",
    "parse_binance_usdm_kline",
    "parse_binance_usdm_mark_price",
]
