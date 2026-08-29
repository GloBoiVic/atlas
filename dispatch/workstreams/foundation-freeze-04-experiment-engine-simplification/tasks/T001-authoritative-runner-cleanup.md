# T001 — Authoritative Runner Cleanup

Status: `DONE`

State history: `READY → IN_PROGRESS → DONE_WITH_CONCERNS → DONE`

## Goal

Leave `ExperimentRunner.run → _run_v2` as the only executable authoritative
Experiment runner path and replace the local pending-trigger tuple with the frozen
runner-local explicit handoff structure.

## Read

- `PLAN.md`
- `ARCHITECTURE.md`, especially sections 1, 2.1, 2.2, 3–8
- `backend/experiments/runner.py`
- `backend/experiments/lifecycle.py`
- relevant runner/golden/lifecycle tests

## Implement

- Remove the unreachable `_run_phase4` loop and `_open_and_close` plus only the
  runner-only diagnostics/imports/composition seams identified by architecture.
- Rename the terminal completion helper to a V2-neutral name without changing its
  operation order or persisted result semantics.
- Add the private frozen/slotted pending-trigger handoff with exactly the intent,
  decision frame, and Strategy decision facts required by the current V2 loop.
- Preserve the existing V2 `EntryPolicy.IMMEDIATE` behavior and tests; do not
  narrow the existing Strategy/runner contract or route it to a superseded loop.
- Update focused tests and write a complete receipt here.

## Do not implement

- No changes to Strategy methodology, Risk, execution, Fill/accounting, clock,
  market-data products, snapshot identity, result formulas, schema, or migrations.
- Do not change valid V2 output, failure sanitization, IMMEDIATE behavior, or
  pending W1–W6 semantics. Any future IMMEDIATE removal requires a separate
  explicit contract decision.

## Acceptance/checks

- Focused runner, golden, lifecycle, and relevant unit tests pass.
- Source graph/import audit proves no `_run_phase4`, `_open_and_close`, runner
  aggregation call/import, or comparison diagnostic production seam remains.
- Receipt compares canonical V2 facts/results before and after the representation
  cleanup, excluding only operational IDs/timestamps and removed diagnostics.

## Completion receipt

### Files changed

- `backend/experiments/runner.py`
- `backend/api/app.py`
- `backend/tests/e2e_app.py`
- `backend/tests/experiments/test_runner_diagnostics.py`
- `playwright.config.ts`
- `dispatch/workstreams/foundation-freeze-04-experiment-engine-simplification/tasks/T001-authoritative-runner-cleanup.md`

### Checks / evidence

- `.venv/bin/ruff check backend/experiments/runner.py backend/api/app.py backend/tests/e2e_app.py backend/tests/experiments/test_runner_diagnostics.py` — passed.
- Python compile check for the changed Python modules — passed.
- Focused runner/golden/lifecycle suite — `26 passed, 7 skipped`.
- All backend experiment tests — `86 passed`.
- Source-graph regression asserts `ExperimentRunner.run` calls `_run_v2` exactly once, and the removed runner names/imports/seams are absent.
- Pending-trigger regression asserts a frozen, slotted handoff with exactly `intent`, `decision_frame`, and `decision`.
- V2 loop retains strict `observation.start_time > decision_time`, Strategy-owned W1–W5/W6 state handling, native M15 MID loading, sparse M1 BID/ASK loading, and the existing IMMEDIATE branch; completion ordering is retained under `_complete_result`.

### Concerns

- API integration execution was environment-blocked: `backend/tests/integration/test_api_experiments.py` requires unset `ATLAS_TEST_DATABASE_URL` (5 tests passed and 8 setup errors); `test_runtime.py` passed.
- V1 result-reader completion/isolation remains the sequential T002 responsibility after the required removal of the application-level market-data injection; no V1 rows or read code were removed here.
