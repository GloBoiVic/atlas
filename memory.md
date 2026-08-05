# Memory — Feature 05 Backtesting + Design-System Reconciliation

Last updated: 2026-08-04

## What was built

### Feature 05 — Backtesting (previous session)

- **CandleRepository read protocol** (`get_candles`) added to protocol, SQLAlchemy, and in-memory implementations with inclusive UTC, complete-only, chronological semantics.
- **BacktestRun/BacktestTrade domain models** in `backend/backtester/models.py` — `BacktestStatus` enum (`PENDING→RUNNING→COMPLETED/FAILED/CANCELLED`), `BacktestConfig` with UUID/Decimal/frozen validation, `BacktestResult` with 8 run-level metrics, execution contract enforcement.
- **Alembic migration 008** — native UUID PKs, `NUMERIC(28,12)` for money/Decimal-ratio columns, `FLOAT` for non-monetary ratios, JSONB for config, `ON DELETE CASCADE` from runs to trades.
- **Backtest ORM models** and SQLAlchemy/InMemory repository parity implementations.
- **Isolated replay engine** (`BacktesterEngine` in `backend/backtester/engine.py`) — fresh run-local EventBus/SimulationClock/PaperBroker/InMemoryExecutionRepository per run, warm-up (strategy-state only, no signals), canonical candle loop (validate → clock.advance → ExecutableMarket with next_candle_open → CandleClosed → triggers), protective stops, last-candle gate, subscription cleanup in `finally`.
- **BacktestService** full lifecycle (`PENDING→RUNNING→COMPLETED/FAILED/CANCELLED`), trusted strategy resolution via `StrategyRegistry`, atomic persistence with bounded terminal-failure fallback, `asyncio.CancelledError` handling.
- **Backtest metrics** in `backend/backtester/metrics.py` — `total_return` (Decimal ratio), `total_pnl`, `starting_equity`, `ending_equity`, `max_drawdown` (monetary), `win_rate`, `profit_factor`, `sharpe_ratio`. Owner-deferred to Feature 10.
- **Four API endpoints** — `POST /backtests`, `GET /backtests`, `GET /backtests/{id}`, `GET /backtests/{id}/trades` — with Decimal-as-string serialization, `_FORBIDDEN_KEYS` untrusted-config rejection, env-configured CORS (no wildcard with credentials), 404/409/422/500 error mapping.
- **Complete frontend backtests UI** — form (strategy/instrument/timeframe/date-range/balance), run list with empty state, detail view with 8-metric `Metric` grid + trades table, `StatusBadge`/`StatusMessage` for lifecycle, UTC datetime-local handling (`Z`-suffix + `aria-describedby` hint), `end>=start` validation, string-only `formatPercentRatio`, design tokens (`bg-atlas-*`, `font-atlas-mono`, `rounded-atlas-*`), accessibility conventions.
- **No new strategy/risk/execution semantics** — reused shared `StrategyEngine`/`RiskEngine`/`ExecutionEngine`/`PaperBroker` contracts exclusively.

**Validation:** 371 backend tests, Ruff clean, backtest-feature mypy 0 errors, coverage 90%, `tsc --noEmit` zero errors, ESLint zero errors, `next build` compiled successfully. Three accepted environment limits: PostgreSQL/Docker integration deferred (daemon unavailable), no frontend test runner, 14 pre-existing unrelated test mypy errors.

### Design-system reconciliation (this session)

