# TASK-UIFIX — Session-Aware Analytical Frontier Coverage

## Status

Implemented and verified. This task remains limited to the V2
analytical-frontier expectation used by Experiment configuration coverage
validation.

## Defect

`backend/experiments/configuration.py:112` currently constructs every 15-minute
wall-clock instant from `required_start` through `trading_end`. That treats
weekend and provider-maintenance/session-closure windows as missing native M15
data. A normal EUR/USD/OANDA Practice request covering 2025-01-06 through
2025-02-06 therefore reports `MISSING_ANALYTICAL_FRONTIERS` despite valid sparse
session data.

The existing policy seam is already authoritative:

- `backend/market_data/session_calendar.py:38` exposes
  `eligible_m15_windows(start, end)`.
- It derives each aligned M15 window from the versioned
  `OANDA_EUR_USD_POLICY`, retaining a window when at least one minute is
  classified `EXPECTED_DATA`.
- The V2 contract remains native M15 MID analysis with sparse M1 BID/ASK
  execution; neither resolution nor execution semantics change.

## Changes applied

Updated only `missing_analytical_frontiers` in
`backend/experiments/configuration.py` and its focused regression tests:

1. Imported `eligible_m15_windows` from
   `backend.market_data.session_calendar`.
2. Replaced wall-clock range generation with the window starts returned by
   `eligible_m15_windows(required_start, trading_end)`.
3. The function now returns only eligible window starts absent from
   `analytical_starts`, preserving
   the existing tuple result and deterministic policy order.
4. Kept the existing caller and `MISSING_ANALYTICAL_FRONTIERS` reason unchanged.

Conceptually:

```python
expected = (
    window_start
    for window_start, _window_end in eligible_m15_windows(
        required_start, trading_end
    )
)
return tuple(frontier for frontier in expected if frontier not in analytical_starts)
```

Do not alter `session_policy.py`, V2 native M15 persistence, sparse M1
execution, gap persistence, configuration boundaries, credentials, database
configuration, or unrelated UI.

## Regression tests added

1. **Weekend/session closure accepted:** builds analytical starts for every
   eligible window in a range spanning a normal Friday-to-Monday closure (or a
   full Jan 6–Feb 6 2025 month), omit all closure slots, and assert
   `missing_analytical_frontiers(...) == ()`.
2. **Internal open-session omission rejected:** builds the same eligible starts,
   remove one start whose policy classification is open, and assert the result
   is exactly that missing frontier.

The fixtures must derive eligible starts through
`eligible_m15_windows`; do not encode a second weekend schedule in tests.

## Verification evidence

Focused verification after the application-code and test changes:

```text
python -m pytest -q backend/tests/experiments/test_configuration.py backend/tests/experiments/test_runner_diagnostics.py backend/tests/market_data/test_task3.py
............................                                             [100%]
28 passed in 0.75s
```

Changed-file lint:

```text
python -m ruff check backend/experiments/configuration.py backend/tests/experiments/test_runner_diagnostics.py
All checks passed!
```

The prior direct reproduction for a Jan 10–13 weekend interval returned `288`
false missing wall-clock frontiers. The new session-aware implementation
excludes those closures while the internal-gap regression remains explicit.
No environment/database/Git change, migration change, real OANDA request, or
unrelated UI change was made.
