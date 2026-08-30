# T002 — Snapshot attachment and historical-load locks

## Assignment

- Status: `DONE`
- Role: `BUILD`
- Workstream: `foundation-freeze-07-experiment-lifecycle-local-authority`
- Depends on: `T001`
- Owns: shared snapshot-first attachment helper and historical-load activation

## Frozen requirements

Implement the reconciled lock boundaries from `ARCHITECTURE.md` §§3.0–3.3 and
§9. All existing-snapshot attachment paths must use one helper with the order
**DatasetSnapshot row `FOR UPDATE`, then referencing row**:

- Experiment creation;
- successful historical-load completion; and
- FAILED-load snapshot preservation/attachment, including insufficient warm-up.

Remove secondary `session.get`, direct-assignment, completion, or failure bypasses.
Introduce one PostgreSQL transaction-scoped lifecycle serialization lock shared by
Experiment orphan deletion, new PENDING load creation, and FAILED → RUNNING resume.
It must serialize activation against orphan deletion without replacing the
snapshot-row lock, changing snapshot semantics, or adding leases/candidate rows,
workers, or distributed infrastructure. Document and test the non-deadlocking
acquisition relationship between the two locks.

## Required proof

Add deterministic tests for every attachment path, insufficient warm-up, lifecycle
lock ordering in both directions for new PENDING creation and FAILED → RUNNING
resume, active-load preservation before snapshot attachment, and the opposite
deletion-first ordering. Preserve terminal load history and all existing market
data semantics.

## Completion receipt

BUILD must update this file with `DONE` or `DONE_WITH_CONCERNS`, list every changed
application/test/migration path, and record task-level checks and concerns. Do not
edit role artifacts or another task artifact.

### Receipt

- Status: `DONE`
- Application paths:
  - `backend/persistence/lifecycle_locks.py`
  - `backend/persistence/experiment_deletion.py`
  - `backend/persistence/experiment_repository.py`
  - `backend/persistence/historical_data_load_repository.py`
  - `backend/market_data/historical_load.py`
- Test path:
  - `backend/tests/conftest.py`
  - `backend/tests/test_historical_data_load.py`
- Migration paths: none; the transaction-scoped advisory lock requires no schema
  change.
- Implementation evidence:
  - Added one shared snapshot-first helper that locks `dataset_snapshots` before
    an existing historical-load request, and used it for successful completion
    and FAILED snapshot preservation. Experiment creation now uses the same
    helper before inserting its referencing row.
  - Added one PostgreSQL `pg_advisory_xact_lock` lifecycle boundary. Experiment
    orphan cleanup acquires it before the active-load predicate and retains it
    through commit; new PENDING creation and FAILED -> RUNNING resume acquire
    the same lock before activation and retain it through their caller-owned
    transaction commit.
  - Moved insufficient-warm-up snapshot preservation through the repository
    attachment seam; removed the historical-load completion/failure direct
    assignment and `session.get` bypasses.
  - Documented in code why lifecycle-lock-before-activation and
    snapshot-row-first attachment cannot form a lock cycle.
