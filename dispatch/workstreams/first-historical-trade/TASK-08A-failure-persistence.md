# TASK-08A — Failure persistence correction

Status: DONE

## Correction

- Added forward-only Alembic revision `0005_phase_3_failure_persistence`.
- Extended the existing `experiments` table/model with immutable terminal
  `failure_category`, `failure_code`, and bounded `failure_detail` columns.
- Added database checks for the approved failure categories, uppercase safety
  codes, control-character-free details, and FAILED/non-FAILED consistency.
- Updated the existing Experiment immutability trigger so failure facts may be
  written only during the RUNNING → FAILED transition and cannot be changed or
  deleted afterward.
- Updated `ExperimentRepository.mark_failed` and runner terminal handling to
  persist the categorized, sanitized failure projection through the repository
  boundary. No new table, API, UI, event, logging system, or Phase 4 behavior
  was added.

## Validation receipts

- `pytest -q backend/tests/integration/test_migrations.py` — **2 passed**;
  verified upgrade, head checks, downgrade-to-base, re-upgrade, approved table
  set, and failure columns.
- `pytest -q backend/tests/integration/test_runner_failure_persistence.py` —
  **1 passed** against controlled PostgreSQL; runner failure was persisted with
  category/code/detail and terminal mutation was rejected by the database.
- `pytest -q` — **168 passed, 1 skipped**, one existing FastAPI/httpx warning.
- `pytest -q backend/tests/test_migration_revision.py backend/tests/experiments
  backend/tests/execution backend/tests/risk` — **18 passed**.
- `ruff check` on all changed implementation, migration, and test files —
  **passed**.
- `python -m compileall -q backend/experiments backend/persistence
  backend/tests/integration/test_runner_failure_persistence.py` — **passed**.
- `git diff --check` on changed tracked paths — **passed**.

## Migration compatibility

Preserved. Existing revision `0004_phase_3_first_historical_trade.py` was not
rewritten; the correction is a forward migration chained from its bounded
revision ID. The PostgreSQL migration cycle (upgrade → downgrade base →
upgrade head) passed, and the revised terminal trigger is restored on downgrade
of `0005`.

## Scope and exclusions

Real EMA behavior and persisted LONG/SHORT golden fixtures remain Task 9. No
Git-changing commands were run, and TASK-02/TASK-08 reports were not modified.
