# Task 05 — Comparison API

## Status

**COMPLETE** — implemented the bounded, stateless comparison read service and
typed GET contract for immutable COMPLETED Experiment facts. No comparison
state, migration, write path, ranking, delta, or UI surface was added.

## Changes

- Added `ExperimentComparisonReadService` with a hard two-to-four bound,
  request-order A–D slots, whole-request eligibility failures, and explicit
  `EXPERIMENT_NOT_FOUND`, `EXPERIMENT_NOT_COMPLETED`, and
  `COMPARISON_RESULT_UNAVAILABLE` errors.
- Composed StrategyVersion, canonical Instrument, DatasetSnapshot, UTC period,
  typed parameter snapshots, capital/base currency, Risk, simulation, model,
  metric-contract, and existing Phase 5 metric-envelope facts.
- Added immutable typed difference/warning dataclasses. Differences use exact
  Decimal equality and recursively canonicalized snapshots; warnings are
  deduplicated and emitted in the approved fixed precedence.
- Added `strongParameterIsolation` and `changedParameterKeys` as factual
  configuration classifications only. No metric deltas or quality judgments
  are calculated.
- Added `GET /api/v1/experiments/comparison?experimentId=...` before the
  dynamic Experiment-ID route with explicit Pydantic success models and the
  existing structured error envelope. Response excludes trades, equity series,
  source contents, and comparison IDs.

## Validation receipts

- `uv run ruff check` on comparison service, API, schemas, and focused tests:
  **passed**.
- `uv run python -m compileall -q backend/experiments backend/api`:
  **passed**.
- Focused comparison tests: **5 passed** (ordering, Decimal equality,
  parameter isolation, bounds, and whole-request status/error handling).
- Existing Experiment result/metric tests: **35 passed**.
- No persistence model, migration, or durable write was introduced.

## Blockers

None within Task 05 scope. Full HTTP/database receipts remain subject to the
existing local `atlas_test` schema setup issue reported by Task 03; final
validation remains the ordered Task 11 gate.
