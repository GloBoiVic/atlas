# Current Feature

## Feature 11 Slice 6 — Remaining Operational Pages and Charts (complete, 2026-08-06)

- [x] Implement the REST-polled `/trades` read-only history surface with typed API strings and
      explicit UTC/freshness states.
- [x] Keep `/settings` truthful against supported backend contracts; report the missing settings
      API as deferred rather than inventing editable configuration.
- [x] Add a cleaned-up Lightweight Charts equity wrapper for the API-provided analytics series;
      do not add a candlestick surface without a corresponding candle API.
- [x] Preserve existing operational routes and document validation gaps.

Branch: `feature/11-slice-6-operational-pages`

Validation: frontend lint, typecheck, and production build passed. Route smoke checks returned HTTP
200 for all canonical routes. The frontend test runner remains unavailable. No backend settings or
candlestick REST contracts exist, so those surfaces were truthfully deferred. `/imprint` is not an
installed executable in this environment; the registry was updated with the imprint pattern capture.

Last updated: 2026-08-06

## Feature 11/12 Slice 5 review fixes — complete, 2026-08-06

- [x] Removed unsafe bot-mode assertions from the operational view and bot form.
- [x] Added a runtime-supported-mode guard; unknown/production modes fail closed without
      paper/testnet controls or lifecycle commands.

Validation: frontend typecheck, lint, and production build passed. No frontend test runner exists.
No WebSocket, mock data, backend, or `/dispatch/` changes were added.

## Feature 11/12 Slice 5 — Bot Management UI (complete, 2026-08-06)

- [x] Implement truthful `/strategies`, `/paper`, and `/testnet` REST-polled operational views.
- [x] Add supported paper/testnet bot create/edit configuration, preserving account/mode and
      strategy-version identity.
- [x] Add confirmed start, pause, resume, and stop mutations with TanStack invalidation/refetch,
      observed/desired transitional states, UTC refresh timestamps, and Sonner outcomes.
- [x] Update UI registry through imprint-equivalent component pattern capture.

Validation: frontend typecheck, lint, and production build passed. Frontend automated test runner
remains unavailable. Route smoke checks and manual browser interaction checks were not available in
this environment; this slice did not modify backend or `/dispatch/` files.

Last updated: 2026-08-06

## Feature 12 runtime-facing Slice 4 — Bot Management Backend (complete, 2026-08-05)

- [x] Implement persisted BotService composition and typed CRUD/lifecycle REST contracts.
- [x] Keep BotSupervisor authoritative for every lifecycle transition and gate execution on
      reconciliation, strategy identity, broker state, and feed safety.
- [x] Add focused safety/isolation/persistence/transport tests and run backend validation gates.

Branch: `feature/12-bot-management-backend`

Validation: focused bot tests 4 passed; full backend pytest 470 passed; Ruff clean. Docker API
image built; PostgreSQL migration 011 upgraded, downgraded, and upgraded successfully. Changed-slice
mypy is unavailable on the host and the Docker run used an image built before the final Decimal
annotation fix; rerun after rebuilding if strict type-gate evidence is required.

Review fix: identical `POST /bots` configuration identities now return the existing persisted bot
through repository-owned duplicate handling; migration 012 adds the matching database uniqueness
constraint. Focused bot tests: 6 passed; full backend pytest: 472 passed; Docker migration 012
upgrade/downgrade/upgrade and changed-slice mypy passed.

Latest review fixes: numeric/Decimal values now use a separate tagged canonical identity projection
without changing runtime config types or precision; numeric `1`, `1.0`, and Decimal `1.00` share
identity while textual `"1"` remains distinct. Migration 012 now fails closed with an actionable
error when legacy duplicate identities exist, and migration 013 adds the nullable identity column
without inventing or deleting historical records. Focused bot tests: 8 passed; full backend pytest:
474 passed; Ruff and changed-slice Docker mypy passed. PostgreSQL verified clean migration 012/013
upgrade path and duplicate-preflight failure path.

Idempotency re-review fix: repository updates now preflight the canonical identity in both
implementations and translate only the named SQL uniqueness violation into `BotConflict`; unrelated
SQLAlchemy integrity failures still propagate. Focused bot/SQL repository tests: 16 passed; full
backend pytest: 477 passed; Ruff and changed-slice Docker mypy passed. No context documentation
change was required.

Tier 3 re-review (2026-08-06): 0 Critical, 1 Important, 1 Minor findings. All prior Critical/Important
findings resolved. Numeric canonicalization verified deterministic and precision-safe; `__atlas_numeric__`
encoding correctly separates text from numeric values; runtime config and identity projection stored in
separate columns without cross-contamination. Migration ordering (011→012→013) correct; preflight
duplicate check verified fail-safe/actionable/non-destructive. Concurrent create idempotency verified
safe via PostgreSQL UNIQUE constraint atomicity. No lifecycle/trading data mutated or deleted. New
Important finding: `update_bot` can trigger unhandled `IntegrityError` on identity collision (recommend
pre-check or catch in repository). New Minor finding: memory `update_configuration` has parity gap
with SQLAlchemy on identity conflict detection. See dispatch/REVIEW.md for full report.

Safety assumptions: API accepts paper/testnet only; account mode must match bot mode; trusted
strategy-version identity and deployed registry resolution are required; supervisor remains the
sole lifecycle owner; reconciliation and pipeline safety failures remain persisted as error and
are returned as HTTP 503; default API runtime is fail-closed and cannot submit orders.

