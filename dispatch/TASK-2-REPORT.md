# Feature 10 Task 2 Report — TradeClosed Journal Projection

## Delivered

- Added `JournalService` with an explicit `TradeClosed` subscription and idempotent
  `close()`/`unsubscribe()` lifecycle methods.
- Projected account, bot, trade, instrument, symbol, direction, prices, quantity, net P&L,
  strategy version, resolved strategy name, signal metadata, market context, and lifecycle
  timestamps into `JournalEntry`.
- Resolved strategy names through the shared persistence `StrategyVersionRepository` at
  projection time without changing the Feature 07 `Trade` contract.
- Resolved the historical symbol through the existing `InstrumentRepository`.
- Used defensive deep copies for signal and market-context snapshots.
- Relied on `JournalRepository.create()` as the durable idempotency fence, with an early
  lookup that avoids repeated strategy/instrument work for already-projected trades.
- Added focused coverage for subscription lifecycle, complete mapping, strategy resolution,
  duplicate events, missing strategy identity, snapshot isolation, and EventBus failure
  recording.

## Failure behavior

Missing `strategy_version_id`, an absent strategy version, or an absent instrument raises a
`ValueError` before persistence. When delivered through `EventBus`, the failure is recorded by
the configured `FailureRecorder` and the affected bot is paused according to the existing
EventBus contract; no partial journal entry is written.

## Scope

No API, analytics, frontend, migration, or Feature 07 trade-semantic changes were made.