- **Token projection chain verified**: JSON → `design/tokens/atlas-tokens.css` → `frontend/src/styles/atlas-theme.css` pairwise audit confirmed zero value drift across 65+ tokens (22 colors, 10 text sizes, 13 spacing, 5 radii, 2 easings, 4 font weights, 5 durations, 6 tracking, 4 leading, 2 font families, 4 layout, 4 z-index). No runtime import of design CSS.
- **Layout/z-index/font-weight projections added**: `--container-atlas`, `--container-atlas-narrow`, `--spacing-atlas-topnav-height`, `--spacing-atlas-page-gutter`, `--z-index-atlas-sticky/modal/toast/tooltip` added to Tailwind `@theme`. Font-weight corrected from non-functional `--fw-atlas-*` to `--font-weight-atlas-*`, generating working `font-atlas-regular/medium/semibold/bold` utilities.
- **Base-style cleanup**: Body reset and `.mono` class removed from `design/tokens/atlas-tokens.css` (now 89 lines, token-only). `frontend/src/app/globals.css` confirmed as sole owner of Google Fonts import, `@import "tailwindcss"`, base reset — single font load, single body reset, correct `@import` ordering.
- **Existing backtests utility migration**: All `/backtests` components migrated from standard Tailwind to semantic Atlas tokens — 10 legacy `font-fw-atlas-semibold` → `font-atlas-semibold`; `tracking-tight` → `tracking-atlas-tight`; 13+ text-size instances → `text-atlas-*`; 30+ spacing instances → `*-atlas-*`; `leading-atlas-tight/snug/normal` deployed; `duration-atlas-base`/`ease-atlas-out` on transitions. No route scope leakage.
- **56px topnav maintained**: `layout.topnav-height` kept at 56px in JSON, design CSS, and Tailwind theme pending human provenance confirmation of the 57px `dashboard-topnav.png` screenshot.
- **8 intentional exceptions documented**: `py-[10px]`, `px-[10px]`, `min-h-11`, `py-[56px]`, `max-w-7xl/2xl/xs`, `mt-[2px]` — with rationale in `ui-registry.md`. Structural/layout utilities (flex, grid, size-4, etc.) recognised as non-token standard utilities.
- **Validation**: lint PASS, typecheck PASS, build PASS (14.9s, 4 routes), compiled CSS utility audit confirms all `bg-atlas-*`, `text-atlas-*`, `font-atlas-*`, `rounded-atlas-*`, `leading-atlas-*`, `tracking-atlas-*`, `*-atlas-*`, `ease-atlas-*`, `duration-atlas-*` utilities resolve correctly.
- **Deferred**: dashboard/landing screenshot comparisons (future acceptance artifacts), topnav 57px provenance (human confirmation).
- **Final review**: **PASS** 🟢 — 0 Critical, 0 Important, 0 Minor findings in reconciliation scope. All 10 architecture conflicts C1–C10 resolved or explicitly deferred. All 5 prior review findings F1–F5 (2 Critical + 3 Important) fixed.

### Feature 06 — Risk Engine (preserved from previous session)

- Deterministic RiskEngine on `feature/06-risk-engine` — configuration-driven stops (percentage_of_entry/absolute_price_distance/explicit_stop_price), 1% default/2% max equity risk, conservative rounding (BUY→FLOOR, SELL→CEILING), R:R take-profit, direction-conflict rejection, transient reservations, per-bot isolation, fail-closed.
- `RiskApproved`/`RiskRejected` typed event payloads.
- 294 tests, Ruff clean, Feature 06 mypy clean, 98% coverage. Final review: PASS.
- No ATR dependency. No scaling or reversal.

### Context documentation reconciliation (preserved from previous session)

- All 17+ context docs reconciled into single authoritative source. Singular ownership boundaries, approved MVP execution model, defaults.

### Feature 04 — Strategy Engine (preserved from previous session)

- UUID/Decimal/immutable Signal, provenance, warm-up, registry, validation, fail-closed contracts. 256 tests.

### Feature 03 — Data Layer (preserved from previous session)

- Historical CSV + Binance Spot providers, normalized contracts, dataset fingerprints, migrations 005/006.

## Decisions made

### From this session (Design-system reconciliation)

- **Token projection chain is authoritative**: `atlas-tokens.json` is the only editable source; `atlas-tokens.css` and `atlas-theme.css` are derived projections. Never edit them independently.
- **`--font-weight-atlas-*` namespace**: Tailwind v4 requires `--font-weight-*` for weight utilities. The non-functional `--fw-atlas-*` was replaced; `font-fw-atlas-*` classes are gone.
- **`globals.css` is sole runtime owner**: No runtime import of `design/tokens/atlas-tokens.css`. Single Google Fonts `@import`, single `@layer base` body reset.
- **56px pending provenance**: Topnav stays 56px until a human confirms whether `dashboard-topnav.png`'s 57px is content+border or pure content.
- **No route scope expansion**: Migration limited to existing `/backtests` files and shared styles. Dashboard/landing stubs remain untouched and still use standard Tailwind.
- **Intentional exceptions are documented, not blocked**: 8 utility instances without Atlas equivalents are preserved with rationale in `ui-registry.md`.
- **Structural/layout utilities exempt**: `flex`, `grid`, `size-4`, `min-h-screen`, `overflow-*`, `truncate`, etc. are standard utilities not requiring Atlas token equivalents.
- **Screenshot comparisons deferred**: Not a code-quality gate for this slice. Dashboard/landing references remain future acceptance artifacts.

