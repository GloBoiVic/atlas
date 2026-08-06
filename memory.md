# Memory — Feature 09 USDⓈ-M Futures Paper Trading

Last updated: 2026-08-05

## What was built

### Previously completed

- Feature 05 Backtesting is complete and merged into `main`.
- Feature 06 Risk Engine and Feature 07 Execution Layer are complete and merged.
- Design-system reconciliation is complete and reviewed.
- Feature 08 Binance USDⓈ-M Futures live streaming is complete and integrated.

### Feature 09 — Phase 8 paper trading

- Reconciled live-data, paper-trading, and future testnet context to Binance USDⓈ-M Futures;
  preserved historical Spot `binance` versus live `binance_usdm` identities.
- Added `MarketContext` → `ExecutableMarket` translation with freshness validation and
  `next_candle_open=None` for live paper.
- Added isolated `LivePaperPipeline` with scoped EventBus handling, shared account-level netting,
  deterministic protective → liquidation → funding maintenance, and fail-closed lifecycle/
  reconciliation behavior.
- Added durable idempotent funding adjustments with Alembic migration 009 and repository support.
- Added paper-state restart reconstruction through chronological fill replay, including fees,
  realized P&L, positions, and funding; no broker snapshot is used.
- Added mark-persistence cadence, strict mode filtering, required funding scope fields, and
  focused pipeline/restart/funding/maintenance tests.

## Decisions made

- `binance_usdm` is canonical for live Futures providers, paper composition, and future testnet;
  historical `binance` remains intentionally Spot-only.
- Feature 09 reuses Feature 07's account-level `AccountExposureCoordinator` across pipelines;
  strategy, risk, feed, and provenance state remain bot-isolated.
- Funding sign convention: Long = `−notional × rate`; Short = `+notional × rate`.
- Balances are floored at zero. Paper restart reconstruction uses durable orders, fills,
  positions, and funding rather than a separate broker snapshot.
- Mark updates use an explicit operational sampling cadence; fills, triggers, liquidation,
  reconciliation, and final state are always persisted.
- `stale_after` defaults to 5 seconds for this slice and remains deferred to configuration.

## Problems solved

- Corrected the initial Spot assumption and reconciled the source-of-truth documentation to
  USDⓈ-M Futures while preserving intentional historical Spot references.
- Fixed restart balance reconstruction by replaying fills chronologically with fee deduction,
  realized P&L, and quantity-weighted entry prices.
- Fixed funding to read authoritative broker positions after maintenance rather than stale
  repository projections.
- Fixed in-memory order mode filtering and made funding scope fields non-optional.
- Preserved deterministic Futures market semantics: bid/ask for execution, mark for P&L,
  triggers, and liquidation; funding remains separate from trading fees and P&L.

## Eureka moments

- Futures market data has distinct trade, executable bid/ask, mark, index, and funding semantics;
  provider-neutral `MarketContext` prevents treating mark/index prices as fill prices.
- Shared account-level netting is intentional shared state; all strategy and feed state remains
  isolated per bot.

## Current state

- Feature 09 Phase 8 is complete on `feature/09-live-trading`.
- Final Tier 2 review: PASS with no Critical or Important findings; six Minor observations remain.
- Validation: 427/428 backend tests passed; one pre-existing frontend Dockerfile failure remains
  unrelated. Ruff and full backend mypy passed.
- Work is uncommitted and ready to merge into `main`.

## Next session starts with

1. Merge or rebase `feature/09-live-trading` into `main`.
2. Resolve the known pre-existing frontend Dockerfile test failure when appropriate.
3. Choose the next roadmap slice: Feature 10 analytics, Feature 12 bot-management/API/UI, or
   the later authenticated USDⓈ-M Futures testnet slice.

## Open questions

- Authenticated USDⓈ-M Futures testnet execution remains deferred to the later Feature 09
  Phase 11 slice.
- Topnav 57px screenshot provenance remains unresolved; 56px remains canonical.
