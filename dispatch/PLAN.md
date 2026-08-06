# Plan — Feature 10 Journal & Analytics

## Goal

Record completed trades as enriched, idempotent journal entries and expose reproducible
closed-trade analytics through API and page-level UI.

## Implementation sequence

1. Add migration 010, journal ORM/domain contracts, repository protocols, SQLAlchemy and
   in-memory implementations, and parity tests.
2. Add TradeClosed journal service with strategy-name lookup, immutable context snapshots,
   notes support, and duplicate-event tests.
3. Add analytics metric functions and service over authoritative closed trades, including
   total return, P&L, win rate, closed-trade daily Sharpe, max drawdown, profit factor, and
   equity-series output.
4. Add API schemas, routes, dependency factories, app registration, serialization, filtering,
   not-found handling, and endpoint tests.
5. Add Journal page-level UI with accessible table, context display, and notes editing.
6. Add Analytics page-level UI with date filters, metric cards, explicit undefined states, and
   equity chart; leave global navigation to Feature 11.

## Required validation

- Backend focused and full pytest, Ruff, and mypy.
- Frontend lint, typecheck, production build, and configured tests if available.
- Migration metadata/isolation checks and repository implementation parity.
- No secrets, floats for backend money, client-side metric recalculation, or scope leakage.
