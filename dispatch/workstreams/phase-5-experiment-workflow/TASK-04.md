# TASK-04 — Run lifecycle and recovery

- **Task:** Implement approved blueprint task 4 only: durable synchronous run
  claiming, row locking, retry-safe terminal behavior, recovery, and sanitized
  infrastructure-failure persistence.
- **Agent:** backend builder
- **Model:** gpt-5.6-luna (`openai/gpt-5.6-luna`)
- **Branch:** `feature/phase-5-experiment-workflow`

## Changed files

- `backend/experiments/lifecycle.py`
- `backend/persistence/experiment_repository.py`
- `backend/tests/integration/test_experiment_lifecycle.py`

## Outcome

Added `ExperimentRunService` with the approved two-transaction protocol:
`PENDING → RUNNING` is row-locked and committed first, then a fresh transaction
locks the row through the existing runner and commits the complete terminal
graph atomically. Terminal retries are no-ops, duplicate commands serialize on
the Experiment row, clean `RUNNING` rows are crash-equivalent retry candidates,
and committed partial facts fail closed as
`PERSISTENCE/INCOMPLETE_RUN_STATE`.

Infrastructure/session failures roll back the runner transaction and use a
fresh transaction to persist bounded `PERSISTENCE_FAILURE`; the raised
infrastructure exception is sanitized. The repository now provides focused
`FOR UPDATE` loading and committed-fact detection, including fills reached via
their Orders. No HTTP routes, UI, workers, queues, or background execution were
added. The gated service integration test proves a separate status session can
observe committed `RUNNING` while execution remains in progress.

## Exact validation receipts

- `pytest -q backend/tests/integration/test_experiment_lifecycle.py` → **5 passed**.
- `ruff check backend/experiments/lifecycle.py backend/persistence/experiment_repository.py backend/tests/integration/test_experiment_lifecycle.py` → **All checks passed**.
- `python -m py_compile backend/experiments/lifecycle.py backend/persistence/experiment_repository.py backend/tests/integration/test_experiment_lifecycle.py` → **passed**.

Coverage includes visible RUNNING claims, domain failure persistence,
duplicate serialization, terminal retry no-op, clean recovery, committed
partial-state fail-closed behavior, and durable sanitized infrastructure
fallback.

## Blocker/conflict

None. No Git mutations were performed. Existing preceding-task changes,
dispatch changes, and `.codegraph/` were preserved.
