# TASK-07 Receipt — Final V2 Configuration Boundary

## Status

Implemented the remaining Important remediation for R1-002 and resolved the
changed-file frontend formatting gate where feasible. No database or OANDA
acceptance was attempted.

## Changes

- Removed the non-V2 configuration coverage/aggregation path from
  `ExperimentConfigurationService`.
- Direct coverage and create requests now fail closed with
  `UNSUPPORTED_SNAPSHOT_SCHEMA` unless the snapshot is the V2 simulation schema;
  no new request can route through V1.
- Updated the database-backed configuration regression coverage to assert that a
  legacy snapshot cannot create or persist an Experiment graph.
- Formatted the changed `strategy-history.tsx`, generated API types, and changed
  Experiment results test with Prettier.

## Verification

- `python -m pytest -q backend/tests/experiments/test_configuration.py backend/tests/experiments/test_clock.py backend/tests/experiments/test_runner_diagnostics.py`: **19 passed**.
- `python -m pytest -q backend/tests/integration/test_experiment_configuration.py`: **2 skipped** (dedicated test database unavailable).
- Ruff on changed configuration implementation/test: **passed**.
- Targeted frontend Experiment results test: **5 passed**.
- Prettier check on changed frontend files: **passed**.
- Full configured frontend formatting check remains red on 11 unrelated pre-existing files; changed frontend files are green.
