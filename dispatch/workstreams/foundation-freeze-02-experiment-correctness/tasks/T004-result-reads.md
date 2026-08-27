# T004 — Persisted-result read paths

Status: `BUILD COMPLETE`

Scope after approval: change normal list/detail reads to persisted summaries and
results, while keeping requested Trades/equity/evidence reads bounded and
explicit. Expected evidence proves no ordinary read recalculates metrics or
loads full evidence unnecessarily, and missing terminal results fail closed.

## Implementation receipt

- `ExperimentResultReadService.detail` now requires a persisted result for a
  completed Experiment and projects metrics directly from its immutable result
  row. It no longer loads Trades/equity or calls `calculate_metrics`.
- API list/detail paths consume that persisted projection. Evidence endpoints
  remain explicit and bounded; failed, pending, running, and incomplete result
  paths remain fail-closed.
- Legacy result rows without the new state projection return no trusted metric
  projection rather than recalculating mutable evidence.
- Files changed: `backend/experiments/results.py`,
  `backend/api/experiments.py`, and focused read regression expectations in
  `backend/tests/experiments/test_results.py`.
- Checks: `pytest -q backend/tests/experiments` (75 passed);
  compileall passed; `git diff --check` passed.

Concerns: list still performs one bounded result/detail lookup per listed
Experiment for compatibility; it does not load evidence. A future batch result
projection could reduce query count without changing the public contract.
