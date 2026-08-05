# Memory — Feature 08 Live Data Streaming

Last updated: 2026-08-05

## What was built

### Previously completed

- Feature 05 Backtesting is complete and merged into `main`, including isolated
  deterministic replay, lifecycle/API/frontend, persistence, and metrics snapshots.
- Feature 06 Risk Engine and Feature 07 Execution Layer are complete and merged.
- Design-system reconciliation is complete and reviewed.

### Feature 08 — Binance USDⓈ-M Futures live streaming

- Implemented `binance_usdm` provider contracts and deterministic Decimal/UTC parsers
  for Futures kline, `@aggTrade`, `@bookTicker`, and `@markPrice@1s` data.
- Added typed keyword-only `DataFeedError`, provider-neutral `MarketContext`, and
  `MarketContextUpdated` contracts.
- Added current Binance category routing: `/market/ws/` for kline/aggTrade/markPrice
  and `/public/ws/` for bookTicker.
- Added provider-local subscriptions, `k.x` completion gating, candle deduplication
  across reconnects, bounded reconnect/backoff, error classification, cancellation
  cleanup, candle-gap detection, and Clock-injected freshness monitoring.
- Added `LiveFeedRunner`/`LiveFeedSession` as the sole EventBus publication owner,
  with event metadata, task ownership, shutdown, failure isolation, and tests.
- Added separate side-effect-free `LiveProviderRegistry` with fresh isolated
  provider instances and `binance_usdm` registration.
- Reconciled Feature 08 documentation and acceptance state with the USDⓈ-M Futures
  architecture and Feature 09/12 boundaries.

## Decisions made

- Feature 08 targets Binance **USDⓈ-M Futures**, not Spot, because Atlas should
  support long/short contract trading without requiring ownership of spot crypto.
- The architecture remains broker-agnostic: `LiveDataProvider`, `MarketContext`,
  and registry boundaries are provider-neutral; `binance_usdm` is the first adapter.
- Historical Binance Spot provider/data remains unchanged and uses provider identity
  `binance`; live USDⓈ-M uses `binance_usdm`.
- Feature 08 transports bid/ask, mark/index price, funding rate, and next funding
  time but does not apply funding, calculate P&L/liquidation, or depend on
  `PaperBroker`. Feature 09 owns pipeline translation and settlement policy.
- COIN-M, authenticated execution, bot pipeline/lifecycle, persistence, API, and
  frontend streaming remain deferred.

## Problems solved

- Corrected the initial Spot assumption after clarifying the product goal; the
  Feature 08 blueprint and source-of-truth documentation now consistently target
  USDⓈ-M Futures.
- Replaced retired legacy Futures WebSocket routing with Binance’s current
  category-based `/public/ws/` and `/market/ws/` paths.
- Preserved candle deduplication and logical subscriptions across reconnects.
- Added review fixes for typed connection factories, feed-runner formatting, and
  book/mark context drain coverage.

## Eureka moments

- Futures market data has distinct trade, executable bid/ask, mark, index, and
  funding semantics; a provider-neutral `MarketContext` is necessary to avoid
  incorrectly treating mark/index prices as fill prices.
- Keeping Feature 08 independent of `PaperBroker` preserves broker agnosticism while
  allowing Feature 09 to translate live context into futures paper execution.

## Current state

- Feature 08 is complete on branch `feature/08-live-data-streaming`.
- Implementation tip is `72fc542`; the final whole-branch review passed with zero
  Critical/Important findings and one cosmetic formatting observation.
- Validation: 419 backend tests passed; Ruff lint and mypy passed. One pre-existing
  frontend Dockerfile assertion remains failing and is unrelated to Feature 08.
- The branch is ready to merge into `main`. No Binance API key is required for the
  public market-data streams; authenticated credentials are deferred to execution.

## Next session starts with

1. Merge or otherwise integrate `feature/08-live-data-streaming` into `main`.
2. Begin exploration and architecture planning for Feature 09, especially the
   live paper-trading pipeline that maps `MarketContext` into Feature 07 execution.
3. Resolve the known pre-existing frontend Dockerfile test failure when appropriate.

## Open questions

- Whether Feature 09 should include authenticated USDⓈ-M Futures execution or retain
  the currently documented Spot testnet execution plan; decide before Feature 09
  implementation.
- Topnav 57px screenshot provenance remains unresolved; 56px remains canonical.
