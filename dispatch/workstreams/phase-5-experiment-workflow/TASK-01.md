# TASK-01 — Contract fixtures and migration

- **Task:** Implement approved blueprint task 1 only: additive Phase 5 metric contract, SQLAlchemy fields/checks/index, result creation defaults, and deterministic metric-state fixtures.
- **Agent:** backend builder
- **Model:** gpt-5.6-luna (`openai/gpt-5.6-luna`)
- **Branch:** `feature/phase-5-experiment-workflow`

## Changed files

- `backend/persistence/migrations/versions/0007_phase_5_metric_contract.py`
- `backend/persistence/models.py`
- `backend/persistence/experiment_repository.py`
- `backend/experiments/metric_contract.py`
- `backend/tests/integration/test_migrations.py`
- `backend/tests/test_migration_revision.py`

## Outcome

Implemented the additive revision after `0006_phase_4_persistence`. It adds nullable NUMERIC metric cache columns, legacy-safe JSONB metric states and schema version defaults, finite/range/state consistency checks, and the deterministic experiment ordering index. Existing Phase 4 result creation receives `LEGACY_UNCOMPUTED` defaults; terminal facts and output fingerprints are untouched. Added versioned metric-state vocabulary and calculation-free fixtures. No metrics execution wiring, lifecycle, API, frontend, or later task work was implemented.

## Exact validation receipts

- `pytest -q backend/tests/integration/test_migrations.py backend/tests/test_migration_revision.py` → **3 passed**. PostgreSQL migration test exercised clean upgrade, `command.check`, downgrade to `0006_phase_4_persistence`, upgrade to head, downgrade to base, and final upgrade.
- `ruff check backend/experiments/metric_contract.py backend/persistence/models.py backend/persistence/experiment_repository.py backend/persistence/migrations/versions/0007_phase_5_metric_contract.py backend/tests/test_migration_revision.py backend/tests/integration/test_migrations.py` → **All checks passed**.
- `python -m py_compile backend/experiments/metric_contract.py backend/persistence/migrations/versions/0007_phase_5_metric_contract.py` → **passed**.
- `pytest -q backend/tests/experiments/test_clock.py backend/tests/test_migration_revision.py` → **6 passed**.

## Evidence scope

Evidence covers migration graph integrity, PostgreSQL upgrade/downgrade/upgrade behavior, model/migration alignment via Alembic `check`, legacy-compatible column defaults, metric contract constants/fixtures, and existing clock/revision regression tests. The migration test database was restricted to the configured `*_test` database by the existing harness.

## Blocker/conflict

None. The working tree's pre-existing dispatch changes and `.codegraph/` remain untouched. No Git mutations were performed.
