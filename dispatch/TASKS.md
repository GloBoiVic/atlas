# Task Ledger

| Task | Agent | Status |
|---|---|---|
| 1. Contracts, configuration, and deterministic Futures parsers | backend | COMPLETE |
| 2. Fstream subscriptions, completion gating, and candle deduplication | backend | COMPLETE |
| 3. Market-context aggregation and freshness | backend | COMPLETE |
| 4. Reconnect, cancellation, gaps, and health monitoring | backend | COMPLETE |
| 5. EventBus feed runner and integration tests | backend | PENDING |
| 6. Live-provider registry and documentation gate | backend | PENDING |
| 7. Final validation and whole-branch review | reviewer | PENDING |

### Task 1 brief

Implement only the first vertical slice from `dispatch/PLAN.md` and
`dispatch/ARCHITECTURE.md`: establish the USDⓈ-M Futures provider identity and
typed non-secret streaming configuration; add the keyword-only `DataFeedError`
payload; add provider-neutral `MarketContext` and `MarketContextUpdated` contracts
if they are required as foundations; implement deterministic parsers and tests for
`@kline`, `@aggTrade`, `@bookTicker`, and `@markPrice@1s` with exact Decimal/UTC
normalization and validation. Do not implement WebSocket connection loops,
reconnection, feed runner, PaperBroker integration, bot pipeline, API, frontend,
or historical Spot changes. Create branch `feature/08-live-data-streaming` from
the current `main` before implementation. Read the architecture and all required
context docs first, plus relevant local FastAPI/asyncio/SQLAlchemy skills only if
the changed area requires them. Add comprehensive tests. Run focused tests, Ruff,
and changed-slice mypy. Update `CURRENT.md` and relevant Feature 08 documentation
only for this completed slice. Commit the slice. Report status, commit, tests,
concerns, and changed files in your response.

### Task 2 brief

Implement only the second vertical slice from `dispatch/PLAN.md` and
`dispatch/ARCHITECTURE.md`: build the Binance USDⓈ-M Futures provider stream layer
on branch `feature/08-live-data-streaming`, using `websockets.asyncio.client.connect`
and the existing Task 1 contracts/parsers. Add injectable connection factory and
test sleeper seams, fstream URLs for kline/aggTrade/bookTicker/markPrice, provider-
local logical subscription registry, k.x completion gating, and completed-candle
deduplication using the mandated composite key across reconnect attempts. Preserve
historical Spot behavior. Do not implement reconnect retry policy beyond the
minimal stream/session structure needed for deterministic tests, market-context
aggregation, EventBus feed runner, PaperBroker integration, bot pipeline, API,
frontend, or historical changes; those are later tasks. Add fake WebSocket tests
for message parsing/stream yields, incomplete-candle suppression, duplicate final
candle suppression, URL/stream selection, duplicate active subscription rejection,
and cleanup on generator exit/cancellation. Run focused tests, Ruff, and changed-
slice mypy. Commit the slice and report status, commit, tests, concerns, and files.

### Task 3 brief

Implement only market-context aggregation from the Futures architecture. Continue
on `feature/08-live-data-streaming` after commits `493fc1a`, `8987dda`, and
`2305517`. Build a provider-neutral aggregator that combines parsed book-ticker
and mark-price updates into coherent `MarketContext` snapshots and exposes the
existing `MarketContextUpdated` contract without importing `PaperBroker` or
`ExecutableMarket`. Require valid positive/non-crossed bid/ask and mark price;
carry index price, funding rate, next funding time, UTC component timestamps, and
freshness/as-of data. Reject or suppress incoherent/stale components according to
the architecture; make freshness thresholds and the clock injectable and avoid
background/orphan tasks. Keep Feature 08 responsible only for transport/context
normalization; do not apply funding, calculate P&L, liquidation, triggers, fills,
or implement Feature 09 pipeline behavior. Add deterministic tests for partial
updates, coherent publication, stale/missing components, crossed books, UTC/Decimal
invariants, and recovery. Run focused tests, Ruff, and changed-slice mypy. Commit
and report status, commit, tests, concerns, and files.

### Task 4 brief

Implement reconnect/failure handling, candle-gap detection, and feed health
monitoring from the authoritative futures architecture. Continue on
`feature/08-live-data-streaming` after `eb61be8`. Add bounded injectable retry and
backoff behavior around the existing fstream sessions; classify transient versus
fatal configuration/protocol/cancellation failures; preserve subscriptions and
candle deduplication across reconnects; surface typed `DataFeedError` without
silently swallowing exhaustion. Cancellation must clean up and re-raise without
retry/error publication. Add gap detection by completed candle open-time intervals
with no synthesis or REST backfill. Add monitor behavior for candle, book-ticker,
and mark/context freshness, using injected Clock and one timeout error per stale
episode with recovery reset. Keep task ownership explicit and avoid orphan tasks.
Do not implement EventBus feed runner orchestration beyond the contracts needed for
deterministic tests, PaperBroker, Feature 09 pipeline, API, frontend, or historical
changes. Add comprehensive deterministic tests, run focused tests/Ruff/changed-
slice mypy, commit, and report status/commit/tests/concerns/files.
