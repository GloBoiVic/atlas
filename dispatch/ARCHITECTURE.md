# Architecture — Feature 10 Journal & Analytics

## Scope

Build the journal projection, canonical closed-trade analytics, API endpoints, and page-level
Journal/Analytics UI. Feature 11 owns global navigation and dashboard-shell integration. The
Trades page remains Feature 11. No bot-management work, marked open-trade analytics, or
authenticated testnet work is included.

## Authoritative decisions

1. **Source of truth:** persisted closed `Trade` records are authoritative for analytics.
   Journal entries are enriched, human-readable projections and must not become a second
   accounting ledger.
2. **Journal projection:** `TradeClosed(trade=...)` creates exactly one journal entry keyed by
   `trade_id`. Repeated events are harmless. Notes are independently mutable; trade-derived
   fields are immutable snapshots.
3. **Strategy identity:** do not change Feature 07's `Trade` contract. Resolve the strategy
   name from `strategy_version_id` at journal creation and persist the resolved name.
4. **Metrics:** Feature 10 owns canonical formulas and undefined-value behavior. Monetary values
   and total-return ratios use Decimal/decimal-string transport; statistical ratios use floats.
5. **Sharpe:** label the MVP metric `closed_trade_daily_sharpe`: UTC calendar-day closed-trade
   equity returns, zero-return gap days, zero risk-free rate, 365 annualization, and `null` for
   fewer than 30 observations or zero variance.
6. **Open trades:** excluded from canonical metrics. Marked-equity metrics are deferred to a
   separate future view and must not be mixed into this response.
7. **Equity curve:** analytics response includes a derived closed-trade equity series for UI
   charting; the browser does not recalculate canonical metrics.
8. **Persistence precision:** journal monetary, price, and quantity columns use
   `NUMERIC(28,12)` to match execution persistence.
9. **Historical provenance:** journal stores the resolved strategy name and copied signal/market
   context as immutable historical snapshots.

## Component boundaries

- `backend/journal`: domain model and TradeClosed projection service.
- `backend/analytics`: metric definitions and service reading closed trades.
- `backend/persistence`: migration 010, ORM model, repository protocols and implementations.
- `backend/api`: thin journal/analytics routes, schemas, dependencies, and registration.
- `frontend`: page-level Journal and Analytics views plus API client types/functions.
- Feature 11 later integrates navigation and shared operational shell.

## Ordered vertical slices

1. Persistence/domain contracts and repository parity.
2. Idempotent TradeClosed journal projection and tests.
3. Canonical analytics metrics/service and fixture-driven tests.
4. Journal/analytics API, schemas, DI, registration, and API tests.
5. Journal page-level UI and notes editing.
6. Analytics page-level UI, filters, metrics, and equity chart.

## Safety and quality gates

- Preserve Decimal precision and explicit null behavior across API boundaries.
- Verify closed-trade filtering, date bounds, idempotency, and strategy-version provenance.
- Do not introduce alternate execution, trade, risk, or broker semantics.
- Run backend pytest, Ruff, and mypy; frontend lint, typecheck, build, and available tests.