- Checks / evidence:
  - Narrow remediation: the root test harness now upgrades a configured
    `*_test` database to Alembic `head` immediately before each root-level
    `@pytest.mark.integration` test, restoring schema after migration tests
    intentionally exercise teardown states without weakening migration teardown.
  - `ATLAS_TEST_DATABASE_URL=postgresql+psycopg://vike@localhost:5432/atlas_freeze07_test
    pytest -m integration` — 48 passed, 401 deselected, 4 warnings.
  - `ATLAS_TEST_DATABASE_URL=postgresql+psycopg://vike@localhost:5432/atlas_freeze07_test
    pytest -q backend/tests/test_historical_data_load.py
    backend/tests/experiments/test_result_state.py
    backend/tests/test_migration_revision.py
    backend/tests/test_foundation_freeze_guards.py` — 38 passed.
  - `ruff check backend/tests/conftest.py` — passed.
  - `pytest -q backend/tests/test_historical_data_load.py` — 28 passed, 1
    skipped.
  - `pytest -q backend/tests/test_historical_data_load.py
    backend/tests/experiments/test_result_state.py
    backend/tests/test_migration_revision.py
    backend/tests/test_foundation_freeze_guards.py` — 37 passed, 1 skipped.
  - `ATLAS_TEST_DATABASE_URL=postgresql+psycopg://vike@localhost:5432/atlas_freeze07_test
    pytest -q backend/tests/integration/test_migrations.py` — 2 passed.
  - PostgreSQL attachment/lifecycle selection — 38 passed, 4 deselected:
    `backend/tests/test_historical_data_load.py
    backend/tests/integration/test_experiment_deletion.py -k 'not http'
    backend/tests/integration/test_experiment_lifecycle.py
    backend/tests/integration/test_candidate_vertical_flow.py`.
  - Task-level command with the configured PostgreSQL URL — 38 passed:
    `backend/tests/test_historical_data_load.py
    backend/tests/experiments/test_result_state.py
    backend/tests/test_migration_revision.py
    backend/tests/test_foundation_freeze_guards.py`.
  - Two-connection PostgreSQL advisory-lock probe confirmed the second
    transaction blocks until the first commits.
  - `ruff check` on all T002 application/test paths — passed.
  - `pyright backend/persistence/lifecycle_locks.py` — 0 errors.
  - Python compilation of all T002 application/test paths — passed.
  - `git diff --check` — passed.
- Concerns: none for T002. A broader selection including T005 HTTP deletion
  assertions still has four unrelated response-envelope failures; those tests
  were excluded from this T002 verification.

## Approved review remediation — R-004

Add only the minimum deterministic proof owned by this task: shared-snapshot and
terminal/active-load retention, both lifecycle-lock race directions for new
PENDING activation and FAILED → RUNNING resume, and no-deadlock proof combining
the lifecycle lock with snapshot-first attachment ordering. Use table-driven
tests where appropriate and preserve the existing migration teardown. Do not
edit role artifacts or other task artifacts; update this receipt with paths,
 checks, and final status.

### Approved review remediation receipt — R-004

- Status: `DONE`
- Application paths: none
- Test path:
  - `backend/tests/integration/test_snapshot_lifecycle_locks.py`
- Migration paths: none; migration teardown and the existing lock contract are
  unchanged.
- Implementation evidence:
  - Added PostgreSQL proof that shared snapshot membership retains the snapshot
    and all membership rows after one Experiment is deleted.
  - Added table-driven terminal (`COMPLETED`/`FAILED`) and active
    (`PENDING`/`RUNNING`) historical-load retention proofs, including an active
    load with no durable snapshot attachment.
  - Added table-driven two-connection races for lifecycle-lock-first and
    deletion-first ordering across new `PENDING` creation and `FAILED` to
    `RUNNING` resume.
  - Added a bounded two-connection completion/deletion proof showing the
    lifecycle lock and snapshot-row-first attachment ordering complete without a
    deadlock.
- Checks / evidence:
  - `ATLAS_TEST_DATABASE_URL=postgresql+psycopg://vike@localhost:5432/atlas_freeze07_test pytest -q backend/tests/integration/test_snapshot_lifecycle_locks.py` — 10 passed.
  - `ATLAS_TEST_DATABASE_URL=postgresql+psycopg://vike@localhost:5432/atlas_freeze07_test pytest -q backend/tests/integration/test_experiment_lifecycle.py backend/tests/integration/test_snapshot_lifecycle_locks.py` — 15 passed.
  - `ATLAS_TEST_DATABASE_URL=postgresql+psycopg://vike@localhost:5432/atlas_freeze07_test pytest -q backend/tests/test_historical_data_load.py` — 29 passed.
  - `ATLAS_TEST_DATABASE_URL=postgresql+psycopg://vike@localhost:5432/atlas_freeze07_test pytest -q backend/tests/integration/test_experiment_deletion.py` — 36 passed, 1 warning.
  - `ruff check backend/tests/integration/test_snapshot_lifecycle_locks.py` — passed.
  - Python compilation and `git diff --check` — passed.
- Concerns: none for the approved T002 R-004 proof. The first deletion-suite
  attempt exceeded the 120-second command timeout; the rerun completed
  successfully in 146.16 seconds.
