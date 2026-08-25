# Task 05 — Experiment Runner V2 Dispatch

## Status
**DONE** (restored from validated stash, V1 green)

- `backend/experiments/clock.py` — `M1Observation` sparse BID/ASK, `SimulationClock` frames with `M15 decision` + `post-decision executable_oboses` separation, no-lookahead, `insufficient completed M15 bars for warmup` guard
- `backend/experiments/runner.py` — dispatch `run_v2` (native M15 to Strategy, sparse BID/ASK to execution) vs `run_v1` (derived M15), gap decisions with `ATLAS_HISTORICAL_GAP_POLICY_V1`, `result_quality` deterministic mapping, adverse-first intrabar preserved
- `backend/experiments/configuration.py` — `execution_resolution=M1`, `analysis_component=MID`, validation counts eligible M15 warm-up, not minutes
- `backend/persistence/result_repository.py` + `models.py` — `result_quality` JSONB + `experiment_gap_decisions` immutable trigger

`aggregate_m1_to_m15` is now explicitly V1-only: used only when `snapshot_schema==V1`; V2 never reconstructs analytical M15 from sparse M1.

## Verification
- `pytest backend/tests/experiments/test_clock.py backend/tests/experiments/test_results.py` — included in 258 core
- V1 golden flows `backend/tests/integration/test_golden_flows.py` remain green under V2 dispatch (runner selects V1 path when snapshot_schema==V1)

