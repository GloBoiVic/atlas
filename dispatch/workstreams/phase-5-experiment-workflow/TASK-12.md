# TASK-12 — Evidence-led valid-run remediation

## Outcome

**Explicitly blocked; no corrective application/configuration change was made.**
The evidence points to the database session timezone policy, which the approved
remediation explicitly identifies as a stop condition requiring a blueprint
update. The only lasting code change is the approved inert, default-off runner
diagnostic seam and its focused safety coverage.

## Evidence and first mismatch

- Added the two-case PostgreSQL regression in
  `backend/tests/integration/test_phase5_valid_run.py`. It creates the candidate
  through `ExperimentConfigurationService` and executes it through
  `ExperimentRunService` plus the real `ExperimentRunner`, alongside a direct
  Phase-4-shaped baseline.
- With the isolated test session explicitly set to UTC, both the primary
  `START + 1500` → `START + 1590` case and zero-Trade
  `START + 1500` → `START + 1515` case complete. Input comparison covers
  StrategyVersion/fingerprint, DatasetSnapshot/fingerprint/member count, venue,
  period, capital, parameters, Risk/config, simulation config, model version,
  account, Position, and status.
- The same direct baseline, before the UTC session setting, fails at the first
  runner operation requiring a clock: `clock_construction`.
- Safe diagnostic record: `event=experiment_runner_value_error`,
  `run_path=PHASE4`, `stage=clock_construction`,
  `reason_code=CLOCK_START_ALIGNMENT_INVALID`; no raw message is emitted.
- PostgreSQL reports the default database timezone as `America/Chicago`. The
  runner receives persisted timestamps with that session offset, while the
  Phase 4 clock requires UTC-aligned timestamps. This is the named first
  mismatch: **runner-entry timestamp/session timezone policy**, not Phase 5
  configuration values or market-data membership.
- The pre-existing E2E receipt independently records both Phase 5 valid browser
  cases reaching durable `MARKET_DATA/INVALID_INPUT`; this seam now identifies
  the corresponding safe runner boundary without changing public failure detail.
- Because the first mismatch is session policy, the approved blueprint requires
  stopping rather than changing `configuration.py`, lifecycle behavior, clock
  semantics, historical access, or Phase 4 behavior. No corrective code was
  attempted.

## Diagnostic seam and sanitization

Changed `backend/experiments/runner.py` only at the approved boundary:

- optional constructor-injected sink, default-off;
- immutable closed `Phase4ValueErrorDiagnostic` record;
- bounded stage markers for the approved Phase 4 operations;
- closed reason vocabulary, with recognized timestamp parsing only;
- unknown/hostile text maps to `UNCLASSIFIED_VALUE_ERROR`;
- sink exceptions are swallowed and cannot affect `_fail`, transaction state,
  persistence, lifecycle, or API behavior.

`backend/tests/experiments/test_runner_diagnostics.py` proves known reasons,
UTC timestamp normalization, hostile/unrecognized text exclusion, absent sink,
SQL, credentials, URLs, filesystem/source paths, traceback data, configuration,
or arbitrary logging. Production `create_app` injects no sink.

## Result and Phase 4 impact

- Under the required explicit UTC isolated-test session, primary completion has
  a result and completed Trade facts; zero-Trade completion has a result,
  equity, and zero Trade facts.
- Existing Phase 4 golden and failure behavior remains unchanged. No runner
  semantic, aggregation, Strategy, Risk, execution, accounting, schema, API, or
  UI correction was made.
- The diagnostic seam is inert unless a test injects a sink; public and durable
  failure sanitization remains `Experiment could not be run`.

## Changed files

- `backend/experiments/runner.py`
- `backend/tests/experiments/test_runner_diagnostics.py`
- `backend/tests/integration/test_phase5_valid_run.py`
- `dispatch/workstreams/phase-5-experiment-workflow/TASK-12.md`

## Exact receipts

- `.venv/bin/ruff check backend/experiments/runner.py backend/tests/experiments/test_runner_diagnostics.py backend/tests/integration/test_phase5_valid_run.py` → passed.
- `.venv/bin/pytest -q backend/tests/experiments/test_runner_diagnostics.py` → **3 passed**.
- `ATLAS_TEST_DATABASE_URL='postgresql+psycopg://vike@localhost:5432/atlas_test' .venv/bin/pytest -q backend/tests/integration/test_phase5_valid_run.py` → **2 passed** in 38.17s, with the isolated regression session explicitly set to UTC.
- `ATLAS_TEST_DATABASE_URL='postgresql+psycopg://vike@localhost:5432/atlas_test' .venv/bin/pytest -q backend/tests/integration/test_golden_flows.py` → **8 passed** in 126.30s.
- `ATLAS_TEST_DATABASE_URL='postgresql+psycopg://vike@localhost:5432/atlas_test' .venv/bin/pytest -q backend/tests/integration/test_experiment_lifecycle.py backend/tests/integration/test_api_experiments.py` → **9 passed** in 199.64s; one pre-existing Starlette/httpx deprecation warning.
- A combined focused/golden invocation printed **7 passed** but exceeded its
  120-second command limit; it is not used as a success receipt.

## Skipped or blocked checks

Skipped because the blueprint evidence gate stopped corrective implementation:

- focused E2E primary and zero-Trade serial receipt;
- canonical full `npm run test:e2e`;
- full Phase 5 backend/frontend validation matrix, generated-contract/build
  receipts, and independent validation/review.

These are not claimed as passed. The required next action is an approved
blueprint update for the session-timezone mismatch, followed by rerunning the
evidence gate and receipts.

## Operations confirmation

- No Git mutations: no commit, reset, checkout, clean, push, merge, or branch
  operation.
- No dependency or browser installation.
- No worktree operation.
- No Phase 6 work.
- No dispatch artifact other than this `TASK-12.md` was altered.
