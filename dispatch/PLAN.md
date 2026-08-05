# Plan

## Feature 08 — Binance USDⓈ-M Futures Live Data Streaming

### Gate status

- Exploration complete and recorded in `EXPLORATION.md`.
- Revised architecture recorded in `ARCHITECTURE.md`.
- Revised futures blueprint confirmed; implementation slices are complete through the
  registry/documentation gate.

### Planned sequence

1. Reconcile Feature 08/context documentation and create
   `feature/08-live-data-streaming` from current `main`.
2. Implement typed futures feed contracts/configuration and deterministic parsers.
3. Implement fstream subscriptions, completion gating, and candle deduplication.
4. Implement market-context aggregation for bid/ask, mark/index/funding data.
5. Implement reconnection, cancellation, gap detection, and health monitoring.
6. Implement EventBus feed runner with explicit task ownership and isolation.
7. Add live-provider registry and finalize acceptance documentation.
8. Review each slice, fix findings, and run focused/full validation.

### Explicit non-goals

No Spot live feed, COIN-M Futures, authenticated orders, PaperBroker changes,
funding settlement, bot pipeline/lifecycle, persistence, API, frontend, or REST
historical backfill in Feature 08.
