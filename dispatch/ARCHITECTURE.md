# Architecture

## Feature 08 — Live Data Streaming (authoritative)

Feature 08 provides broker-agnostic live market-data contracts and a Binance
**USDⓈ-M Futures** public-stream implementation. It covers completed futures
klines, aggregate trades, best bid/ask, mark/index/funding context, normalization,
EventBus publication, reconnection, deduplication, gap detection, and feed health.

It does not cover authenticated execution, paper-broker behavior, bot lifecycle,
persistence, API/frontend work, or Binance COIN-M Futures. Existing historical
Binance Spot provider assumptions remain unchanged.

### Provider and instrument identity

- Target linear USDⓈ-M contracts such as `BTCUSDT` and `ETHUSDT`.
- Use provider identity `binance_usdm` and implementation `BinanceUsdMStreamingProvider`.
- USDⓈ-M instruments are distinct records from historical Spot instruments.
- Provider metadata may describe contract type, margin/settlement asset, multiplier,
  tick/step constraints, and leverage limits; execution/risk use remains downstream.

### Streams and semantics

- Use current raw public fstream routes: `wss://fstream.binance.com/public/ws/{stream}` for
  high-frequency streams such as `@bookTicker`, and
  `wss://fstream.binance.com/market/ws/{stream}` for regular market streams.
- Subscribe separately to `{symbol}@kline_{interval}`, `{symbol}@aggTrade`,
  `{symbol}@bookTicker`, and `{symbol}@markPrice@1s`.
- Kline fields map to existing `Candle` fields with Decimal values, UTC timestamps,
  `price_basis="trade"`, and `provider="binance_usdm"`.
- `k.x` is the sole completion authority; incomplete candles never emit or cross
  the completed-candle interface.
- `@aggTrade` maps aggregate price/quantity/time into the existing `Tick`; do not
  expand `Tick` solely for exchange aggregate-trade IDs.
- `@bookTicker` supplies executable bid/ask context. `@markPrice@1s` supplies mark
  price, index price, funding rate, and next funding time.
- Mark/index/funding values are never treated as executable prices. Feature 08
  transports and validates them but does not apply funding or calculate P&L,
  liquidation, triggers, or fills.

### Market-context boundary

Add provider-neutral `MarketContext` and typed `MarketContextUpdated` contracts
containing at least instrument/provider, bid, ask, mark price, index price, funding
rate, next funding time, freshness/as-of timestamps, and component timestamps.
Require a coherent fresh bid/ask/mark snapshot; reject crossed/non-positive/stale
components. Feature 08 must not import `PaperBroker` or `ExecutableMarket`.
Feature 09 translates `MarketContext` into the Feature 07 execution-facing context.

### Provider/EventBus ownership

- Preserve the existing async-generator `LiveDataProvider` candle/tick contract;
  add an optional live-market-context capability rather than forcing all providers
  to implement futures context.
- The provider parses, normalizes, tracks subscriptions, and holds dedup state but
  does not publish directly to the shared EventBus.
- A Feature 08 `LiveFeedRunner` owns provider-draining tasks, context aggregation,
  EventBus publication, health monitors, cancellation, and cleanup. It is the sole
  publication owner and does not implement a concrete `BotPipeline`.
- Add a separate `LiveProviderRegistry`; never couple it to the historical registry.

The live registry maps provider names to side-effect-free factories, not shared provider
instances. Each lookup creates a fresh provider so subscription and candle-deduplication state
cannot cross bot/feed sessions. Registering `binance_usdm` does not open a WebSocket or alter the
historical Spot registry's `binance` identity. Context streams are an optional capability in
addition to the base candle/tick provider contract.

### Deduplication and subscriptions

- Completed candle key: `(instrument_id, provider, timeframe, open_time, price_basis)`.
- Preserve dedup state across reconnects; conflicting duplicates are logged and not
  re-emitted.
- Logical subscription keys are separate for candle, aggregate trade, book ticker,
  and mark price. Duplicate active subscriptions fail deterministically and cleanup
  releases keys on normal exit, cancellation, or fatal failure.

### Reconnection, errors, gaps, and health

- Use `websockets.asyncio.client.connect` with injected connection factory, retry
  limits, sleeper/backoff, and transport settings.
- Retry transient transport failures only; cancellation, invalid configuration, and
  invalid protocol/schema terminate without retry. Exhaustion publishes one typed
  `DataFeedError(instrument_id, error)` and terminates only that feed.
- Malformed individual messages are logged and surfaced without tearing down a
  healthy connection where possible. Cancellation re-raises without error events.
- Detect skipped completed-candle intervals, surface `gap_detected`, accept valid
  current candles, and never synthesize or REST-backfill candles.
- Monitor candle, book-ticker, and mark/context freshness using injected `Clock`.
  Emit one timeout error per stale episode and reset after recovery; runner owns
  monitor tasks and awaits them during shutdown.

### Ownership boundaries

- Feature 08: WebSockets, parsing, normalization, context aggregation, retries,
  subscriptions, candle deduplication, feed errors, freshness, and EventBus feed
  runner.
- Feature 09: mode-specific pipeline assembly, StrategyEngine warm-up, mapping
  `MarketContext` to Feature 07 PaperBroker, funding settlement policy, and any
  authenticated execution scope.
- Feature 12: bot CRUD/lifecycle/UI and supervisor-facing configuration.
- COIN-M, inverse/delivery contracts, Spot live streaming, authenticated Futures
  execution, REST backfill, order-book depth, database persistence, and frontend
  streaming are non-goals.

### Vertical slices

1. Contracts/configuration: `DataFeedError`, futures identity, `MarketContext`,
   `MarketContextUpdated`, and live registry capability.
2. Deterministic parsers: kline, aggTrade, bookTicker, markPrice, Decimal/UTC and
   validation tests.
3. Provider subscriptions: fstream URLs, logical subscriptions, k.x gating,
   candle deduplication.
4. Context aggregation: coherent bid/ask/mark/index/funding snapshots and freshness.
5. Reconnect/cancellation: failure classification, bounded retry, exhaustion,
   cleanup, and isolation.
6. Gap/health monitoring: interval gaps and stale-episode behavior.
7. EventBus runner: one publication owner, task ownership, StrategyEngine tests,
   and context event integration without PaperBroker coupling.
8. Registry, acceptance documentation, full validation, and review.

### Invariants

1. `k.x == false` never emits `CandleClosed`.
2. Futures candles use trade-price semantics and `provider="binance_usdm"`.
3. `@aggTrade`, not `@trade`, is the tick source.
4. Candle keys emit at most once per feed context, including reconnects.
5. Fresh executable bid/ask and mark price are required for market-context snapshots.
6. Index/funding are not executable prices; Feature 08 does not settle funding.
7. No credentials are required for public streams.
8. Feature 08 does not depend on `PaperBroker` or alter historical Spot behavior.
9. Cancellation is never retry/error; tasks are explicitly owned and awaited.
10. No missing candles are synthesized or REST-backfilled.

### Validation

Run focused parser/provider/context/reconnect/monitor/runner/registry/EventBus tests,
then full backend tests, Ruff, and changed-slice mypy. Frontend checks are
regression-only; optional worker/container validation follows `AGENTS.md`.
