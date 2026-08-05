# Feature: 08 — Live Data Streaming

## Description

Real-time Binance USDⓈ-M Futures market data feeds for live trading and paper trading.
The live feed owns CandleClosed event emission — only completed, deduplicated candles
produce events.

**Completed-candle authority:** The Binance `k.x` flag is the authoritative signal for
candle completion. Incomplete candles are never emitted as `CandleClosed`.

**No synthetic gap candles:** Data gaps are detected for observability, but the MVP never
synthesizes missing candles. Non-24/7 calendars and gap-recovery policy are deferred.
Binance crypto 24/7 candle coverage is the MVP target — gaps of more than one candle
interval are logged and surfaced via `DataFeedError`.

## Dependencies

- 03 — Data Layer (interfaces and data models)

## Deliverables

- [x] USDⓈ-M Futures provider identity, non-secret stream configuration, typed feed errors,
      provider-neutral market context contracts, and deterministic Binance parsers (Task 1)
- [x] Provider-neutral book/mark context aggregation with injectable freshness and clock
      policy (Task 3)
- [x] Bounded reconnect/backoff, cancellation-safe cleanup, completed-candle gap detection,
      and deterministic candle/book/mark freshness monitoring (Task 4)
- [x] Binance USDⓈ-M Futures streaming: WebSocket connections for live klines and trades
- [x] CandleClosed emission: Only completed candles produce events (Binance `k.x` flag)
- [x] TickReceived emission: Real-time aggregate-trade stream
- [x] Data feed management: Reconnection, subscription deduplication, health monitoring
- [x] Live data integration: Live data feeds the strategy boundary through EventBus
- [x] Separate broker-agnostic `LiveProviderRegistry` with isolated provider factories

### Task 5 completion

The `LiveFeedSession`/`LiveFeedRunner` owns provider-draining tasks and is the sole publisher of
live `CandleClosed`, `TickReceived`, `DataFeedError`, and `MarketContextUpdated` events. Sessions
preserve UTC timestamps and scope metadata, suppress incomplete/duplicate candles, await all child
tasks during shutdown, and isolate a failing feed from sibling feeds. Strategy integration remains
through EventBus subscriptions only; pipeline, execution, persistence, and transport API behavior
remain outside this feature.

`run()` owns a session until all finite drains end; callers using externally managed `start()` must
pair it with `stop()` during shutdown.

Binance Spot live streaming, OANDA streaming, and COIN-M Futures are deferred. The provider
interface remains broker-agnostic.

### Provider registry and ownership

`LiveProviderRegistry` is separate from `HistoricalProviderRegistry` and maps provider names to
side-effect-free factories. The built-in `binance_usdm` factory creates a fresh
`BinanceUsdMStreamingProvider` for each lookup, preserving per-session subscriptions and candle
deduplication state. Registration does not construct a WebSocket or any other network resource.
The registry does not change historical Spot's `binance` identity. Providers with futures-only
book/mark streams expose them through the optional live-market-context capability; the base
`LiveDataProvider` candle/tick contract remains sufficient for providers without that capability.

Feature 09 owns mode-specific pipeline assembly, translation of `MarketContext` to execution
context, funding settlement, PaperBroker integration, and authenticated execution. Feature 12
owns bot configuration, CRUD, lifecycle controls, and UI. Feature 08 does not implement those
boundaries, persistence, API/frontend behavior, COIN-M, or authenticated execution.

### Event Payload Status

`CandleClosed` and `TickReceived` already carry typed, keyword-only payloads
(`candle: Candle` and `tick: Tick`, both `field(kw_only=True)`) in
`backend/core/events.py`. The `DataFeedError` payload is owned by this feature and
must follow the same `kw_only=True` convention when implemented, carrying
`instrument_id: UUID` and `error: str`.

### Task 1 completion

Task 1 establishes `binance_usdm` identity and the public `fstream` endpoint configuration.
The parsers normalize Binance millisecond timestamps to UTC and numeric strings to exact
`Decimal` values. They validate positive prices, non-negative quantities, OHLC bounds, and
crossed books. Kline parsing preserves `k.x` as `Candle.is_complete`; transport gating and
event publication remain in later tasks. No credentials are accepted or required.

### Task 2 completion

The USDⓈ-M provider now opens injectable raw `fstream` sessions for klines, aggregate trades,
book tickers, and mark-price updates. Logical subscriptions are provider-local and release their
keys on generator exit or cancellation. Klines are yielded only after `k.x` completion and use
the mandated composite candle key for deduplication across the minimal reconnect session seam.
EventBus publication and bounded retry policy remain deferred.

### Task 3 completion