Last updated: 2026-08-05

## Feature 11 — Option 1 WebSocket reconciliation (complete, 2026-08-05)

- [x] Keep REST polling as the authoritative Feature 11 MVP live mechanism.
- [x] Gate Slice 4a route registration and EventBus projection behind the explicit,
      non-default `ENABLE_DEFERRED_OPERATIONAL_WEBSOCKET` setting.
- [x] Prove default app behavior does not register `/ws/operational`; retain protocol unit tests
      only through explicit deferred opt-in.

The default API/Docker deployment has no operational WebSocket route and no client activation. The
deferred foundation remains intentionally non-production: API and worker EventBus instances are
separate, the default authenticator rejects every connection, and Cloudflare Access auth/proxy
wiring is not implemented. Future activation additionally requires a cross-process bridge, unique
state-envelope IDs, send timeout/backpressure handling, and deployment auth tests.

Validation: focused reconciliation/config tests 22 passed; full backend pytest 466 passed; full
Ruff passed; `docker compose config --quiet` and default app route inspection passed. Changed-slice
mypy could not run because `mypy` is not installed in this environment. Starlette emitted one
existing httpx compatibility warning.

Last updated: 2026-08-05

## Feature 11 Slice 3 — Dashboard REST View (complete, 2026-08-05)

- [x] Replace the dashboard placeholder with a typed, read-only operational REST view.
- [x] Display API-provided account/equity/P&L, positions, bots, recent trades, health/freshness,
      strategy inventory, and analytics/equity information.
- [x] Add truthful loading, empty, error, unavailable, stale, and REST polling states without
      browser-side financial calculations or WebSocket behavior.
- [x] Update the UI registry through imprint for dashboard panel patterns.
- [x] Run frontend lint, typecheck, production build, and route smoke validation.

Validation: `npm run lint`, `npm run typecheck`, and `npm run build` passed. Frontend automated
test runner remains unconfigured. Dashboard route smoke passed against the production server.
Backend/Docker integration was not rerun; Slice 2 recorded PostgreSQL/Docker availability limits.

Last updated: 2026-08-05

## Feature 11 Slice 2 — Backend Read Models (complete, 2026-08-05)

- [x] Add typed, scoped dashboard read contracts and repository/service composition.
- [x] Wire deployment-configured AnalyticsScope without inventing equity.
- [x] Add focused backend coverage and run the required validation gates.

Branch: `feature/11-backend-read-models`

Validation: focused dashboard/API tests 15 passed; full backend pytest 457 passed; changed-scope
Ruff and mypy passed. PostgreSQL/Docker-backed endpoint execution was not available in this run.

Last updated: 2026-08-05

## Feature 11 Slice 1 — Shell Foundation (complete, 2026-08-05)

- [x] Add persistent App Router shell and canonical route navigation.
- [x] Add TanStack Query provider and reusable shell status/boundary primitives.
- [x] Preserve existing Backtests, Journal, and Analytics behavior.
- [x] Run frontend lint, typecheck, production build, and focused route checks.

Branch: `feature/11-shell-foundation`

Validation: frontend lint, typecheck, and production build pass. Route smoke checks pass for all
9 canonical routes and active navigation state.

Last updated: 2026-08-05

## Feature 10 — post-review environment validation (complete, 2026-08-05)

- [x] PostgreSQL migration 010 upgraded, downgraded to 009, and upgraded again successfully
      against Docker Desktop PostgreSQL.
- [x] Corrected the stale standalone Dockerfile test; focused test and full backend suite pass.
- [x] Built the frontend Docker image successfully; `/journal` and `/analytics` compile.
- [ ] Frontend test runner remains unconfigured and is deferred as infrastructure work.

Validation: 453 backend tests passed; frontend Docker build, lint, typecheck, and production build
passed. Docker-backed migration execution is now verified.

Last updated: 2026-08-05

## Feature 10 Task 6 — page-level Analytics UI (complete, 2026-08-05)

- [x] Add `/analytics` page, API client types/function, UTC date filters, explicit metric states,
      and accessible API-provided closed-trade equity curve.
- [x] Reuse Atlas UI patterns, update the registry through imprint, and keep Feature 11 shell
      integration out of scope.
- [x] Run frontend lint, typecheck, and production build.

Last updated: 2026-08-05

## Feature 10 Task 4 — Journal/Analytics API layer (complete, 2026-08-05)

- [x] Add schemas, routes, dependency factories, registration, and API coverage.
- [x] Run focused tests, Ruff, changed-slice mypy, and commit the implementation.

Last updated: 2026-08-05

## Feature 10 Task 3 — canonical analytics metrics and service (complete, 2026-08-05)

- [x] Add pure immutable canonical metrics and closed-trade equity curve contracts.
- [x] Add execution-repository closed-trade reads with inclusive UTC exit-time filtering.
- [x] Add analytics service with explicit starting-equity input and focused coverage.
- [x] Run final validation and commit the implementation.

Last updated: 2026-08-05

## Feature 10 Task 2 — TradeClosed journal projection (complete, 2026-08-05)

- [x] Add the idempotent TradeClosed journal projection service and focused tests.
- [x] Run focused tests, Ruff, and changed-slice mypy.

Last updated: 2026-08-05

## Feature 10 Task 1 — persistence/domain contracts and repository parity (complete, 2026-08-05)

- [x] Add journal migration, ORM/domain contracts, and repository implementations.
- [x] Add focused migration, precision, validation, filtering, idempotency, notes, and parity tests.
- [x] Run focused tests, Ruff, changed-slice mypy, and commit the implementation.

