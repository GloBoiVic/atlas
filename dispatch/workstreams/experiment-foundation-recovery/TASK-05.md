# TASK-05 Receipt — Final Bounded Fix Pass 2

## Status

Implemented the final safe V2-path cleanup. V2 now uses one coherent model
version and canonical historical-context naming throughout the current runner,
clock, configuration, and result-read path.

## Changes

- Changed the current Experiment model label to
  `PHASE5_HISTORICAL_EXECUTION_V2` in configuration and runner provenance.
- Changed V2 risk/simulation configuration labels to `PHASE5_*` labels.
- Changed the result schema to `PHASE5_EXPERIMENT_RESULT_V2`; metric schema
  remains unchanged.
- Replaced V2 clock and runner `warmup_m15_bars`/`warm_up_bars` usage with
  `required_historical_context_bars`.
- Removed the result reader's warm-up compatibility fallback.
- Removed stale derived-M15 wording in the clock and changed the retained
  internal diagnostic path's run label to `V2`.
- Updated focused clock/configuration/result tests and test doubles to assert
  the canonical V2 model/context contract.

The older `backend/market_data/ingestion.py` `load_missing` service and CLI
remain untouched because they are shared legacy acquisition surfaces rather
than callers in the current `load_v2()` path; removing them would exceed a
safe bounded cleanup without their broader caller/test migration. Immutable
migration history was not changed.

## Verification

- `python -m pytest -q backend/tests/experiments/test_clock.py backend/tests/experiments/test_configuration.py backend/tests/experiments/test_runner_diagnostics.py backend/tests/experiments/test_results.py backend/tests/experiments/test_price_analysis_results.py`
  — **51 passed** in 116.63s.
- Focused `python -m ruff check` over all changed experiment and focused test
  files — **passed**.
- CodeGraph/search confirmation: no `PHASE4_MODEL_VERSION`, `warm_up_bars`,
  `warmup_m15_bars`, or PHASE4 model/config labels remain under
  `backend/experiments`.

No frontend, migration, environment, credential, or unrelated files were
changed. No Git commands or dispatch operations were performed.

## Files changed

- `backend/experiments/clock.py`
- `backend/experiments/configuration.py`
- `backend/experiments/metric_contract.py`
- `backend/experiments/results.py`
- `backend/experiments/runner.py`
- `backend/tests/experiments/test_clock.py`
- `backend/tests/experiments/test_configuration.py`
- `backend/tests/experiments/test_price_analysis_results.py`
- `backend/tests/experiments/test_results.py`
- `dispatch/workstreams/experiment-foundation-recovery/TASK-05.md`
