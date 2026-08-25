# TASK-INTRABAR-FIX

## Result

Implemented the minimal directional protection fix in `backend/execution/simulated.py`.

- LONG stop: BID low `<=` stop.
- LONG target: BID high `>=` target.
- SHORT stop: ASK high `>=` stop.
- SHORT target: ASK low `<=` target.

Open-quote gap/reach behavior and ENTRY/EXIT semantics are unchanged. The existing
stop-adverse-first policy is now marked ambiguous only when both of those
directionally executable levels are touched in the same observation.

Added regression coverage for all LONG/SHORT × STOP_LOSS/TAKE_PROFIT cases,
one-sided touches, a genuine dual touch, and opposite-side extremes that must not
produce ambiguity.

## Validation

Input evidence for Experiment `fd67625e-15e0-4d10-b4d0-40e3ca613923`: 80 trades,
80 same-entry exits, 80 previously ambiguous; old generic logic reported both
levels touched for all 80, while directional logic reports 0 genuine dual touches.

Exact commands and results:

```text
.venv/bin/ruff check backend/execution/simulated.py backend/tests/execution/test_simulated.py
All checks passed!

.venv/bin/pytest backend/tests/execution/test_simulated.py backend/tests/test_runtime.py backend/tests/experiments/test_results.py
30 passed in 33.43s

.venv/bin/pytest backend/tests/experiments/test_runner_diagnostics.py
10 passed in 1.39s
```

No Strategy logic, API/UI, migrations, environment, or database files were changed.
