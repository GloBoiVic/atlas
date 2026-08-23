# TASK-19 — Financing disclosure on Trade detail

## Outcome

Done with E2E concerns. The approved contract trace confirmed that Trade detail
must disclose financing, and the persisted configuration already provides the
data. A bounded API/UI repair and regressions were added. No financing
semantics, accounting, Phase 4 behavior, or broad UI surface was changed.

## Root cause and contract evidence

- `backend/experiments/configuration.py:38-69` constructs the immutable
  simulation configuration with `financing_model.type = EXCLUDED` and
  `disclosure = FINANCING EXCLUDED`.
- `backend/experiments/runner.py:687-688` validates that exact financing model,
  and `runner.py:845` persists the same disclosure in the result projection.
- The approved Phase 5 blueprint requires costs on Trade detail to disclose
  financing (`dispatch/workstreams/phase-5-experiment-workflow/ARCHITECTURE.md`,
  section “Result and Trade inspection”, line 92). The feature contract also
  requires financing disclosure in result assumptions (`context/features/
  experiment-results.md`, lines 43-49 and 67-69).
- CodeGraph tracing showed `ExperimentResultReadService.trade` composed
  summary/rationale/lineage/chart but did not include the disclosure. The
  frontend rendered `FINANCING EXCLUDED` only in the Experiment-level
  `StateDisclosure`; Trade detail had no financing field or row. The existing
  canonical E2E assertion at `tests/e2e/experiment-workflow.spec.ts:49`
  therefore failed after the chart repair reached Trade detail.

## Bounded fix

- `backend/experiments/results.py`: expose the disclosure from the immutable
  Experiment `simulation_config` in the Trade-detail payload.
- `frontend/components/experiment-workflow.tsx`: render a Financing row in the
  Trade summary using the API-provided value.
- `backend/tests/experiments/test_results.py`: assert the composed disclosure.
- `frontend/tests/experiment_results.test.tsx`: supply and assert the Trade
  detail disclosure.

## Validation

- `pytest -q backend/tests/experiments/test_results.py` — **PASS**, 9 passed.
- `npm run test:web -- --run frontend/tests/experiment_results.test.tsx` —
  **PASS**, 4 passed.
- Affected E2E:
  `npx playwright test tests/e2e/experiment-workflow.spec.ts --grep 'configures, runs' --workers=1`
  — **BLOCKED** before browser tests. The API web server rejected the current
  `DATABASE_URL`: `database_url must use postgresql+psycopg`.
- Full E2E:
  `npm run test:e2e -- --workers=1` — **BLOCKED** by the same isolated E2E
  environment/configuration failure before test execution.

## Blockers and scope confirmation

The isolated E2E database URL must be restored to the project’s required
`postgresql+psycopg` form before affected and canonical E2E receipts can be
re-run. Full Phase 5 validation and review were not run, per instruction.
No Git operations, dependency changes, migrations, financing/accounting
changes, Phase 4 changes, or adjacent UI broadening were performed for Task 19.
