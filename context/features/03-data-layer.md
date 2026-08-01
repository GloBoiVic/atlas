# Feature: 03 — Data Layer

## Description

Fetch, normalize, and store market data. CSV provider for backtesting, API providers for live data.

## Dependencies

- 02 — Core Infrastructure

## Deliverables

- [ ] DataProvider interface defined
- [ ] Data models: Candle, Tick, Instrument
- [ ] CSV DataProvider: Load historical OHLC data from CSV files
- [ ] Historical data loader: Bulk import candles to PostgreSQL
- [ ] Candle storage pipeline: Fetch → Store → Emit CandleClosed event
- [ ] Binance DataProvider: Fetch historical Spot candles via ccxt
- [ ] Provider registry: Keep broker-specific data access behind the common interface

## Technical Details

### DataProvider Interface

```python
from collections.abc import AsyncGenerator

class DataProvider(ABC):
    @abstractmethod
    async def get_historical_candles(
        self, instrument: str, timeframe: str,
        start: datetime, end: datetime
    ) -> list[Candle]

    @abstractmethod
    async def subscribe_live_candles(
        self, instrument: str, timeframe: str
    ) -> AsyncGenerator[Candle, None]

    @abstractmethod
    async def subscribe_ticks(
        self, instrument: str
    ) -> AsyncGenerator[Tick, None]
```

### Data Models

```python
class Candle:
    instrument: str
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    timeframe: str

class Tick:
    instrument: str
    timestamp: datetime
    bid: Decimal
    ask: Decimal

class Instrument:
    name: str
    type: str  # forex, crypto, futures
    pip_location: int
    display_precision: int
```

### CSV Data Provider

```python
class CSVDataProvider(DataProvider):
    def __init__(self, data_dir: str):
        self.data_dir = data_dir

    async def get_historical_candles(
        self, instrument: str, timeframe: str,
        start: datetime, end: datetime
    ) -> list[Candle]:
        file_path = f"{self.data_dir}/{instrument}_{timeframe}.csv"
        # File parsing runs outside the async event loop in the implementation.
        ...
```

### Binance Data Provider

```python
class BinanceDataProvider(DataProvider):
    def __init__(self):
        self.exchange = ccxt.async_support.binance()

    async def get_historical_candles(
        self, instrument: str, timeframe: str,
        start: datetime, end: datetime
    ) -> list[Candle]:
        # ccxt fetch_ohlcv
        ...
```

### Historical Data Loader

```python
class HistoricalDataLoader:
    def __init__(self, provider: DataProvider, repository: CandleRepository):
        self.provider = provider
        self.repository = repository

    async def load(
        self, instrument: str, timeframe: str,
        start: datetime, end: datetime
    ):
        candles = await self.provider.get_historical_candles(
            instrument, timeframe, start, end
        )
        await self.repository.save_many(candles)
```

## Acceptance Criteria

- [ ] CSV provider loads validated historical candles and emits CandleClosed events
- [ ] Binance provider fetches normalized candles from the public Spot API
- [ ] All providers normalize timestamps, ordering, duplicates, precision, and Decimal values
- [ ] Historical data persists in PostgreSQL
- [ ] Data loader handles bulk imports efficiently
- [ ] Live providers emit only completed candles and deduplicate by instrument/timeframe/timestamp

## Done when

All acceptance criteria are met.
