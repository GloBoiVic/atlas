# T002 — Persisted result-state and immutability

Status: `BUILD COMPLETE`

Scope after approval: define the narrow persisted metric/result-state contract,
required constraints, and terminal Experiment/ExperimentResult immutability.
Expected evidence: migration/domain tests proving complete result facts are
written atomically and failed/partial Experiments expose no trusted result.

## Implementation receipt

- Files changed: `backend/persistence/models.py`,
  `backend/persistence/experiment_repository.py`,
  `backend/experiments/metric_contract.py`, and Alembic revision
  `0014_result_metric_state_details.py`.
- Result state now covers all seven headline metrics and stores `{state,
  reason}` objects in the existing `metric_states` JSON field. Legacy rows are
  normalized by the migration; no new result table or metric columns were
  added.
- Repository lifecycle now rejects completion without an ExperimentResult,
  duplicate results, and fact/result writes after terminal status. This keeps
  completion transactional because the caller-owned transaction contains both
  result creation and status transition.
- Checks: `python -m compileall -q backend/persistence backend/experiments`;
  `pytest -q backend/tests/experiments/test_result_state.py
  backend/tests/experiments/test_metrics.py` (11 passed);
  `git diff --check`.

Concerns for T003: completion currently supplies the existing four metric
states; repository normalization supplies deterministic legacy reasons for
missing states. T003 must persist the authoritative metric reasons and states
directly from the V2 calculation, including the frozen Sharpe methodology.
