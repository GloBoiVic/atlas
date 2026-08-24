# Task 04 — Experiment Parameters

## Status

**COMPLETE** — added additive StrategyVersion availability/identity data and
schema-driven manual parameter entry while preserving server validation and the
atomic immutable Experiment creation path.

## Changes

- Extended configuration options with `displayName`, `createdAt`,
  `executionAvailable`, and `unavailableReason`; unavailable versions remain
  visible but are disabled for new creation.
- Added explicit response contracts for the configuration-options payload.
- Rebuilt the Experiment form controls from the selected persisted schema.
  Integer values are converted to integers at submission; decimal values stay
  decimal strings at the UI/API boundary.
- Added inline finite/type/inclusive-range errors for manually typed values.
- Rendered `min == max` parameters read-only with “Fixed by methodology”; the
  fixed value is still submitted.
- Reset parameter values to persisted defaults on StrategyVersion selection,
  invalidated coverage on version/parameter/period changes, and blocked create
  until coverage and parameters are valid.
- Updated one stale exact-registry test lookup to select the preserved v1
  implementation after multi-version registration.

## Validation receipts

- `uv run ruff check backend/api/experiments.py backend/api/schemas.py backend/tests/experiments/test_configuration.py` — **passed**.
- `uv run pytest backend/tests/experiments/test_configuration.py -q` — **3 passed**.
- `python -m compileall -q backend/api` — **passed**.
- `npm run lint:web` — **passed**.
- `npm run typecheck:web` — **passed**.
- Focused frontend tests (`experiment_list.test.tsx`, `experiment_results.test.tsx`) — **5 passed**.

## Scope / blockers

No blocker. No history UI, comparison, migration, optimization, or PAPER/LIVE
surface was added. Generated API client refresh remains in the ordered contract
freshness gate.