Last updated: 2026-08-05

## Feature 09 Phase 8 — Tier 2 review fixes — complete (2026-08-05)

- [x] Reconstructed paper balance on restore from durable fill fees/realized P&L and funding,
      with idempotent Decimal semantics and regression coverage for profitable closes.
- [x] Added behavioral funding, maintenance-ordering, position-lifecycle, mode-filtering, and
      FundingAdjustment boundary tests; funding now reads the broker's authoritative position.
- [x] Aligned FundingAdjustment required fields with the non-null persistence contract.
- [x] Focused tests: 18 passed; changed-slice Ruff and mypy clean.

Validation: full backend pytest 427 passed; 1 pre-existing frontend Dockerfile assertion failed.
Full Ruff clean; changed-slice mypy clean. No commit created.

Last updated: 2026-08-05

## Feature 09 Phase 8 — live USDⓈ-M Futures paper pipeline — complete (2026-08-05)

- [x] Added the explicit `MarketContext` → `ExecutableMarket` adapter with Decimal/UTC,
      provider/instrument validation, and no live `next_candle_open`.
- [x] Added isolated `LivePaperPipeline` assembly over the existing feed, StrategyEngine,
      RiskEngine, ExecutionEngine, and Futures-aware PaperBroker contracts.
- [x] Added account/instrument/mode-scoped durable funding settlements with idempotent keys,
      operational mark sampling, deterministic maintenance ordering, and final-state persistence.
- [x] Added paper restart reconstruction from durable orders, fills, positions, and funding facts;
      no broker snapshot was introduced.
- [x] Updated Feature 09 Phase 8 acceptance status and added focused adapter/recovery tests.

Validation: focused execution/migration/model tests 49 passed; full backend pytest 422 passed,
1 pre-existing frontend Dockerfile assertion failed; changed-slice Ruff and mypy clean.
Blocker: PostgreSQL/Docker integration was not available in this environment.

Last updated: 2026-08-05

## Feature 08 — Task 6 LiveProviderRegistry and documentation gate — complete (2026-08-05)

- [x] Add separate broker-agnostic live-provider factory registry with deterministic duplicate/
      unknown errors and fresh per-session provider instances.
- [x] Register `binance_usdm` without constructing transport resources or changing historical
      Spot's `binance` registry/provider identity.
- [x] Reconcile Feature 08 source-of-truth documentation and add focused registry/doc tests.
- [x] Run focused tests, full suite, Ruff, and changed-slice mypy; commit the completed slice.

Validation: focused registry/documentation/provider tests 14 passed; changed-slice Ruff and
mypy clean. Full backend suite: 419 passed, 1 pre-existing frontend Dockerfile assertion failed.

Last updated: 2026-08-05

## Feature 08 — Task 5 EventBus feed runner — complete (2026-08-05)

- [x] Added isolated `LiveFeedSession` and `LiveFeedRunner` with explicit child-task ownership,
      cancellation-safe shutdown, and sole EventBus publication responsibility.
- [x] Published typed candle, tick, feed-error, and coherent market-context events with UTC
      timestamps and session metadata; incomplete and duplicate candles are suppressed.
- [x] Added lifecycle, metadata/order, failure-isolation, and no-orphan-task coverage.
- [x] Existing StrategyEngine integration remains EventBus-only; PaperBroker, BotPipeline,
      BotSupervisor, execution calculations, API, frontend, persistence, and history remain out
      of scope.
- [x] Task 5 review fixes: formatted the runner and added deterministic book/mark capability,
      context publication/metadata, failure, and cancellation-cleanup coverage.

### Feature 08 — Task 4 reconnect, gaps, and health — complete (2026-08-05)

- [x] Created `feature/08-live-data-streaming` from current `main`.
- [x] Added USDⓈ-M Futures provider identity and typed non-secret public-stream configuration.
- [x] Added keyword-only `DataFeedError`, provider-neutral `MarketContext`, and
      `MarketContextUpdated` foundations.
- [x] Added exact Decimal/UTC parsers and validation tests for Binance `@kline`, `@aggTrade`,
      `@bookTicker`, and `@markPrice@1s` payloads.
- [x] Added injectable fstream sessions, logical subscription cleanup, completion gating, and
      reconnect-preserving completed-candle deduplication.
- [x] Added deterministic provider-neutral book/mark context aggregation with injectable
      freshness thresholds and clock, immutable snapshots/events, and recovery behavior.
- [x] Added bounded injectable reconnect backoff, typed exhaustion/invalid-message feed errors,
      cancellation-safe cleanup, completed-candle gap detection, and deterministic feed health
      monitoring with stale-episode recovery.
- [ ] Feed runner, PaperBroker integration, bot pipeline, API, frontend, and registry remain
      deferred to later Feature 08 tasks.

### Task 2 review fixes — complete (2026-08-05)

- [x] Replaced retired `/ws` routing with explicit `/public/ws/` book-ticker and `/market/ws/`
      kline, aggregate-trade, and mark-price routes.
- [x] Tightened the injected connection factory contract with typed async-context-manager and
      transport-setting signatures.
- [x] Added route-specific configuration and stream URL coverage; historical Spot behavior is
      unchanged.

Last updated: 2026-08-05

## Frontend standalone asset serving fix — complete (2026-08-04)

- [x] Corrected the runner image layout so standalone `server.js` runs at `/app` and serves
      `.next/static` from `/app/.next/static`.
