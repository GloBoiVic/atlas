# T006 — Validation remediation

Status: `BUILD COMPLETE`

## Changes

- Repaired `0014_result_metric_state_details` to descend from the established
  `0008_proposal_constraints` head. Alembic now reports one authoritative head.
- Updated the migration-head expectation to the new approved schema head.
- Added the smallest explicit accounting/invariant classifier: known fill,
  Trade, Position, financial-projection, sequence, and direction invariant
  failures receive `ACCOUNTING_INVARIANT`, while retaining the existing
  validation category and sanitized durable failure behavior.
- Added focused regression coverage for the accounting classification.
- Did not modify T003's owned artifact or unrelated dispatch files.

Files changed: `backend/persistence/migrations/versions/0014_result_metric_state_details.py`,
`backend/tests/test_migration_revision.py`, `backend/experiments/runner.py`,
`backend/tests/experiments/test_runner_diagnostics.py`.

## Checks

- `pytest -q backend/tests/test_migration_revision.py backend/tests/experiments/test_runner_diagnostics.py` — **13 passed**.
- `alembic heads` — **PASS**, single head `0014_result_metric_state_details`.
- `python -m compileall -q backend` — **PASS**.
- `git diff --check` — **PASS**.

## Concerns

- PostgreSQL-backed migration upgrade/downgrade remains unverified in this
  environment because `ATLAS_TEST_DATABASE_URL` is unavailable; the full
  validation suite must rerun with that database configured.
- The stale T003 receipt preamble remains unchanged as instructed; Solo should
  reconcile that metadata before REVIEW.
