# T001 — DELETE lock order correction

## Assignment

- Status: `DONE`
- Role: `BUILD`
- Workstream: `foundation-freeze-07-corrections`
- Depends on: none
- Owns: DELETE API/service lock boundary and focused tests

## Required implementation

Correct the DELETE workflow so it follows the frozen order **non-lock Experiment
read → DatasetSnapshot `FOR UPDATE` → Experiment `FOR UPDATE`**. Eliminate
duplicate lock ownership between `backend/api/experiments.py` and the deletion
service; do not add a second parallel preflight. Preserve exact human
confirmation facts, locked RUNNING precedence, stale-status mismatch behavior,
one caller-owned transaction, and existing deletion service semantics.

## Required proof

Add focused tests that observe the API/service boundary and prove the snapshot is
locked before Experiment, the API does not acquire a contradictory Experiment
lock first, and confirmation/error behavior remains unchanged. Use the smallest
deterministic seam available; do not broaden the test suite.

## Completion receipt

BUILD must update this file with final status, changed paths, checks/evidence, and
concerns. Do not edit PLAN.md, ARCHITECTURE.md, ACTIVE.md, VALIDATION.md, REVIEW.md,
or T002. Do not start pre-PAPER/PAPER work.

## BUILD completion receipt

- Final status: `DONE`
- Changed paths:
  - `backend/api/experiments.py`
  - `backend/persistence/experiment_deletion.py`
  - `backend/tests/integration/test_experiment_deletion.py`
- Checks/evidence:
  - `uv run ruff check backend/api/experiments.py backend/persistence/experiment_deletion.py backend/tests/integration/test_experiment_deletion.py` passed.
  - `python -m compileall -q backend/api/experiments.py backend/persistence/experiment_deletion.py backend/tests/integration/test_experiment_deletion.py` passed.
  - Added API SQL-observation proof for non-lock Experiment read → snapshot `FOR UPDATE` → Experiment `FOR UPDATE`, with exactly one lock per root row and no API-first Experiment lock.
  - With `ATLAS_TEST_DATABASE_URL=postgresql+psycopg://vike@localhost:5432/atlas_freeze07_test`, focused HTTP DELETE lock-order/confirmation tests passed: 5 passed.
  - Full directly affected `backend/tests/integration/test_experiment_deletion.py` passed: 38 passed.
- Concerns:
  - One existing Starlette/httpx deprecation warning remains; no task-level blockers.