- [x] Rebuilt the frontend image and restarted only `atlas-frontend-1` with `--no-deps`.
- [x] Verified `/backtests` and its emitted CSS URL return HTTP 200; CSS contains Atlas styles.
- [x] Frontend lint, typecheck, and production build pass; bounded smoke check passes.

Root cause: the standalone bundle was copied under `/app/.next/standalone` but launched from
that nested path while static assets were copied to `/app/.next/static`. Next's standalone
server resolves its static directory relative to the standalone server root, so it looked for
`/app/.next/standalone/.next/static` and returned 404. The runner now follows Next's convention:
standalone contents at `/app`, static assets at `/app/.next/static`, and `node server.js`.

Validation: Docker build succeeded; `GET /backtests` returned 200; the emitted
`/_next/static/chunks/27mub1g206k2p.css` returned 200 with 18,855 bytes and an Atlas marker;
the container contains `/app/server.js` and that CSS asset. `npm run lint`, `npm run typecheck`,
and `npm run build` all passed.

## Design-system reconciliation — final review PASS (2026-08-04)

- [x] Final review complete: 0 Critical, 0 Important, 0 Minor findings in reconciliation scope.
- [x] All 5 prior findings (F1–F5) verified as resolved.
- [x] Compiled CSS confirmed: `font-atlas-semibold` → font-weight 600, all Atlas leading/tracking/spacing utilities work.
- [x] Intentional exceptions documented in CURRENT.md and `context/ui-registry.md`.
- [x] No legacy `font-fw-atlas-*` or `tracking-tight` in source or compiled output.
- [x] Quality gates: lint ✅, typecheck ✅, build ✅.
- [x] Topnav 56px maintained; screenshot provenance deferred for human confirmation.

See `dispatch/REVIEW.md` for the full final review.

## Design-system reconciliation slice 2 — complete (2026-08-04)

- [x] Resolved review findings F1–F5 across the existing `/backtests` surface.
- [x] Replaced legacy weight utilities, migrated semantic type/spacing/leading/tracking,
      and added Atlas duration/easing only to existing transitions.
- [x] Kept topnav source geometry at 56px; no routes, dashboard, landing, or navigation work added.
- [x] Updated the UI registry through the imprint workflow with intentional utility exceptions.

Intentional exceptions: `py-[10px]` on compact controls, `min-h-11` touch target,
`py-[56px]` for the empty-list state, and `max-w-7xl`/
arbitrary grid minimums preserve existing geometry where no equivalent Atlas token exists.

Validation: `npm run lint`, `npm run typecheck`, and `npm run build` pass. Compiled CSS contains
working `font-atlas-semibold` (600), Atlas leading/tracking, Atlas spacing, Atlas easing, and
the explicit duration utility. Source audit finds no legacy `font-fw-atlas-*`, `tracking-tight`,
or reviewed standard text/spacing utilities. Bounded smoke: `GET /backtests` returned HTTP 200
and rendered “Backtests”; no data was created. The first 3001 smoke attempt was blocked by the
already-running local Next server on port 3000, so the bounded check used that existing server.

Last updated: 2026-08-04

## Design-system reconciliation slice 1 — complete (2026-08-04)

- [x] Reconcile JSON-derived design and Tailwind token projections
- [x] Validate frontend lint, typecheck, build, and compiled utilities
- [x] Record the 56px token / 57px screenshot measurement without changing the source token

Validation: token projection audit passed; compiled utility audit passed; frontend lint,
typecheck, and production build passed. `dashboard-topnav.png` remains 1440×57px while the
canonical `layout.topnav-height` token remains 56px; border/crop provenance is deferred for
human confirmation. Component utility migration and route work remain out of scope.

Last updated: 2026-08-04

## Feature 05 — Final-gates blocker B1 resolved (2026-08-04)

- [x] Made `test_backtest_models_are_registered_for_alembic_metadata` self-contained by
      explicitly importing the backtest ORM models using the normal test import convention.
- [x] Isolated migration test passes without test-order side effects.
- [x] `python3 -m pytest -q tests/test_migrations.py -k
      test_backtest_models_are_registered_for_alembic_metadata`: 1 passed, 20 deselected.
- [x] `python3 -m pytest -q`: 371 passed in 11.35s.
- [x] `python3 -m ruff check .`: all checks passed.
- [x] Relevant mypy (backtest code plus `tests/test_migrations.py`): 14 files, 0 errors.

Last updated: 2026-08-04

## Feature 05 — Final quality gates complete (2026-08-04)

- [x] Backend pytest: 371 passed (full suite, 9.95s)
- [x] Ruff: all checks passed
- [x] mypy (backtest feature code, 13 files): 0 errors
- [x] mypy (full repo): 14 pre-existing errors, unchanged, unrelated to Feature 05
- [x] Coverage: 89% overall (above 80% minimum)
- [x] TypeScript typecheck: zero errors
- [x] ESLint: zero errors/warnings
- [x] `next build`: compiled successfully (1 cosmetic CSS @import warning)
- [x] **B1** `test_backtest_models_are_registered_for_alembic_metadata` is self-contained and passes in isolation
- [ ] PostgreSQL/Docker integration: deferred (Docker daemon not running)
- [ ] Frontend test runner: absent (infrastructure gap)

**Verdict: PASS** ✅ — No production code changes needed. All application quality gates pass. PostgreSQL/Docker and frontend test-runner gates remain deferred as documented.

Last updated: 2026-08-04

