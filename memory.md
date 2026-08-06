# Memory — Feature 10 Journal & Analytics + Feature 11/12 Operational UI & Bot Management

Last updated: 2026-08-06

## What was built

### Previously completed (Features 01–10)

- Feature 02 Core Infrastructure (EventBus, Clock, config, logging, supervisor contracts)
- Feature 04 Strategy Engine (Signals, registry, per-bot engine, warm-up, example strategies)
- Feature 05 Backtesting (deterministic replay engine, ORM, API, frontend UI with 8-metric grid)
- Feature 06 Risk Engine (configuration-driven stops, max-risk sizing, bot isolation, reservations)
- Feature 07 Execution Layer (Order/Fill/Position/Trade contracts, Futures Paper Broker, reconciliation, net exposure coordinator, Alembic migration 007)
- Feature 08 Live Streaming (USDⓈ-M Futures fstream subscriptions, candle dedup, MarketContext aggregation, reconnect/backoff, feed runner, live provider registry)
- Feature 09 Paper Trading (USDⓈ-M Futures alignment, LivePaperPipeline, deterministic funding/maintenance, restart reconstruction, canonical `binance_usdm` identity, account-level netting)
- Feature 10 Journal & Analytics (JournalEntry ORM/domain/repos, TradeClosed projection, closed-trade analytics service/routes/API, page-level `/journal` and `/analytics` UI, analytics equity curve, Dockerfile API recovery, migration 010)

### Feature 11 Operational UI + Feature 12 Bot Management

- **Shell foundation**: Atlas shell with persistent `TopNav`, canonical 9-route navigation (`/dashboard`, `/strategies`, `/backtests`, `/paper`, `/testnet`, `/trades`, `/journal`, `/analytics`, `/settings`), TanStack Query provider, Shadcn primitives, common status/loading/error/stale/disconnected boundaries
- **Backend read models**: typed REST endpoints for dashboard summary, account summary, positions, bots, trades, strategies, strategy versions — all with Pydantic v2 `extra="forbid"`, UTC/Decimal-string validation, `AnalyticsScope` deployment-configured via `settings.ANALYTICS_ACCOUNT_ID` + `settings.ANALYTICS_STARTING_EQUITY`
- **Dashboard REST view**: full operational view with P&L, positions, account, active bots, recent trades, health, freshness; polls every 15s with 30s stale threshold; explicit polling/stale/disconnected states
- **Bot management backend**: `BotService` with CRUD + lifecycle (`start`/`stop`/`pause`/`resume`), idempotent create with canonical numeric identity (`__atlas_numeric__` tagged encoding), supervisor delegation, mode/strategy validation, production mode rejection, fail-closed on reconciliation uncertainty (503)
- **Bot management UI**: strategies/paper/testnet pages, bot create/edit forms, lifecycle controls with native `<dialog>` confirmation (scope + consequence, no optimistic state), Sonner toasts on API confirmation
- **Migrations 011–013**: 011 persists strategy config JSONB, 012 adds `uq_bots_create_idempotency` with preflight duplicate check, 013 adds `config_identity` JSONB column and rebuilds constraint on it
- **Trades page**: REST-polled trade history with all states, Decimal-string footer copy
- **Settings page**: truthful "no backend contract exists" banner — zero form elements, zero fake controls
- **Lightweight Charts equity curve**: `LineSeries` wrapper on analytics page, bounded at 2000 points, UTC timestamps, ResizeObserver, accessible `role="img"`, no candlestick chart (deferred until candle REST API exists)
- **WebSocket gating**: operational WebSocket route disabled by default (`ENABLE_DEFERRED_OPERATIONAL_WEBSOCKET=False`); `DenyByDefaultAuthenticator` rejects all connections; test confirms default-off behavior
- **Validation**: 477 backend tests pass (full suite), public Ruff check passes, `npm run lint`/`npm run typecheck`/`npm run build` all pass; 3 pre-existing environment gaps documented (frontend test runner, Docker/PostgreSQL integration, mypy)
- **Final whole-feature review**: **PASS** — 0 Critical, 0 Important findings; 8 Minor (cosmetic/optimization/documentation)

## Decisions made

### From prior sessions

- Closed-trade analytics read authoritative persisted closed Trades; JournalEntry is an enriched projection from `TradeClosed`.
- Strategy names resolved from `strategy_version_id` at journal projection time; Trade semantics unchanged.
- Canonical MVP analytics exclude open trades. Closed-trade daily Sharpe uses UTC day buckets, zero-return gap days, zero risk-free rate, 365 annualization, explicit undefined states.
- Futures market data has distinct trade, executable bid/ask, mark, index, and funding semantics; `MarketContext` prevents treating mark/index prices as fill prices.
- Shared account-level netting is intentional shared state; strategy, risk, feed, and provenance state remain isolated per bot.
- Journal projections remain separate from the authoritative execution ledger, preserving enriched historical context.

### From this session

