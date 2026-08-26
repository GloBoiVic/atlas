# TASK-01 Results — Experiment correctness

## Scope

Implemented approved blueprint §1–2 backend result/metric correction only. No
Strategy, Risk/execution/accounting redesign, load, UI, PAPER/LIVE, or other
dispatch artifacts were changed.

## Files changed

- `backend/experiments/runner.py`
  - V2 now persists the initial `trading_start` equity fact.
  - Samples every eligible completed M1 close after protection/accounting.
  - Defers an exposed final observation until the end-of-Experiment close, then
    records the post-close fact; existing timestamp deduplication remains in
    force.
- `backend/experiments/metrics.py`
  - Orders canonical equity facts chronologically for deterministic replay.
  - Computes drawdown amount and percent from the same maximum peak-to-trough
    event.
  - Retains UTC-daily endpoint, sample-standard-deviation, zero-risk-free,
    sqrt(252), and fail-closed Sharpe states.
- `backend/tests/experiments/test_metrics.py`
  - Added multi-trade/intra-run drawdown regression and out-of-order replay
    determinism regression; existing daily endpoint, insufficient-return, and
    zero-variance tests remain active.

## Validation evidence

- `pytest -q backend/tests/experiments/test_metrics.py backend/tests/experiments/test_runner_diagnostics.py backend/tests/experiments/test_results.py`
  - **30 passed**
- `ruff check backend/experiments/metrics.py backend/experiments/runner.py backend/tests/experiments/test_metrics.py`
  - **All checks passed**
- `python -m compileall -q backend/experiments backend/tests/experiments/test_metrics.py`
  - **Passed**

Final post-adjustment focused verification (`test_metrics.py` +
`test_runner_diagnostics.py`) also passed: **19 passed**; lint and compile were
re-run successfully.

No Git commands or commits were performed.