## Feature 05 Task 6 review fixes — complete (2026-08-04)

- [x] Corrected Decimal-ratio percentage formatting without floating-point conversion
- [x] Displayed max drawdown according to its absolute monetary contract
- [x] Added client-side date ordering/validity checks and explicit UTC handling for datetime-local inputs
- [x] Replaced backtest-page relative imports with `@/` aliases and refreshed the UI registry
- [x] Frontend lint, typecheck, and production build pass
- [ ] No frontend test runner exists in the current package; CSS warning limitation reported below

Validation limitations: frontend has no configured test runner. `next build` may continue to
report the pre-existing CSS `@import` ordering warning from `shadcn-bridge.css`.

Last updated: 2026-08-04

## Feature 05 Task 6 — Backtests UI — complete (2026-08-04)

- [x] Added `/backtests` with API-boundary list/detail fetching and a validated run form
- [x] Added completed, pending, running, failed, and cancelled presentation states with safe
      empty/error handling, responsive trades table, and accessible labels/status announcements
- [x] Preserved Decimal strings at the transport boundary; only presentation formatting is done in
      the browser and canonical metrics are never recalculated client-side
- [x] Updated the UI registry via the imprint workflow
- [x] Frontend lint, typecheck, and production build pass
- [ ] No frontend test runner exists in the current package, so automated UI tests were not added

Last updated: 2026-08-04

## Feature 05 Task 5 API review fixes — complete (2026-08-04)

- [x] Added environment-configured CORS with localhost:3000 default and wildcard-origin rejection
- [x] Added CORS, ValueError→409, empty-list, non-empty trade, and immutable-created_at coverage
- [x] Removed unused get_api_session scaffolding
- [x] Full backend pytest: 371 passed; full Ruff and changed-slice mypy clean
- [ ] PostgreSQL-backed endpoint execution and Docker Compose validation remain unavailable because
      the local Docker daemon is not running
- [ ] Full-repository mypy remains limited by 14 pre-existing errors in provider, circuit-breaker,
      strategy-example, supervisor, and logging tests

Last updated: 2026-08-04

## Feature 05 Task 5 — Backtest API — complete (2026-08-04)

- [x] Added FastAPI session/dependency infrastructure, trusted service factories, and router
      registration for the synchronous backtest API
- [x] Added Pydantic request/response schemas with trusted UUID selection, forbidden secret/import
      configuration fields, UTC validation, and Decimal-as-string result/trade serialization
- [x] Added POST, list, detail, and trades endpoints with documented 404/409/422/500 mappings
- [x] Added API coverage for success, validation, missing IDs, conflicts, failures, and Decimal output
- [x] Full backend pytest: 365 passed; changed-slice Ruff and mypy clean
- [ ] PostgreSQL-backed endpoint execution remains environment-blocked; frontend intentionally deferred

Last updated: 2026-08-04

## Feature 05 Task 4 review fixes — complete (2026-08-04)

- [x] Persisted `dataset_id` during SQLAlchemy terminal finalization
- [x] Added bounded FAILED fallback for terminal persistence errors while preserving the
      original infrastructure exception
- [x] Added service-boundary coverage for trusted resolution, strategy failure, protective
      projection, terminal metadata, cancellation, and SQLAlchemy dataset persistence
- [x] Full pytest: 361 passed; full Ruff clean; changed-slice mypy clean
- [x] Full-repository mypy still reports 14 pre-existing errors in unrelated provider,
      circuit-breaker, logging, strategy-example, and supervisor tests

Last updated: 2026-08-04

## Feature 05 Task 4 — BacktestService orchestration — complete (2026-08-04)

- [x] Added trusted strategy/instrument resolution and immutable run metadata snapshots
- [x] Added PENDING → RUNNING → COMPLETED/FAILED/CANCELLED lifecycle, bounded errors,
      cancellation persistence, terminal idempotency, and progress timestamps
- [x] Added atomic BacktestRepository finalization for run, closed trades, and metrics;
      replay remains isolated from Feature 07 execution tables
- [x] Added protective/liquidation closed-trade projection without changing fill semantics
- [x] Added focused service lifecycle, cancellation, identity, failure, and projection tests
- [x] Full backend pytest: 355 passed; Ruff and changed-slice mypy clean

Last updated: 2026-08-04

## Feature 05 Task 3 review fixes — complete (2026-08-04)

- [x] Propagated replay candle timestamps through SignalGenerated, risk, and execution events
- [x] Formalized validated `DataRequirement.warmup_candles`; removed undocumented getattr fallback
- [x] Added expected-value metric, protective-trigger, event timestamp, and same-input dataset identity tests
- [x] Full backend pytest, Ruff, and changed-slice mypy passed
- [ ] BacktestService status lifecycle, persistence orchestration, and cancellation ownership remain
      deferred to Task 4 as recorded in the review

Last updated: 2026-08-04

## Feature 05 Task 3 — isolated replay (in progress, 2026-08-04)

- [ ] Implement isolated BacktesterEngine replay orchestration and canonical projections
- [ ] Add deterministic timing, warm-up, final-candle, cleanup, and failure-path tests
- [ ] Run focused/full backend pytest, Ruff, and changed-slice mypy

## Feature 05 Task 3 — isolated replay (complete, 2026-08-04)

- [x] Implemented fresh run-local EventBus, strategy, risk, broker, execution repository/engine,
      and SimulationClock composition
- [x] Added loader dataset identity reuse, validated complete-candle replay, warm-up, executable
      next-candle-open market context, protective/liquidation checks, and final-candle gating
