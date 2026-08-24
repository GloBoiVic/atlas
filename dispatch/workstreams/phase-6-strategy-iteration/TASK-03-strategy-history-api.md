# Task 03 — Strategy History API

## Status

**COMPLETE** — added the bounded, read-only Strategy catalog and StrategyVersion
history API without a schema migration, source-content exposure, UI, parameter
form, or comparison surface.

## Changes

- Added repository reads for stable Strategy catalog ordering and immutable
  Experiment usage facts (count and last-used timestamp) at Strategy and
  StrategyVersion scope.
- Added explicit Pydantic response contracts for:
  - `GET /api/v1/strategies`
  - `GET /api/v1/strategies/{strategyKey}`
- Added Atlas-owned display identity (`Strategy name + v{version_number}`),
  persisted version number, source fingerprint, creation time, implementation
  key, manifest paths/byte lengths, parameter schema, timeframe, warm-up, state
  schema, capabilities, and usage facts.
- Added exact local registry availability checks with a stable unavailable
  reason. Optional `gitSha` is returned as secondary provenance only.
- Kept `exact_source_snapshot` server-side; no route returns source contents.
- Registered the Strategy router in the application factory. No persistence
  schema or migration files were changed.

## Validation receipts

- `uv run ruff check backend/api/app.py backend/api/schemas.py backend/api/strategies.py backend/persistence/strategy_repository.py` — **passed**.
- `uv run ruff format --check backend/api/app.py backend/api/schemas.py backend/api/strategies.py backend/persistence/strategy_repository.py` — **passed**.
- `python -m compileall -q backend/api backend/persistence` — **passed**.
- `uv run pytest backend/tests/strategies backend/tests/domain -q` — **93 passed**.
- Existing integration attempt (`test_strategy_persistence.py` and
  `test_api_experiments.py`) reached the configured `atlas_test` database but
  failed because relation `instruments` does not exist; this is an environment
  schema/setup issue and did not reach the new route assertions.

## Blockers

None within Task 03 scope. The integration database must be migrated before
HTTP history-route receipts can be collected.
