"""Domain data models shared across providers, persistence, and events.

All models use ``UUID`` for identifiers, ``Decimal`` for monetary values and volumes,
and ``datetime`` (UTC) for timestamps.  ``Candle`` is provider-domain only — it does
**not** carry a database-generated row identifier.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Instrument:
    """Provider-aware instrument reference.

    Example constraints (Binance):
      {"min_qty":"0.001","step_size":"0.001","tick_size":"0.01","min_notional":"10"}

    Example constraints (OANDA, deferred):
      {"margin_rate":"0.05","display_precision":5,"trade_units_precision":0,"pip_location":-4}
    """

    id: UUID
    symbol: str  # normalized, e.g. "BTCUSDT"
    provider: str  # "binance", "oanda"
    asset_type: str  # "crypto", "forex"
    base_currency: str | None = None
    quote_currency: str | None = None
    price_precision: int = 8
    quantity_precision: int = 8
    is_active: bool = True
    constraints: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Candle:
    """Provider-domain OHLC candle — no database row id.

    ``open_time`` is the start of the interval in UTC.  ``is_complete`` is ``True`` for
    every historical candle and ``False`` for an in-progress streaming update.
    """

    instrument_id: UUID
    provider: str  # "binance", "oanda", "csv"
    timeframe: str  # "1m", "5m", "1h", "4h", "1d"
    open_time: datetime  # start of the interval, UTC
    close_time: datetime | None = None  # end of interval
    price_basis: str = "trade"  # "trade", "mid", "bid", "ask"
    open: Decimal = Decimal("0")
    high: Decimal = Decimal("0")
    low: Decimal = Decimal("0")
    close: Decimal = Decimal("0")
    base_volume: Decimal = Decimal("0")  # traded base asset quantity
    quote_volume: Decimal | None = None  # quote asset volume (Binance)
    trade_count: int | None = None  # number of trades (Binance)
    taker_buy_base_volume: Decimal | None = None
    taker_buy_quote_volume: Decimal | None = None
    tick_volume: int | None = None  # price-update count (OANDA)
    is_complete: bool = True


@dataclass(frozen=True, slots=True)
class Tick:
    """A single price/tick update for an instrument."""

    instrument_id: UUID
    timestamp: datetime
    price: Decimal
    base_volume: Decimal | None = None
    tick_volume: int | None = None  # OANDA price-update count


@dataclass(frozen=True, slots=True)
class DatasetIdentity:
    """Fingerprint for reproducible backtest runs.

    The ``id`` is a stable hash over the instrument, timeframe, candle window,
    and source — the same inputs always produce the same fingerprint.
    """

    id: str  # fingerprint hash
    instrument_id: UUID
    timeframe: str
    start: datetime
    end: datetime
    candle_count: int
    source: str  # "csv", "binance"


@dataclass(frozen=True, slots=True)
class HistoricalLoadResult:
    """Returned by the historical data loader after bulk import."""

    dataset: DatasetIdentity
    inserted_count: int  # rows actually inserted after dedup