- [x] Added TradeClosed collection, closed-trade projection, Decimal canonical metrics, and
      cleanup/failure-path coverage
- [x] Focused replay tests: 4 passed; full backend pytest: 347 passed
- [x] Changed-slice Ruff and mypy: clean

Last updated: 2026-08-04

## Current session

### Feature 05 Task 1 review fixes — in progress (2026-08-04)

- [ ] Resolve the review-reported test mypy errors without suppressing unrelated errors
- [ ] Add focused BacktestTrade and BacktestRun validation coverage
- [ ] Add cross-implementation CandleRepository parity coverage
- [ ] Run full backend pytest, Ruff, and mypy validation

### Feature 05 Task 1 review fixes — complete (2026-08-04)

- [x] Replaced heterogeneous `**dict[str, object]` test construction with precise
      `TypedDict`/explicit arguments; no broad mypy suppression added
- [x] Added focused BacktestTrade validation for valid/nullable/frozen metadata and invalid
      Decimal, quantity, and UTC values
- [x] Added focused BacktestRun validation for valid/frozen config, status, and UTC values
- [x] Added identical-data SQLAlchemy/in-memory CandleRepository parity assertion
- [x] Full backend pytest: 337 passed
- [x] Changed-slice Ruff and mypy: clean

### Feature 05 Task 2 — persistence (2026-08-04)

- [x] Added Alembic migration 008 for isolated backtest runs and trade projections
- [x] Added UUID/UTC/JSONB-aware ORM models and Decimal-preserving conversions
- [x] Added deterministic, idempotent SQLAlchemy and in-memory BacktestRepository implementations
- [x] Added migration, repository, conversion, cascade, and validation tests
- [x] Focused validation: 21 tests, Ruff, and changed-slice mypy clean
- [x] Full backend pytest: 341 passed
- [x] Full backend Ruff and changed-slice mypy: clean

### Feature 05 Task 2 review fixes — in progress (2026-08-04)

- [ ] Import backtest ORM models in Alembic env.py for autogenerate metadata discovery
- [ ] Add offline migration downgrade ordering and ORM metadata coverage
- [ ] Run full backend pytest, Ruff, and changed-slice mypy

### Feature 05 Task 2 review fixes — complete (2026-08-04)

- [x] Imported BacktestRunModel and BacktestTradeModel in Alembic env.py so autogenerate sees
      all persistence metadata
- [x] Added offline migration assertions for FLOAT metric columns and downgrade dependency/index
      ordering
- [x] Added Alembic model-import and Base.metadata coverage without requiring PostgreSQL
- [x] Added explicit NULL-metric result=None repository coverage
- [x] Full backend pytest: 343 passed
- [x] Full backend Ruff: clean
- [x] Changed-slice mypy: clean
- [ ] PostgreSQL migration upgrade/downgrade execution: not run; PostgreSQL was unavailable

## Status

- [ ] Not started
- [ ] In progress
- [x] Complete

## Feature

- **Number:** 05
- **Name:** Backtesting
- **File:** context/features/05-backtesting.md

## Branch

- **Name:** feature/05-backtesting
- **Created:** 2026-08-04

## Current session

### Context reconciliation (2026-08-04)

- [x] Applied approved Atlas context reconciliation per `dispatch/ARCHITECTURE.md`
- [x] Added Feature ID → roadmap phase table to `context/features/README.md`
- [x] Updated `context/architecture.md`: fee/slippage scope, order-type scope,
      partial-fill semantics, trigger ambiguity, unknown-order fail-closed policy,
      ratio-vs-money numeric rule
- [x] Updated `context/roadmap.md`: feature IDs on all phase headings, cross-links
      for split phases (03/08, 08/09/12), Phase 7 dependency on 06/07, Phase 10
      dependency on 09 data
- [x] Updated `context/project-brief.md`: added MVP realism scope (completed candles,
      no same-candle fills, fee/slippage defaults, no synthetic gaps)
- [x] Updated `context/database.md`: NUMERIC vs FLOAT metric column policy,
      data-retention policy
- [x] Updated `context/features/02-core-infrastructure.md`: reconciled checkbox status;
      health monitoring deferred to 13
- [x] Updated `context/features/04-strategy-engine.md`: added repeated-signal
      responsibility, no-future-data expectation, strategy version immutability
- [x] Updated `context/features/05-backtesting.md`: marked Phase 7, deferred metric
      formulas to 10, added lookahead/data-integrity gate, recorded execution
      assumptions
- [x] Updated `context/features/06-risk-engine.md`: removed stale SignalGenerated
      payload claim (already implemented by 04), clarified risk-only payload ownership,
      added reuse-by-backtesting section
- [x] Updated `context/features/07-execution-layer.md`: authoritative execution event
      payload status table, added approved fee/slippage/order-type/partial-fill/
      trigger-ambiguity/unknown-order policy
- [x] Updated `context/features/08-live-data-streaming.md`: changed examples to
      `Instrument`, distinguished feed health contract from 13 hardening,
      documented no synthetic gap candles
- [x] Updated `context/features/09-live-trading.md`: removed duplicate payload-gap
      section, added ownership boundaries, separated Phase 8 paper from Phase 11
      testnet, added strategy-version startup policy
- [x] Updated `context/features/10-journal-analytics.md`: canonical metric formulas
      with annualization, drawdown basis, undefined cases, open-trade policy
