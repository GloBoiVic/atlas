# Task 05 — Runner and results receipt

## Changed paths

- `backend/experiments/runner.py`
- `dispatch/workstreams/phase-4-historical-execution/TASK-05-runner-results.md`

## Implemented behavior

- Added the Phase 4 `PENDING → RUNNING → COMPLETED/FAILED` orchestration path while preserving the Phase 3 runner path.
- Integrated the Task 02 chronological M1 observations and M15 frontiers with warm-up Strategy state, actual Position context, and no-lookahead entry timing.
- Persisted actionable intents and both Risk phases; expected Risk rejections are durable and continue the loop.
- Added entry, submitted protection pair, protection-trigger, sibling cancellation, sequential Trade, and end-of-experiment close orchestration through Task 03/04 boundaries.
- Samples starting equity and eligible M1-close equity, values open exposure on BID/ASK liquidation sides, and derives drawdown from the running peak.
- Added zero-or-more Trade terminal result reconciliation and a deterministic SHA-256 semantic fingerprint over provenance, configuration, ordered decisions/risk/orders/fills/trades, and equity facts while excluding UUIDs and audit timestamps.
- Preserved categorized terminal failure persistence and no-result behavior on failure.

## Exact checks

- `uv run ruff check backend/experiments/runner.py` — passed
- `python -m compileall -q backend/experiments` — passed
- `uv run pytest backend/tests/experiments/test_clock.py backend/tests/execution/test_simulated.py backend/tests/integration/test_golden_flows.py backend/tests/integration/test_runner_failure_persistence.py` — 17 passed

## Exclusions

No API, UI, runtime, PAPER/LIVE, broker, reconciliation, optimization, distributed execution, generalized strategy/provider/instrument abstraction, or new persisted trading noun was added. No Git-changing command was performed. No other dispatch artifact was intentionally modified.

## Reusable validation caveats

The focused suite exercises the existing PostgreSQL Phase 3 compatibility and Task 02–04 contracts. A dedicated Phase 4 end-to-end fixture covering multi-Trade, ambiguity, equity/result projection, and cross-Experiment fingerprint equality remains for the independent validation task.

## Blockers

None for the assigned implementation scope.
