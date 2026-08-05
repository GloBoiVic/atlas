# Exploration Report

## Feature 08 scope revision — Binance USDⓈ-M Futures

### Confirmed direction

- User confirmed the live-data target should be Binance USDⓈ-M Futures because the
  product should support buying/selling contracts without owning spot coins.
- Feature 07 already contains futures-style paper execution concepts.
- Feature 08's original Spot assumptions must not be carried into implementation.

### Replacements for Spot assumptions

- WebSocket transport uses current raw category routes: `/public/ws/` for high-frequency
  book-ticker data and `/market/ws/` for klines, aggregate trades, and mark-price data.
- Klines remain `@kline_<interval>` and retain the same nested payload/completion
  shape; `k.x` remains authoritative.
- Trades use Futures `@aggTrade`, not Spot `@trade`.
- Futures-specific context requires `@bookTicker` for bid/ask and
  `@markPrice@1s` for mark price, index price, funding rate, and next funding time.
- Use distinct provider identity `binance_usdm`; do not reuse historical Spot
  provider identity `binance`.
- USDⓈ-M instruments are distinct from Spot instruments even when symbols match.

### Boundary findings

- Feature 08 should normalize futures market context but must not import or depend
  on `PaperBroker` or `ExecutableMarket`.
- A provider-neutral `MarketContext` plus typed `MarketContextUpdated` event is the
  recommended boundary. Feature 09 translates it for Feature 07 execution.
- Feature 08 transports mark/index/funding values but does not apply funding,
  calculate P&L, trigger liquidation, or submit orders.
- Existing historical Binance Spot provider and Feature 03 historical assumptions
  remain unchanged in this feature.
- COIN-M/inverse futures, delivery contracts, authenticated execution, and testnet
  execution are deferred.

### Required implementation areas

1. Futures contracts/configuration and typed errors/context events.
2. Deterministic parsers for kline, aggTrade, bookTicker, and markPrice.
3. fstream subscriptions, logical subscription registry, completion gating, and
   candle deduplication across reconnects.
4. Coherent market-context aggregation with bid/ask and mark freshness.
5. Retry, cancellation, gap detection, and feed health monitoring.
6. EventBus feed runner with explicit task ownership and StrategyEngine tests.
7. Separate live-provider registry and final boundary/documentation validation.

### Risks

- Stale or missing mark price can invalidate downstream futures P&L, trigger, and
  liquidation behavior; context freshness must be explicit.
- Bid/ask and mark/index prices have different semantics and must never be mixed.
- Funding rate is a rate, not a cash amount; settlement remains outside Feature 08.
- Public streams require no credentials; no secret handling is needed.
- Historical Spot and future USDⓈ-M live data must remain provider-distinct.

### Validation

- Focused parser, provider, context, reconnect, monitor, runner, registry, and
  EventBus tests, then full backend tests.
- Ruff and changed-slice mypy.
- Frontend checks are regression-only; optional worker Docker validation follows
  `AGENTS.md` low-resource rules.