- [x] Updated `context/features/11-ui-dashboard.md`: added Feature 09 dependency,
      documented UI boundary (displays facts only)
- [x] Updated `context/features/12-bot-management.md`: added Feature 09 dependency,
      ownership boundaries (supervisor core in 02, pipeline construction in 09),
      migration policy
- [x] Updated `context/features/13-polish-testing.md`: health-monitor boundary,
      lookahead gate, reconciliation tests, endpoint safety gates
- [x] Updated `CURRENT.md`: corrected stale next-feature from "Feature 05 — Bot
      Supervisor" to "Feature 06 — Risk Engine"
- [x] No application source code, dependencies, migrations, or `.env` modified

### Documentation reconciliation (2026-08-04)

- [x] Reconciled `context/features/04-strategy-engine.md`:
  - Removed `candle_id` from `SignalGenerated` payload
  - Replaced `instrument: str` with `instrument_id: UUID` on Signal
  - Replaced `strength: float` with `strength: Decimal` on Signal
  - Added canonical `strategy_version_id: UUID` to Signal
  - Removed individual `strategy_name`/`strategy_version`/`strategy_commit_sha` duplication
  - Made `DataRequirement` timeframe-aware (Feature 04 supports one candle series)
  - Rewrote Strategy Engine to assemble immutable Signal from strategy decision,
    with engine-owned provenance, validation, deduplication, warm-up gating, and
    fail-closed error handling
  - Updated SMA Crossover example to use `StrategyDecision`, `Decimal`, UUID
  - Added warm-up/replay ownership, registry trust, parameter ownership,
    safety/validation semantics sections
  - Updated acceptance criteria to reflect agreed contracts
- [x] Updated `context/architecture.md`: expanded Strategy Engine section with
    Signal provenance, engine responsibilities, deployment trust, and fail-closed
    semantics; removed `strategy_version_id: UUID` from `SignalGenerated` event
    contract (canonical on Signal)
- [x] Updated `CURRENT.md` for Feature 04 planning/document reconciliation
- [x] No application source code, dependencies, migrations, or `.env` modified

### Task 2 — Strategy contracts and trusted registry (2026-08-04)

- [x] Implemented immutable strategy contracts with UUID, Decimal, UTC, and metadata validation
- [x] Implemented synchronous Strategy base contract and timeframe-aware data requirements
- [x] Implemented fail-closed trusted registry for explicitly deployed factories
- [x] Added focused contract and registry tests
- [x] Implemented per-bot StrategyEngine, warm-up gating, event payloads, and focused tests

### Task 4 — Example strategies (2026-08-04)

- [x] Implemented Decimal SMA crossover and Bollinger Bands examples with isolated state
- [x] Added focused behavior and configuration tests
- [x] Wrote `dispatch/feature04-examples-report.md`
- [x] Ruff, mypy, and pytest coverage clean (256 tests passed, Ruff clean, mypy clean)

### Contracts and registry quality fix (2026-08-04)

- [x] Replaced string-mixin enums with Python 3.12 `StrEnum` while preserving values
- [x] Typed metadata freezing/validation without weakening Decimal support or immutability
- [x] Updated registry `Callable` import to `collections.abc`

### Task 5 — Final documentation status (2026-08-04)

- [x] Fixed stale "same candle ID" wording → canonical composite key
- [x] Marked all implemented deliverables and acceptance criteria with [x]
- [x] Marked YAML config boundary as partially complete ([~]) — end-to-end wiring deferred
- [x] Updated "Done when" to reference orchestrator final validation gate
- [x] Updated `CURRENT.md` with completed slices and remaining validation state
- [x] No application source code, dependencies, migrations, or `.env` modified
- [x] Feature 04 final validation gate passed: 256 tests, Ruff clean, mypy clean

## Feature 09 — Documentation reconciliation complete (2026-08-05)

- [x] Reconciled 7 context files to Binance USDⓈ-M Futures per `dispatch/ARCHITECTURE.md`
- [x] Ran documentation consistency checks — 1 finding reported below
- [x] No application source code, dependencies, migrations, or `.env` modified
- [x] No Feature 09 paper pipeline implemented

### Changes applied

| File | Changes |
|------|---------|
| `context/architecture.md` | Purpose line, rate-limit paragraph (USDⓈ-M Futures, safe phrasing, no unverified numbers), Broker interface testnet reference |
| `context/project-brief.md` | "first concrete integration" → live-data/execution USDⓈ-M Futures; authenticated adapter → Phase 11; paper-to-testnet workflow |
| `context/roadmap.md` | Overview workflow, Phase 3/8/11 goals, deferred scope (COIN-M), MVP completion criteria all updated to USDⓈ-M Futures |
| `context/tech-stack.md` | WebSocket section names `fstream` integration |
| `context/features/09-live-trading.md` | Phase 11 title/description, configuration broker name (`binance_usdm`), BinanceBroker example replaced with deferred Phase 11 stub (no `defaultType: spot`), acceptance criterion |
| `context/features/10-journal-analytics.md` | Removed stale "Spot" qualifier from 24/7 annualization note |
| `context/features/13-polish-testing.md` | Testnet boundary wording — removed "Binance Spot" qualifier |

### Consistency check — 1 finding

**Finding F1 (stale — resolved 2026-08-05):** `context/features/08-live-data-streaming.md`
line 48 stated "Binance Spot live streaming... are deferred." — corrected to state that
Feature 08 provides Binance USDⓈ-M Futures live streaming and Feature 09 consumes it.
OANDA streaming and COIN-M Futures remain deferred.

