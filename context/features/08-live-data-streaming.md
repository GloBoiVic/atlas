# Feature: 08 — Live Data Streaming

## Description

Real-time market data feeds for live trading and paper trading.

## Dependencies

- 03 — Data Layer

## Deliverables

- [ ] Binance Spot streaming: WebSocket connection for live candles and trades
- [ ] Data feed management: Reconnection, health monitoring
- [ ] TickReceived event: Emitted for real-time price updates
- [ ] Live data integration: Live data feeds into strategy engine

Oanda streaming is deferred. The provider interface remains broker-agnostic.

## Technical Details

Oanda streaming is deferred. Its provider-specific protocol will be documented when that integration is scheduled.

### Binance Streaming

```python
class BinanceStreamingProvider:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus

    async def subscribe_candles(self, instrument: str, timeframe: str):
        symbol = self._to_binance_symbol(instrument)
        ws = await websockets.connect(
            f"wss://stream.binance.com:9443/ws/{symbol.lower()}@kline_{timeframe}"
        )
        async for message in ws:
            data = json.loads(message)
            candle = self._parse_candle(data)
            if data["k"]["x"] and self._is_new_candle(candle):
                await self.event_bus.publish(CandleClosed(candle=candle))

    async def subscribe_ticks(self, instrument: str):
        symbol = self._to_binance_symbol(instrument)
        ws = await websockets.connect(
            f"wss://stream.binance.com:9443/ws/{symbol.lower()}@trade"
        )
        async for message in ws:
            data = json.loads(message)
            tick = self._parse_tick(data)
            await self.event_bus.publish(TickReceived(tick=tick))
```

### Data Feed Health Monitoring

```python
class DataFeedMonitor:
    def __init__(self, event_bus: EventBus, clock: Clock):
        self.event_bus = event_bus
        self.clock = clock
        self.last_candle_time = {}
        self.timeout = timedelta(minutes=5)

    async def check_feed(self, instrument: str):
        last_time = self.last_candle_time.get(instrument)
        if last_time and self.clock.now() - last_time > self.timeout:
            await self.event_bus.publish(DataFeedError(
                instrument=instrument,
                error="Data feed timeout - no candles received"
            ))
```

## Acceptance Criteria

- [ ] Only completed, deduplicated candles are emitted as CandleClosed events
- [ ] Live ticks are received and emitted as TickReceived events
- [ ] Data feed reconnection works automatically
- [ ] Data feed errors are handled gracefully
- [ ] Data feed health is monitored
- [ ] Feed timestamps are normalized to UTC and use the shared Clock for timeout decisions
- [ ] Reconnects do not duplicate subscriptions or candles

## Done when

All acceptance criteria are met.