`MarketContextAggregator` retains the newest valid book and mark components and returns
`MarketContextUpdated` only when both components belong to the same instrument, are UTC,
positive/non-crossed where applicable, non-future, and fresh under injected thresholds.
Missing or stale pairs are suppressed; invalid and out-of-order updates do not replace
valid retained state, so a newer component recovers publication deterministically. The
aggregator is synchronous and creates no background tasks. `as_of` records the injected
clock reading and component timestamps are carried separately. Feature 08 transports
index/funding facts only; Feature 09 owns execution-context translation and all funding,
P&L, liquidation, trigger, and fill behavior.

## Technical Details

### Binance Streaming

The `BinanceUsdMStreamingProvider` uses the current raw public fstream category routes:

- `wss://fstream.binance.com/public/ws/{symbol}@bookTicker` for best bid/ask.
- `wss://fstream.binance.com/market/ws/{symbol}@kline_{interval}` for klines.
- `wss://fstream.binance.com/market/ws/{symbol}@aggTrade` for aggregate trades.
- `wss://fstream.binance.com/market/ws/{symbol}@markPrice@1s` for mark/index/funding context.

The provider parses and yields normalized values but never publishes directly to EventBus.
`LiveFeedRunner` is the sole publication owner. `@bookTicker` and `@markPrice@1s` are optional
market-context capabilities and are not required of every live provider.

**Binance kline parsing details:**
- The `k` object contains: `t` (open time, ms), `T` (close time, ms), `o` (open, string),
  `h` (high, string), `l` (low, string), `c` (close, string), `v` (volume, string),
  `q` (quote volume, string), `n` (trade count, int), `V` (taker buy base volume, string),
  `Q` (taker buy quote volume, string), `x` (closed, boolean).
- Timestamps are millisecond integers — convert to UTC datetime.
- Values arrive as string numerics — convert to Decimal at the adapter boundary.
- The `k.x` boolean is the authoritative signal for candle completion.
- **Volume mapping:** Binance `v` → `base_volume`, `q` → `quote_volume`, `n` → `trade_count`.
  Do not conflate `v` (traded base quantity) with OANDA's tick-volume (price-update count).
- **Price basis:** Binance klines represent trade prices; set `price_basis = "trade"`.

### Candle Deduplication

The streaming provider must track which `(instrument_id, provider, timeframe, open_time, price_basis)`
candles have already emitted `CandleClosed`. Binance may retransmit the final kline message
after the closed flag is set. Deduplication prevents duplicate events:

```python
def _is_new_candle(self, candle: Candle) -> bool:
    key = (candle.instrument_id, candle.provider, candle.timeframe,
           candle.open_time, candle.price_basis)
    if key in self._emitted_candle_closed:
        return False
    self._emitted_candle_closed.add(key)
    return True
```

### Data Feed Health Monitoring

Feed health contracts (timeout detection, stale-feed signals) are defined here.
Validation and hardening of health-monitor behavior is owned by Feature 13.

```python
class DataFeedMonitor:
    def __init__(self, event_bus: EventBus, clock: Clock):
        self.event_bus = event_bus
        self.clock = clock
        self.last_candle_time: dict[UUID, datetime] = {}
        self.timeout = timedelta(minutes=5)

    async def check_feed(self, instrument_id: UUID):
        last_time = self.last_candle_time.get(instrument_id)
        if last_time and self.clock.now() - last_time > self.timeout:
            await self.event_bus.publish(DataFeedError(
                instrument_id=instrument_id,
                error="Data feed timeout - no candles received",
            ))
```

### Reconnection

Reconnection must not produce duplicate subscriptions or duplicate events. The provider
should maintain a subscription registry and cleanly reconnect while preserving the
deduplication set:

```python
async def connect_with_reconnect(self, instrument: str, timeframe: str):
    for attempt in range(max_retries):
        try:
            async for candle in self.subscribe_candles(instrument, timeframe):
                # process candle
                pass
        except websockets.ConnectionClosed:
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            raise
```

## OANDA (Deferred)

OANDA live streaming uses the OANDA v20 `pricing` stream, which provides price updates
(bid/ask) rather than completed OHLC candles. Candle construction from live pricing data
must be designed when OANDA is scheduled. The provider interface remains broker-agnostic
(`LiveDataProvider`), but the implementation strategy differs.

## Acceptance Criteria

- [x] Only completed, deduplicated candles are emitted as CandleClosed events
- [x] Live aggregate trades are received and emitted as TickReceived events
- [x] Data feed reconnection works automatically without duplicate subscriptions
- [x] Data feed errors are handled gracefully (DataFeedError event)
- [x] Data feed health is monitored (timeout detection)
- [x] Feed timestamps are normalized to UTC and use the shared Clock for timeout decisions
- [x] Binance `k.x` flag is the authoritative candle completion signal
- [x] Candle deduplication prevents duplicate CandleClosed events

## Done when

All acceptance criteria are met.