All other remaining `Binance Spot` references in `context/` are intentional historical
references (Feature 03/05 historical provider, data format docs, library-docs implementation
note) per ARCHITECTURE.md preservation rule.

## What comes next

- **Next scheduled feature:** Feature 05 — Backtesting.

### Feature 07 — Contracts slice (2026-08-04)

- [x] Added immutable Order, Fill, Position, and Trade domain contracts with UUID,
      instrument_id, Decimal, UTC, and one-way Futures semantics.
- [x] Added broker-facing OrderResult, AccountInfo, BrokerSnapshot, and Broker protocols.
- [x] Added typed frozen keyword-only execution event payloads and focused tests.
- [x] No persistence, Binance connectivity, or execution engine implemented.

### Feature 07 — Persistence and paper broker slice (2026-08-04)

- [x] Started implementation of the PostgreSQL execution persistence boundary and
      Futures-aware Paper Broker.

### Feature 07 — Persistence and paper broker slice complete (2026-08-04)

- [x] Added migration 007 and SQLAlchemy execution models for orders, append-only fills,
      active one-way positions, and trade lifecycle aggregates.
- [x] Added UUID/NUMERIC repository protocols, SQLAlchemy implementation, and in-memory
      deterministic implementation with client, broker-order, and broker-execution idempotency.
- [x] Added isolated-margin Futures Paper Broker with 1x default/2x hard maximum leverage,
      configurable 0.05% taker fee, separate funding, executable bid/ask and backtest prices,
      mark-price P&L, protective triggers, maintenance margin, and non-negative liquidation.
- [x] Added focused Paper Broker tests.
- [x] Execution Engine and account-level net exposure coordinator remain deferred to the next
      Feature 07 slice.
- [x] Backend pytest: 300 passed
- [x] Ruff: clean
- [x] mypy: clean

### Feature 07 — Net exposure coordinator and RiskApproved integration (2026-08-04)

- [x] Added account/instrument serialization, strategy-keyed virtual exposures, deterministic
      net target/delta calculation, explicit close-before-reversal, and FIFO allocation helper.
- [x] Added ExecutionEngine RiskApproved subscription with durable client IDs before broker I/O,
      persistence-before-event ordering, provenance propagation, duplicate-fill handling,
      partial-fill handling, and unknown-state blocking.
- [x] Reconciled Feature 06's former instrument-wide conflict rule to the approved
      cross-strategy policy while retaining same-strategy no-scaling behavior.
- [x] Added multi-strategy netting and reversal integration coverage.
- [x] Added strategy-aware reservation tests, typed execution fixtures, coordinator idempotency/
      FIFO/event coverage, and cumulative trade fee/P&L updates for partial fills.
- [x] Focused validation: 57 passed; full backend suite: 308 passed; slice Ruff/mypy clean.

### Slice 2 review fixes (2026-08-04)

- [x] Fully annotated Paper Broker test helpers and async test signatures.
- [x] Reconciled execution schema documentation with migration 007/ORM, including
      NUMERIC(28, 12) precision and idempotency indexes.
- [x] Added accumulation, weighted-average, partial/full close, protective trigger,
      liquidation, re-marking, and repository-backed persistence/idempotency coverage.
- [x] Validation: 304 pytest passed; Ruff and mypy clean.

### Feature 06 final validation (2026-08-04)

- [x] Implemented typed risk events, YAML risk configuration, and the pure RiskEngine plus
      EventBus adapter with isolated transient reservations.
- [x] Added event, configuration, and comprehensive risk-engine behavior tests.
- [x] Backend pytest: 266 passed
- [x] Ruff: clean
- [x] mypy: clean

### Feature 07 — Reconciliation and recovery slice (2026-08-04)

- [x] Implemented broker-snapshot reconciliation behind broker/repository/coordinator protocols
- [x] Added authoritative order, fill, and position comparison with provenance preservation,
      unknown-order recovery, fill idempotency, durable reconciliation records, and fail-closed
      coordinator blocking/unblocking
- [x] Added startup, reconnect, periodic invocation methods and matching, missing-state,
      mismatch, duplicate-execution, unblock, and restart-recovery tests

### Feature 07 — Reconciliation review fixes (2026-08-04)

- [x] Paper Broker reconciliation now returns its complete order/fill ledger plus positions
- [x] Added real Paper Broker regression coverage, missing-local-fill recovery, orphan-position
      closure, mode-scoped fills, lifecycle entry points, bot/account scope, and coordinator
      blocking tests
- [x] Reconciliation test helpers are fully typed; changed-slice mypy is clean
- [x] Validation: 322 pytest passed; Ruff clean; mypy clean

### Feature 07 — Final validation gate (2026-08-04)

- [x] Whole-feature review passed with zero Critical or Important findings
- [x] Backend pytest: 322 passed
- [x] Ruff: clean
- [x] Feature 07 source, tests, and migration mypy: clean
- [x] Feature 07 complete; next scheduled feature is Feature 05 — Backtesting

### Feature 05 — Task 1 (2026-08-04)

- [x] Extended CandleRepository with deterministic inclusive UTC reads in SQLAlchemy and memory
- [x] Added immutable BacktestConfig, BacktestStatus, BacktestResult, BacktestRun, and BacktestTrade contracts
- [x] Added focused candle and contract validation tests
- [x] Focused validation: 37 passed; Ruff clean; changed-slice mypy clean
- [x] Migration, replay engine, API, and UI remain deferred