### From previous session (Feature 05 Backtesting)

- **Reuse `build_dataset_identity` from `loader.py`** — not the simplified spec example. Production function hashes all candle fields.
- **`NUMERIC(28,12)` for backtest money/Decimal-ratio columns** — matches Feature 07 convention, not the `NUMERIC(20,8)` in the database doc.
- **Warm-up is strategy-state-only** — no signals, no events emitted during warm-up.
- **Signal at candle T close → fill at T+1 open** — enforced by `PaperFillMode.BACKTEST` + `ExecutableMarket.next_candle_open`. Last candle is a no-execution gate.
- **`total_return` = Decimal ratio** (0.125 = 12.5%). Persisted as `NUMERIC(28,12)`, serialized as string in API, displayed as percentage via string-only `formatPercentRatio` (no float conversion).
- **`max_drawdown` = absolute monetary value**, not a ratio. Labeled "Max drawdown (absolute)" in UI, formatted as raw Decimal string.
- **CORS configurable via env** with explicit origin list; wildcard `*` with credentials explicitly rejected.
- **No metric recalculation in the frontend** — all formatting-only transformations.
- **Feature 05 is sequenced after Feature 07** despite its lower domain ID — Feature 07's execution contracts were necessary for backtest execution.
- **Asyncio.CancelledError is caught, persists CANCELLED status, then re-raises** — clean cancellation semantics.

### Preserved from earlier sessions (still relevant)

- Feature IDs are stable domain identifiers, not implementation sequence.
- BotSupervisor ownership: Feature 02 (core), Feature 09 (paper/testnet), Feature 12 (API/UI).
- Paper Broker: shared algorithm with mode-specific price sources (next-candle-open for backtests, current market for live).
- Event payload ownership: Feature 04 owns SignalGenerated/StrategyError; Feature 06 owns RiskApproved/RiskRejected; Feature 07 owns execution events.
- Execution realism defaults: 0.10% taker fee, 0.05% fixed adverse slippage, stop-loss-first candle ambiguity, complete fills by default, no synthetic candles, indefinite data retention, immutable strategy pins.
- Metric formulas canonical in Feature 10; Feature 05 persists raw snapshots only.
- Atlas remains single-user, paper-first, broker-agnostic, single-worker for MVP.
- Backend identifiers use UUID; money/prices/quantities/fees/P&L use Decimal; timestamps are UTC.
- No ATR for MVP risk engine — configuration-driven stop sources.
- Conservative rounding direction (BUY→FLOOR, SELL→CEILING) for stop distance and quantity.
- Transient reservations + per-bot isolation for risk engine.
- Fail-closed: exceptions in handlers log and re-raise; no misleading approvals.

## Problems solved

### From this session