- **REST polling** is the authoritative MVP live mechanism. WebSocket operational route is gated/disabled by default. Future activation requires: cross-process EventBus bridging, deployment Cloudflare Access auth/proxy wiring, unique state-envelope IDs, send timeouts, and full acceptance tests.
- **Bot create idempotency** uses canonical identity `(account_id, mode, name, strategy_version_id, broker, instrument, timeframe, config_identity)` with `__atlas_numeric__` tagged encoding to distinguish numeric `1`, `1.0`, Decimal `1.00` from string `"1"`.
- **Migration 012** runs a preflight duplicate query with actionable error before adding `ON CONFLICT DO NOTHING` constraint — fails closed on pre-existing duplicates.
- **Migration 013** moves from `config` to `config_identity` column for the unique constraint; `config_identity` nullable so legacy rows are not mutated.
- **Settings page** renders truthful "no backend contract exists" state — no form elements, no fake controls, warns the user that setting read/write requires a backend contract.
- **Analytics upgraded** from SVG polyline to Lightweight Charts equity curve; all existing metrics, fields, templates, loading/empty/error/stale states preserved.
- **Confirmation UX** uses native `<dialog>` with `showModal()`, blocks background interaction, escape to cancel, `aria-labelledby` linkage, consequence text, and disabled confirm during mutation. No optimistic state before API confirmation.

## Problems solved

### From prior sessions

- Reconciled journal precision documentation with migration/ORM precision.
- Fixed zero-P&L UI rendering (zero remains neutral without parsing Decimal strings).
- Fixed empty analytics date filters serializing `undefined` query parameters.
- Resolved stale standalone Dockerfile test to match `/app/server.js` runtime layout.
- Resolved persistent API image `binutils` hash mismatches via HTTPS apt sources with retries.

### From this session

- Bot create idempotency required canonical identity with `__atlas_numeric__` encoding to handle Python Decimal/numeric/string type differences across SQLAlchemy and in-memory implementations — both repos now produce identical idempotency behavior.
- Migration 012 preflight checks discoverable pre-existing duplicates in a developer-friendly error message before the constraint is applied.
- Update identity collision (`PATCH /bots/{id}`) handled via pre-Flush conflict detection before SQL `IntegrityError` — produces a clean `409 BotIdentityConflictError` response.
- Bot mode type safety: replaced `as Mode` and `as "paper" | "testnet"` assertions with `isSupportedBotMode()` runtime guard with three-layer defense (early return alert block, disabled controls, type narrowing).
- WebSocket deferred gating implemented as a clean disabled-by-default route with `DenyByDefaultAuthenticator`, logged deferral reason, and `.env.example` documentation — producible test confirms it stays off.

## Eureka moments

- Futures market data has distinct trade, executable bid/ask, mark, index, and funding semantics; provider-neutral `MarketContext` prevents treating mark/index prices as fill prices.
- Shared account-level netting is intentional shared state; strategy, risk, feed, and provenance state remain isolated per bot.
- Journal projections should remain separate from the authoritative execution ledger, while preserving enriched historical context for human review.
- REST polling as the MVP baseline avoids the cross-process EventBus bridging, deployment auth/proxy, unique envelope IDs, and send-timeout problems that would be required for a production-safe WebSocket implementation — the deferred route correctly defaults off.

## Current state

- Feature 11 Operational UI + Feature 12 Bot Management are **complete and review-passed** (FEATURE-11/12: PASS — 0 Critical/Important findings, 477 backend tests, frontend lint/typecheck/build all pass).
- Bot create, lifecycle commands, and REST-polled dashboard are fully functional through the API with the `_UnavailableFactory`/`_UnavailableReconciler` defaults (real pipeline construction requires the worker process).
- All 9 canonical routes compile and render loading/error/empty/stale/populated states.
- WebSocket operational route is disabled by default and must be explicitly enabled (not recommended for MVP).
- Exposed settings `ANALYTICS_ACCOUNT_ID` and `ANALYTICS_STARTING_EQUITY` are required for analytics to populate; not yet documented in `.env.example` (Minor M7 from review).
- Work remains uncommitted by request on branch `feature/11-slice-6-operational-pages`.
- Three pre-existing environment gaps remain: frontend test runner, Docker/PostgreSQL integration, mypy.

## Next session starts with

1. Commit the working tree on `feature/11-slice-6-operational-pages` and merge into `main`.
2. Begin Feature 13 (Polish & Testing) for hardening, health monitoring, and endpoint safety gates.
3. Document `ANALYTICS_ACCOUNT_ID` and `ANALYTICS_STARTING_EQUITY` in `.env.example` (Minor M7 from final review).
4. Validate Docker Compose full-stack startup and PostgreSQL migration upgrade path (010→011→012→013) when environment permits.

## Open questions

- Authenticated USDⓈ-M Futures testnet execution remains deferred to Feature 09 Phase 11.
- Frontend test-runner infrastructure remains unconfigured.
- Topnav 57px screenshot provenance remains unresolved; 56px remains canonical.
- Candlestick chart deferred until a candle REST API endpoint is deployed.
- Settings read/write API requires a backend contract — deferred outside this session.
- WebSocket operational route activation blocked until cross-process EventBus bridge, deployment auth/proxy wiring, unique state-envelope IDs, and send timeouts are approved.
