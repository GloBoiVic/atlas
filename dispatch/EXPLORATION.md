# Exploration — Feature 10 Journal & Analytics

## Readiness

- Feature 09 is merged into `main`; the working tree is clean.
- `TradeClosed(trade=...)` is implemented and emitted by the execution engine.
- Trade records already carry signal metadata, market context, strategy-version identity,
  fees, P&L, and lifecycle timestamps.
- Journal and analytics packages, persistence, repositories, routes, schemas, and UI do not
  yet exist.

## Existing patterns and files

- Execution contracts/events: `backend/execution/models.py`, `backend/core/events.py`,
  `backend/execution/engine.py`.
- Persistence protocols/implementations: `backend/persistence/repositories/` and
  `backend/persistence/models.py`; latest migration is 009.
- API composition: `backend/api/app.py`, `backend/api/deps.py`,
  `backend/api/routes/backtests.py`, and `backend/api/schemas.py`.
- Frontend page/API pattern: `frontend/src/app/backtests/` and
  `frontend/src/lib/api.ts`; Feature 11 owns the global navigation shell.

## Gaps

- Journal domain model/service and idempotent `JournalRepository` implementations.
- `journal_entries` ORM model and migration 010; documented journal numeric precision must be
  reconciled with the existing trade precision.
- Analytics metrics/service with canonical formulas, undefined-value behavior, and tests.
- Journal and analytics API routes, schemas, dependency wiring, and registration.
- Journal and analytics page-level UI and API client functions.
- Focused repository, service, metrics, API, and frontend validation.

## Architectural questions for Architect

1. Resolve `strategy_name`: repository lookup from `strategy_version_id` versus changing the
   execution `Trade` contract. Exploration recommends lookup without changing Feature 07.
2. Decide whether Feature 10 analytics is canonical for backtest metrics or remains a separate
   journal-entry analytics implementation, and define any reconciliation work.
3. Choose the authoritative analytics source: journal entries or trades, while preserving the
   journal as an enriched historical record.
4. Define Sharpe return-series construction, including calendar-day bucketing and gap days.
5. Decide whether marked open-trade analytics are in scope now or deferred as a separate view.
6. Confirm journal-table precision and immutable denormalized `strategy_name` semantics.
7. Confirm Feature 10 owns page components while Feature 11 owns navigation-shell integration;
   the Trades page remains Feature 11.

## Proposed vertical slices

1. Domain, migration, ORM, repository protocols, and in-memory/SQLAlchemy parity.
2. TradeClosed journal service with strategy-name resolution and idempotency.
3. Canonical analytics metrics and service.
4. Journal/analytics API, schemas, dependency injection, and tests.
5. Journal page-level UI.
6. Analytics page-level UI and chart, with Feature 11 shell integration deferred.

## Risks and gates

- Paper/live close events must continue to emit complete `TradeClosed` payloads.
- Decimal money/return serialization and explicit undefined metrics require end-to-end tests.
- Open trades must remain excluded from canonical metrics.
- Run backend Ruff, mypy, and tests; frontend lint, typecheck, build, and available tests.