- **Legacy `font-fw-atlas-semibold` in 10 instances (F1)** — All replaced with `font-atlas-semibold`. Compiled CSS confirms `font-weight: 600`.
- **`tracking-tight` value drift (F2)** — Replaced with `tracking-atlas-tight` (`-0.02em` vs Tailwind's `-0.025em`).
- **Standard Tailwind text sizes in backtests components (F3)** — All 13+ `text-xs/sm/lg/xl/3xl` instances migrated to semantic `text-atlas-*`.
- **Standard Tailwind spacing in backtests components (F4)** — All 30+ spacing instances migrated to `*-atlas-*` patterns; 8 exceptions documented.
- **No `leading-atlas-*` utilities used (F5)** — `leading-atlas-tight/snug/normal` deployed across all 5 backtests components.
- **Design CSS base reset vs globals reset (C9)** — Body reset and `.mono` removed from `atlas-tokens.css`; `globals.css` confirmed as sole owner.

### From previous session

- **formatPercentRatio padStart→padEnd bug** — Original implementation used `padStart` which could produce wrong decimal shifts. Fixed to `padEnd` with 8 test value verification (0.125→12.5%, 0.01→1%, 1.5→150%, etc.). String-only operation, no float conversion.
- **max_drawdown monetary vs ratio ambiguity** — Prior review flagged `max_drawdown` as potentially needing `%` display. Contract evidence proved it is absolute monetary value. Finding withdrawn. Labeled "Max drawdown (absolute)".
- **Migration isolation failure (B1)** — `test_backtest_models_are_registered_for_alembic_metadata` failed when run in isolation because `Base.metadata.tables` was empty. Fixed by adding explicit model imports to the test.
- **Wall-clock event timestamps** — Initial replay used `datetime.now(timezone.utc)` for event timestamps. Fixed to propagate `SimulationClock` time through the event chain.
- **Dataset identity missing from SQLAlchemy persistence path** — `SqlAlchemyBacktestRepository.finalize_run` omitted the `dataset_id` column from its UPDATE statement. Fixed.
- **Bounded terminal-failure fallback** — If `_finalize` persistence fails, the service catches the error, attempts to persist FAILED status with the error message, and re-raises.
- **CORS wildcard-with-credentials** — Fixed to env-configured explicit origin list.
- **UTC datetime-local handling** — Fixed by appending `"Z"` suffix to force UTC interpretation, with `aria-describedby` hint text.
- **Post-rounding stop geometry guard** — After conservative rounding, a rounded stop at entry is possible (zero distance). Added guard that rejects `invalid_stop` if rounded distance isn't positive.

### Preserved from earlier sessions (still relevant)

- Event payload lockstep — adding fields requires simultaneous test update (solved with parametrized EVENT_TYPES).
- Mode filtering gap in risk position conflict — reservation keys now scoped by mode (backtest vs paper).
- Stale Feature 04 contracts resolved (instrument: str, strength: float, candle_id, mutation).
- Documentation drift root cause addressed with explicit ownership boundaries.

## Eureka moments

- **Explicit stop sources over ATR** eliminates indicator state, warm-up latency, and candle-sync complexity from the risk gate — fully configuration-driven and deterministic.
- **Conservative tick/step rounding** on both stop distance and quantity means the risk engine is always pessimistic — correct safety posture.
- **`RiskContextProvider` protocol** decouples risk engine from any DB/broker dependency without abstract base classes or DI frameworks.
- **Shared contract reuse** (StrategyEngine/RiskEngine/ExecutionEngine/PaperBroker) in backtesting proves the architecture works — the same event-driven pipeline runs in both modes.
- **`formatPercentRatio` as string-only operation** avoids float precision issues entirely — moves decimal point with regex/string manipulation, not arithmetic.

## Current state

- **Feature 05 Backtesting** is **complete and reviewed** — 371 tests, Ruff clean, backtest mypy 0 errors, coverage 90%, tsc/ESLint/build PASS.
- **Feature 06 Risk Engine** is **complete and reviewed** — previously delivered on branch `feature/06-risk-engine`.
- **Design-system reconciliation** is **complete and reviewed** — token projections verified, all backtests components migrated, all 10 architecture conflicts resolved/deferred, quality gates pass. Final review: PASS 🟢.
- **Feature 07 Execution Layer** is **complete and reviewed** — execution contracts, persistence, paper broker, reconciliation, net exposure coordinator.
- **Three accepted environment limitations**: PostgreSQL/Docker integration testing deferred (daemon unavailable), no frontend test runner (infrastructure gap), 14 pre-existing unrelated test mypy errors.
- All changes currently uncommitted on the `feature/05-backtesting` branch. Dispatch files have been reset to empty templates.

## Next session starts with

1. Commit and push all work on `feature/05-backtesting` (or merge to `main`).
2. Read Feature 08 (Live Data Streaming) acceptance criteria — `context/features/08-live-data-streaming.md`.
3. Feature 08 requires: WebSocket data feed integration, live candle assembly, CandleClosed emission from live data, feed health monitoring.

## Open questions

- Whether to push local `main` to remote before beginning Feature 08.
- Topnav 57px provenance — human confirmation needed on whether `dashboard-topnav.png` represents a 57px bar, a 56px bar plus 1px border, or capture framing. Until confirmed, 56px remains canonical.
