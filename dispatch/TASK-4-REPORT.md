# Feature 10 Task 4 Report — Journal/Analytics API layer

## Implemented

- Added Pydantic transport models for enriched journal entries, notes updates, canonical
  performance metrics, and equity points. Decimal monetary values and the exact total-return
  ratio are serialized as strings; statistical ratios remain floats and undefined values remain
  `null`.
- Added thin `GET /journal`, `GET /journal/{entry_id}`, and
  `PATCH /journal/{entry_id}/notes` routes with inclusive filters, UUID/date validation,
  not-found handling, and infrastructure error mapping.
- Added `GET /analytics` with optional UTC bounds and a response containing the service-owned
  metrics and derived equity series. The route does not recalculate metrics.
- Added dependency factories and app registration while preserving the existing backtests
  routes and dependency/session ownership patterns.
- Added focused API tests covering filters, empty results, detail 404s, notes updates, UTC and
  UUID validation, analytics serialization/nulls, fail-closed scope configuration, and the
  existing backtests API.

## Starting-equity limitation

The current repository has no configured, account-scoped starting-equity/account-selection
provider for the API. The implementation therefore exposes an explicit `AnalyticsScope`
dependency seam and returns HTTP 503 when it is not configured. It never hardcodes an equity
value and never accepts account or secret material from the browser. A deployment can override
`get_analytics_scope` with its trusted account-scoped source when that source is introduced.

## Validation

- Focused journal/analytics, backtests, journal-service, and metrics tests: 27 passed.
- Full backend pytest: 452 passed, with one pre-existing frontend Dockerfile assertion failure.
- Ruff: clean.
- Changed-slice mypy: clean.
