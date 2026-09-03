# T001 — Runtime persistence and migration

- **Status:** `DONE`
- **Role:** `BUILD`
- **Workstream:** `paper-06-runtime-activation`
- **Branch:** `solo/paper-06-runtime-activation`
- **Depends on:** none
- **Owned artifact:** this file

## Objective

Implement the three approved PAPER 06 runtime persistence tables and the next Alembic migration from the actual PAPER 05 head. Add typed persistence contracts and repository primitives needed by later tasks, while preserving the frozen activation, cycle, and ownership constraints.

## Required boundaries

- Persist only the approved non-secret activation snapshot, lifecycle projection, operational projection, Strategy state, cycle evidence, and singleton ownership projection.
- Enforce the approved fixed OANDA Practice/USD/EUR_USD scope, lifecycle/status vocabularies, bounded canonical JSON, finite positive Risk value, lowercase SHA-256 fingerprints, foreign-key restrictions, and uniqueness constraints.
- Keep the live ownership authority as a dedicated PostgreSQL session-level advisory lock seam; do not substitute heartbeat age for lock ownership.
- Keep runtime tables separate from PAPER 05 attempt/claim/observation/reconciliation tables and historical Experiment persistence.
- Do not implement activation HTTP routes, scheduling, Strategy orchestration, or broker mutation in this task.

## Evidence required

- Migration upgrade/downgrade/re-upgrade and Alembic checks on a dedicated PostgreSQL test database.
- Deterministic contract/repository tests for constraints, idempotent immutable activation identity, cycle uniqueness, bounded state/evidence, and ownership generation guards.
- No real OANDA calls or credentials.

## Completion receipt

Implemented the PAPER 06 runtime persistence slice.

### Files changed

- `backend/runtime/persistence_contracts.py`
- `backend/runtime/__init__.py`
- `backend/persistence/models.py`
- `backend/persistence/runtime_repository.py`
- `backend/persistence/__init__.py`
- `backend/persistence/migrations/versions/0023_paper_runtime_activation.py`
- `backend/tests/runtime/test_runtime_persistence.py`
- `backend/tests/integration/test_runtime_repository.py`
- `backend/tests/integration/test_migrations.py`
- `backend/tests/test_migration_revision.py`

### Checks and evidence

- Focused runtime/PAPER tests: `11 passed`.
- Runtime persistence integration tests on dedicated `atlas_freeze07_test`: `2 passed`.
- Migration integration tests on dedicated `atlas_freeze07_test`: `3 passed`.
- Full non-integration/non-external backend suite: `978 passed, 4 skipped`.
- Alembic `upgrade head`, `current`, `check`, `downgrade 0022_paper_persistence`, and re-upgrade: passed; current head is `0023_paper_runtime_activation`.
- Ruff and Pyright changed-slice checks: passed.
- `git diff --check`: passed.
- No OANDA calls, credentials, activation, or broker mutation were used.

### Concerns / handoff

- The repository deliberately does not acquire the live advisory lock; `record_ownership_after_lock` is the durable write seam for T003's dedicated pinned PostgreSQL connection.
