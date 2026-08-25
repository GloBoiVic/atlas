# Rerun persistence failure investigation

## Evidence

- Failed rerun: `06d69d83-442d-455b-bbc2-ebb8f8b20292`.
- Supplied persisted evidence: 49 partial trades, including 16 wins, ending in
  `PERSISTENCE_FAILURE`.
- The runner closes any remaining open Position at the experiment end through
  `_close_at_end`, creating an `EXIT` order and applying its Fill.
- `apply_fill` classified a fill as historical only when
  `model_version == "PHASE4_HISTORICAL_EXECUTION_V1"`. The current rerun model
  is `PHASE5_HISTORICAL_EXECUTION_V2`.
- Consequently, a V2 end close received exit reason `EXIT`. The `trades` table
  constraint `phase_4_exit_reason` permits only `TAKE_PROFIT`, `STOP_LOSS`, or
  `END_OF_EXPERIMENT`; the final Fill therefore failed persistence after prior
  trades had already been projected.

## Change

- Updated `backend/execution/fill_application.py` so both historical model
  versions classify end-close fills as `END_OF_EXPERIMENT`:
  - `PHASE4_HISTORICAL_EXECUTION_V1`
  - `PHASE5_HISTORICAL_EXECUTION_V2`
- Added a regression test in
  `backend/tests/integration/test_fill_application.py` that seeds a V2
  experiment, applies an entry and end-close Fill, and asserts the constrained
  historical exit reason.
- No Strategy logic, architecture, migration, environment, or schema change.

## Verification

- `python -m pytest backend/tests/execution/test_simulated.py backend/tests/experiments/test_runner_diagnostics.py -q`
  - **25 passed**.
- `python -m pytest backend/tests/integration/test_fill_application.py -q`
  - **3 skipped**: `ATLAS_TEST_DATABASE_URL` is not configured.
- `python -m pytest backend/tests/integration/test_golden_flows.py -q`
  - **2 skipped**: `ATLAS_TEST_DATABASE_URL` is not configured.
- Python compilation of the changed production and regression-test files
  completed successfully.

## Remaining blocker

The supplied failed Experiment could not be rerun against its persisted
PostgreSQL facts in this worktree because neither `ATLAS_DATABASE_URL` nor
`ATLAS_TEST_DATABASE_URL` is configured. The focused regression is ready for
the configured integration database; the production root cause and fix are
deterministic from the runner path and database constraint.
