# TASK-08-BACKEND-REPAIR — Experiment list metrics

- **Task:** Repair only the approved Phase 5 Task 8 backend list contract.
- **Branch:** `feature/phase-5-experiment-workflow`
- **Blocker status:** None.

## Changed files

- `backend/api/experiments.py`
- `backend/tests/integration/test_api_experiments.py`
- `backend/tests/experiments/test_results.py`

## Outcome

`GET /api/v1/experiments` now composes each row through the existing
`ExperimentResultReadService.detail` path. Completed rows therefore reuse the
canonical immutable Trade/equity metrics calculation; the route only performs
the existing API serialization. Noncompleted rows retain `metrics: null`.

Metric state objects and decimal-string values are preserved, including

Regression coverage includes completed list/detail metric parity for Net
Return, Max Drawdown, Sharpe, and Trade Count; zero-Trade unavailable states;

## Exact validation receipts

- `.venv/bin/pytest -q backend/tests/experiments/test_results.py backend/tests/experiments/test_metrics.py` → **16 passed**.
- `.venv/bin/pytest -q backend/tests/integration/test_api_experiments.py` → **4 passed** (one existing Starlette/httpx deprecation warning).
- `.venv/bin/ruff check backend/api/experiments.py backend/tests/integration/test_api_experiments.py backend/tests/experiments/test_results.py` → **All checks passed**.
- `.venv/bin/python -m py_compile backend/api/experiments.py backend/tests/integration/test_api_experiments.py backend/tests/experiments/test_results.py` → **passed**.
- `git diff --check` → **passed**.

No Git mutations were performed. Pre-existing worktree changes and forbidden
dispatch artifacts were left untouched.
