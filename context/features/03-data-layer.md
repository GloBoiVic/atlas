# Feature: 03 — Data Layer

## Description

Fetch, normalize, and store market data. CSV provider for backtesting, API providers for live data.

**This feature covers historical data ingestion only.** Live streaming (WebSocket feeds and
CandleClosed event emission) is owned by Feature 08. The historical data loader does not
emit CandleClosed events — it persists candles into the database and returns them for
replay.

## Dependencies

- 02 — Core Infrastructure

## Deliverables

- [x] HistoricalDataProvider interface (returns bounded list of candles)
- [x] LiveDataProvider interface (async generator — interface only;
      implementation in Feature 08)
- [x] Data models: Candle, Tick, Instrument (provider-aware), DatasetIdentity
- [x] CSV DataProvider: Load historical OHLC data from CSV files
- [x] Historical data loader: Bulk import candles to PostgreSQL
- [x] Candle persistence with `(instrument_id, provider, timeframe, open_time, price_basis)`
      uniqueness and explicit volume field semantics
- [x] Binance DataProvider: Fetch historical Spot klines via async ccxt
- [x] Instrument provider: Provider-aware instruments with provider-specific constraints
      stored as JSONB metadata
- [x] Dataset identity/fingerprint for reproducible backtests

## Technical Details

### Domain Model Principles

- **UUID identity is the target.** Domain models use `UUID` for identifiers. New code must
  use `UUID`, not `str`.
- **Instruments are provider-aware.** Candles reference an `instrument_id` rather than
  duplicating fragile symbol strings. Uniqueness is scoped to
  `(instrument_id, provider, timeframe, open_time, price_basis)`.
- **Open-time semantics.** `open_time` is the start of the interval (UTC).
- **All monetary values are Decimal.** Providers normalize string or float values at the
  adapter boundary.
- **`price_basis`** identifies the price source: `"trade"` for Binance (trade prices),
  `"mid"`, `"bid"`, or `"ask"` for OANDA.
- **Volume semantics are explicit and provider-specific:**
  - `base_volume`: Traded quantity of the base asset (Binance kline `v`).
  - `quote_volume`: Traded quantity of the quote asset (Binance kline `q`).
  - `trade_count`: Number of trades (Binance kline `n`).
  - `tick_volume`: Number of price updates (OANDA volume) — **not** the same as
    `base_volume`. Do not conflate tick-count with traded quantity.
- **`is_complete`** distinguishes a finished candle from an in-progress streaming update.
  Historical data always sets `is_complete = True`.

### Separate Historical and Live Interfaces

```python
from collections.abc import AsyncGenerator
from abc import ABC, abstractmethod

class HistoricalDataProvider(ABC):
    """Returns a bounded list of completed candles."""

    @abstractmethod
    async def get_historical_candles(
        self, instrument: Instrument, timeframe: str,
        start: datetime, end: datetime
    ) -> list[Candle]:
        ...

class LiveDataProvider(ABC):
    """Emits streaming candles and ticks.

    Defined here for interface completeness; implementation is owned by
    Feature 08.  Accepts a resolved Instrument (not a raw symbol string)
    so that symbol resolution stays centralised — the same convention
    used by HistoricalDataProvider.
    """

    @abstractmethod
    async def subscribe_candles(
        self, instrument: Instrument, timeframe: str
    ) -> AsyncGenerator[Candle, None]:
        ...

    @abstractmethod
    async def subscribe_ticks(
        self, instrument: Instrument
    ) -> AsyncGenerator[Tick, None]:
        ...
```

### Data Models

