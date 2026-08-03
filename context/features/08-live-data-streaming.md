# Feature: 08 — Live Data Streaming

## Description

Real-time market data feeds for live trading and paper trading. The live feed owns
CandleClosed event emission — only completed, deduplicated candles produce events.

## Dependencies

- 03 — Data Layer (interfaces and data models)

## Deliverables

- [ ] Binance Spot streaming: WebSocket connection for live klines and trades
- [ ] CandleClosed emission: Only completed candles produce events (Binance `k.x` flag)
- [ ] TickReceived emission: Real-time trade stream
- [ ] Data feed management: Reconnection, subscription deduplication, health monitoring
- [ ] Live data integration: Live data feeds into strategy engine via EventBus

OANDA streaming is deferred. The provider interface remains broker-agnostic.

### Event Payload Status

`CandleClosed` and `TickReceived` already carry typed, keyword-only payloads
(`candle: Candle` and `tick: Tick`, both `field(kw_only=True)`) in
`backend/core/events.py`. The `DataFeedError` payload remains owned by this feature and
must follow the same `kw_only=True` convention when implemented, carrying
`instrument_id: UUID` and `error: str`.

## Technical Details

### Binance Streaming

```python
class BinanceStreamingProvider(LiveDataProvider):
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus

    async def subscribe_candles(self, instrument: str, timeframe: str) -> AsyncGenerator[Candle, None]:
        symbol = self._to_binance_symbol(instrument)
        interval = self._to_binance_interval(timeframe)
        ws_url = f"wss://stream.binance.com:9443/ws/{symbol.lower()}@kline_{interval}"
        async with websockets.connect(ws_url) as ws:
            async for message in ws:
                data = json.loads(message)
                kline = data["k"]
                candle = self._parse_kline(kline, instrument, timeframe)

                # Emit CandleClosed only when the kline's closed flag is true
                # and the candle hasn't been emitted before.
                if kline["x"] and self._is_new_candle(candle):
                    await self.event_bus.publish(CandleClosed(
                        candle=candle,
                    ))

                yield candle

    async def subscribe_ticks(self, instrument: str) -> AsyncGenerator[Tick, None]:
        symbol = self._to_binance_symbol(instrument)
        ws_url = f"wss://stream.binance.com:9443/ws/{symbol.lower()}@trade"
        async with websockets.connect(ws_url) as ws:
            async for message in ws:
                data = json.loads(message)
                tick = self._parse_tick(data)
                await self.event_bus.publish(TickReceived(
                    tick=tick,
                ))
                yield tick
```

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

```python
class DataFeedMonitor:
    def __init__(self, event_bus: EventBus, clock: Clock):
        self.event_bus = event_bus
        self.clock = clock
        self.last_candle_time: dict[str, datetime] = {}
        self.timeout = timedelta(minutes=5)

    async def check_feed(self, instrument: str):
        last_time = self.last_candle_time.get(instrument)
        if last_time and self.clock.now() - last_time > self.timeout:
            await self.event_bus.publish(DataFeedError(
                instrument=instrument,
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

- [ ] Only completed, deduplicated candles are emitted as CandleClosed events
- [ ] Live ticks are received and emitted as TickReceived events
- [ ] Data feed reconnection works automatically without duplicate subscriptions
- [ ] Data feed errors are handled gracefully (DataFeedError event)
- [ ] Data feed health is monitored (timeout detection)
- [ ] Feed timestamps are normalized to UTC and use the shared Clock for timeout decisions
- [ ] Binance `k.x` flag is the authoritative candle completion signal
- [ ] Candle deduplication prevents duplicate CandleClosed events

## Done when

All acceptance criteria are met.