The domain `Candle` models a provider-parsed candle.  It does **not** carry
a database-generated row identifier — that identity belongs to the persisted
record (see `candles` table below, where `id UUID DEFAULT gen_random_uuid()`).
There is no `id` field on the domain model.  If replay or tracing needs an
identifier for a candle retrieved from storage, that is a persisted-record
concern (e.g. the ORM row's `id` column), not a required provider-domain
field.

```python
from dataclasses import dataclass, field

@dataclass(frozen=True, slots=True)
class Candle:
    instrument_id: UUID              # FK to Instrument
    provider: str                    # "binance", "oanda", "csv"
    timeframe: str                   # "1m", "5m", "1h", etc.
    open_time: datetime              # start of the interval, UTC
    close_time: datetime | None      # end of interval (Binance kline T)
    price_basis: str                 # "trade", "mid", "bid", "ask"
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    base_volume: Decimal             # traded base asset quantity
    quote_volume: Decimal | None     # quote asset volume (Binance)
    trade_count: int | None          # number of trades (Binance)
    taker_buy_base_volume: Decimal | None
    taker_buy_quote_volume: Decimal | None
    tick_volume: int | None          # price-update count (OANDA)
    is_complete: bool

@dataclass(frozen=True, slots=True)
class Tick:
    instrument_id: UUID
    timestamp: datetime
    price: Decimal
    base_volume: Decimal | None
    tick_volume: int | None          # OANDA: price-update count

@dataclass(frozen=True, slots=True)
class Instrument:
    id: UUID
    symbol: str                      # normalized, e.g. "BTCUSDT"
    provider: str                    # "binance", "oanda"
    asset_type: str                  # "crypto", "forex"
    base_currency: str | None
    quote_currency: str | None
    price_precision: int
    quantity_precision: int
    constraints: dict                # provider-specific metadata as JSONB
    # Binance example:
    #   {"min_qty": "0.001", "step_size": "0.001", "tick_size": "0.01",
    #    "min_notional": "10"}
    # OANDA example:
    #   {"margin_rate": "0.05", "display_precision": 5,
    #    "trade_units_precision": 0, "pip_location": -4}

@dataclass(frozen=True, slots=True)
class DatasetIdentity:
    id: str                          # fingerprint hash
    instrument_id: UUID
    timeframe: str
    start: datetime
    end: datetime
    candle_count: int
    source: str                      # "csv", "binance"

@dataclass(frozen=True, slots=True)
class HistoricalLoadResult:
    """Returned by the historical data loader after bulk import.

    The dataset identity enables reproducible backtests — the same
    (instrument, provider, timeframe, start, end, source) always
    produces the same fingerprint hash.
    """
    dataset: DatasetIdentity
    inserted_count: int              # rows actually inserted after dedup
```

### CSV Data Provider

```python
class CSVDataProvider(HistoricalDataProvider):
    def __init__(self, data_dir: str):
        self.data_dir = data_dir

    async def get_historical_candles(
        self, instrument: Instrument, timeframe: str,
        start: datetime, end: datetime
    ) -> list[Candle]:
        # File parsing runs outside the async event loop.
        # Uses instrument.symbol to locate the CSV file and
        # instrument.provider for the expected data format.
        # Returns sorted, deduplicated, Decimal-normalized candles
        # with price_basis="trade" and is_complete=True.
        ...
```

### Binance Historical Provider

```python
class BinanceHistoricalProvider(HistoricalDataProvider):
    def __init__(self, *, clock: Clock, timeout_policy: BinanceTimeoutPolicy):
        self.clock = clock
        self.timeout_policy = timeout_policy
        self.exchange = ccxt.async_support.binance({"timeout": 10000})

    async def get_historical_candles(
        self, instrument: Instrument, timeframe: str,
        start: datetime, end: datetime
    ) -> list[Candle]:
        # Uses instrument.symbol for the ccxt market symbol and
        # instrument.provider to select the exchange adapter.
        # ccxt fetch_ohlcv returns: [timestamp_ms, open, high, low, close, volume]
        # timestamp is the kline open time in milliseconds → UTC datetime.
        # Volume values arrive as floats → Decimal at the adapter boundary.
        # price_basis = "trade", is_complete = True.
        ...
```

**Binance kline specifics:**
- `fetch_ohlcv` returns `[timestamp, open, high, low, close, volume]` where `timestamp` is
  the kline open time in milliseconds and `volume` is base asset volume.
- The full kline from Binance REST API includes `quoteVolume`, `count` (trade count),
  `takerBuyBaseVolume`, `takerBuyQuoteVolume`.
- Instrument constraints from `exchangeInfo` include `LOT_SIZE` (minQty, maxQty, stepSize),
  `PRICE_FILTER` (minPrice, maxPrice, tickSize), `MIN_NOTIONAL`. These are stored as the
  `constraints` JSONB metadata on the `Instrument` model.

### Binance historical timeout contract

- The provider receives a `Clock`; production composition supplies `LiveClock`, while tests may
  supply a controllable clock. The clock is used for observable/domain-time deadline decisions.
- Actual async transport cancellation is independent of `SimulationClock`: each ccxt page request
  has a 10-second default timeout, and the complete pagination operation has a 600-second default
  timeout. Both values are constructor-injected through `BinanceTimeoutPolicy`.
- Timeout and cancellation paths close the ccxt exchange in the existing `finally` block and never
  return candles collected before a failed operation.

### OANDA (Deferred)

OANDA data integration is deferred. When scheduled:

- Timestamps are RFC3339 (not millisecond integers).
- OHLC can be bid, ask, or mid — `price_basis` distinguishes them.
- Volume is `tick_volume` (number of price changes), not traded asset volume.
- OANDA live pricing is a stream of price updates (`PricingStream`), not completed OHLC
  candles. Candle construction from live pricing data is a deferred design concern.
- Instrument constraints differ from Binance: `marginRate`, `displayPrecision`,
  `tradeUnitsPrecision`, `pipLocation`. These are stored in the `constraints` JSONB
  metadata field — not flattened into the same columns as Binance constraints.

### Candle Persistence

```sql
CREATE TABLE candles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instrument_id UUID NOT NULL REFERENCES instruments(id),
    provider VARCHAR(50) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    open_time TIMESTAMP WITH TIME ZONE NOT NULL,
    close_time TIMESTAMP WITH TIME ZONE,
    price_basis VARCHAR(10) NOT NULL DEFAULT 'trade',
    open NUMERIC(20, 8) NOT NULL,
    high NUMERIC(20, 8) NOT NULL,
    low NUMERIC(20, 8) NOT NULL,
    close NUMERIC(20, 8) NOT NULL,
    base_volume NUMERIC(20, 8) NOT NULL DEFAULT 0,
    quote_volume NUMERIC(20, 8),
    trade_count INT,
    taker_buy_base_volume NUMERIC(20, 8),
    taker_buy_quote_volume NUMERIC(20, 8),
    tick_volume BIGINT,
    is_complete BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(instrument_id, provider, timeframe, open_time, price_basis)
);
```

### Candle Repository

```python
from typing import Protocol

class CandleRepository(Protocol):
    """Bulk-insert candles with conflict-safe no-op deduplication.
    Returns count of rows actually inserted — not the requested batch
    size."""

    async def save_many(self, candles: list[Candle]) -> int:
        """
        Inserts candle rows. On a unique-violation conflict
        (instrument_id, provider, timeframe, open_time, price_basis),
        the existing row is retained (no-op — DO NOTHING, not
        DO UPDATE). Returns the number of rows that were *inserted*,
        not the total batch size.
        """
        ...

The conflict behaviour is deliberately a no-op (ON CONFLICT DO NOTHING) rather
than an upsert (ON CONFLICT DO UPDATE) because historical candles are immutable
once persisted. A row that already exists is guaranteed identical to the
incoming row for the same uniqueness key — there is nothing to update.

### Dataset Identity

```python
class DatasetIdentity:
    """Fingerprint for reproducible backtest runs."""
    id: str    # hash of instrument_id + timeframe + sorted candle window
    # ...
```

### Instrument Upsert Flow

Before fetching or persisting any candle data, the caller must resolve the
`Instrument` record via the following flow:

1. **Resolve provider metadata.** Obtain exchange metadata (e.g. Binance
   `exchangeInfo` for LOT_SIZE, PRICE_FILTER, MIN_NOTIONAL) or CSV schema
   defaults.
2. **Upsert / get-or-create** an `Instrument` row keyed on
   `(provider, symbol)`. If the row exists, update the `constraints` JSONB
   and `is_active` flag; otherwise insert.
3. **Obtain `instrument_id`** from the upserted or fetched `Instrument`.
4. **Fetch** raw market data through the provider (CSV file, ccxt OHLCV).
5. **Normalize** raw values to the `Candle` domain model (UTC timestamps,
   `Decimal` prices/volumes, `price_basis`, `is_complete=True`).
6. **Persist** the normalized candles via `CandleRepository.save_many()`.

```python
async def load_historical_data(
    *,
    provider: HistoricalDataProvider,
    instrument_repo: InstrumentRepository,
    candle_repo: CandleRepository,
    symbol: str,
    provider_name: str,
    timeframe: str,
    start: datetime,
    end: datetime,
) -> HistoricalLoadResult:
    # Step 1-2: Resolve or create the instrument
    instrument = await instrument_repo.resolve(
        symbol=symbol, provider=provider_name,
    )
    # Step 4-5: Fetch and normalize
    candles = await provider.get_historical_candles(
        instrument=instrument, timeframe=timeframe,
        start=start, end=end,
    )
    # Step 6: Bulk persist (returns inserted count)
    inserted = await candle_repo.save_many(candles)
    # Build and return the result with fingerprint
    dataset = build_dataset_identity(
        instrument.id, timeframe, start, end, len(candles), provider_name,
    )
    return HistoricalLoadResult(dataset=dataset, inserted_count=inserted)
```

**Important:** The `HistoricalDataProvider.get_historical_candles` method
receives a fully-resolved `Instrument` object, not a raw symbol string.
The provider uses `instrument.symbol` for the exchange market key and
`instrument.provider` to select the correct adapter or file directory.
This keeps symbol resolution centralised in the data loader rather than
dispersed across every provider implementation.

### Migration Plan (Migrations 005 and 006)

Alembic migration history is immutable — no existing migrations are rewritten
or deleted. Two new migrations serve Feature 03:

**Migration 005 — UUID Identity Migration**
- Converts existing `String(36)` primary-key and foreign-key columns to native
  PostgreSQL `UUID` across: `accounts`, `strategies`, `strategy_versions`,
  `bots`, and `reconciliation_runs`.
- Uses `ALTER COLUMN ... TYPE UUID USING ...` with explicit casting from the
  existing `VARCHAR(36)` representation.
- Foreign-key constraints are dropped before column type changes and recreated
  after.
- **Requires** upgrade and downgrade tests verified against a Codespace
  PostgreSQL instance (not SQLite, which cannot execute this migration).

**Migration 006 — Instruments and Candles**
- Creates `instruments` table with the schema documented in this feature.
- Creates `candles` table with the schema documented in this feature.
- Creates the `idx_candles_lookup` index.
- All columns use native PostgreSQL `UUID` (no `String(36)` gap).
- **Requires** upgrade and downgrade tests verified against Codespace
  PostgreSQL.

Both migrations must be validated in the **single** shared Codespace on
`main` (no per-branch Codespaces). Validate the pushed branch by checking it
out in the existing Codespace, then return to `main`.

### Event Payload Convention

The `CandleClosed` event carries a `candle: Candle` payload and `TickReceived` carries
a `tick: Tick` payload — both implemented during the Feature 03 foundation slice with
**keyword-only dataclass fields** to avoid inheritance ordering failures when a parent
`DomainEvent` declares positional defaults:

```python
from dataclasses import dataclass, field

@dataclass(frozen=True, slots=True)
class CandleClosed(DomainEvent):
    candle: Candle = field(kw_only=True)
```

This applies to **all** domain event payload fields — not just `CandleClosed`. The
`kw_only=True` convention prevents the brittle default-field ordering problem that occurs
when a subclass adds a field before a parent's optional field. Every payload-bearing
domain event must follow this pattern.

Downstream payload-bearing events (SignalGenerated, OrderSubmitted, OrderFilled, etc.)
remain stubs owned by later features.

## Acceptance Criteria

- [x] CSV provider loads validated historical candles (sorted, deduplicated, Decimal values,
      is_complete=True, price_basis="trade")
- [x] Binance historical provider fetches normalized candles from the public Spot API
- [x] Providers normalize timestamps to UTC
- [x] Historical data persists in PostgreSQL with
      `(instrument_id, provider, timeframe, open_time, price_basis)` uniqueness
- [x] Volume fields use explicit semantics: ccxt OHLCV maps only to base_volume; unavailable
      quote/trade/taker fields remain null
- [x] Data loader returns a DatasetIdentity fingerprint for reproducible backtests
- [x] Historical loader does not emit CandleClosed events
- [x] Instruments are provider-aware with provider-specific constraints stored as JSONB
- [x] Live streaming interface is defined but not implemented (Feature 08)
- [x] Event payload types are populated (CandleClosed carries candle field) before 03/04
      integration
- [x] Binance historical pagination has constructor-injected 10-second page and 600-second
      overall timeouts, with Clock-based domain deadlines kept separate from transport cancellation

## Done when

All acceptance criteria are met.

---

**Completed 2026-08-02.** Commit `ec70874`. All acceptance criteria verified.
PostgreSQL/Codespace validation: migrations 005/006 upgrade → downgrade → re-upgrade
passed, `alembic current` at 006, repository smoke test passed against live PostgreSQL,
health check passed, 218 tests passing, ruff/mypy clean.
