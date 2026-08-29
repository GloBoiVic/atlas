# T008 — E2E Date and Fixture Remediation

Status: `DONE`

State history: `READY → IN_PROGRESS → DONE`

## Goal

Make the existing E2E workflow spec interact with the current composite UTC
date/time picker and ensure its existing failed-Experiment setup reaches the
existing assertions, without changing product behavior or assertion semantics.

## Read

- `PLAN.md`
- `ARCHITECTURE.md`, section 8
- `VALIDATION.md`
- `tasks/T007-e2e-selector-remediation.md`
- `tests/e2e/experiment-workflow.spec.ts`
- `tests/e2e/global-setup.ts`
- `backend/tests/e2e_seed.py`
- `frontend/components/utc-date-time-picker.tsx`
- `frontend/components/ui/calendar.tsx`
- relevant current status-page and API contracts

## Implement

- Replace stale composite `fill()` calls only with deterministic interactions against
  the current date button and UTC time select, preserving the same requested dates
  and times and every existing assertion.
- Diagnose the failed-Experiment workflow timeout using current fixtures and API/UI
  state. Fix only stale test setup/selection or fixture wiring if necessary; do not
  weaken, remove, or rewrite assertions and do not change product code.
- Run the complete Playwright suite with the dedicated `atlas_test` database and
  alternate API/web ports; leave PID 72514 untouched.
- Write a complete completion receipt in this task file.

## Acceptance

- All existing Playwright E2E tests pass with unchanged behavioral assertions.
- Targeted web checks and diff checks pass.
- No product code, API behavior, fixture semantics beyond stale setup wiring, or
  application defaults changed.

## Do not implement

- Do not edit frontend product components.
- Do not stop or reuse PID 72514.
- Do not modify VALIDATION.md or claim final validation PASS.
- Do not commit.

## Completion receipt

ROLE: BUILD  
STATUS: DONE  
ARTIFACT: `dispatch/workstreams/foundation-freeze-04-experiment-engine-simplification/tasks/T008-e2e-date-and-fixture-remediation.md`

### Implementation

- Replaced the stale composite `fill()` calls with deterministic calendar-button
  and UTC time-select interactions for the existing fixed UTC values:
  `2026-01-06T01:00`, `2026-01-06T02:30`, `2026-01-06T02:00`, and
  `2026-01-06T01:15`.
- Kept the workflow assertions intact, narrowing the existing `No Trades` text
  locator to the exact current result heading so it does not also match the
  technical price-chart disclosure.
- Diagnosed the failed-Experiment timeout: the test database retained the retired
  Phase 4 insert trigger, which changed current-model E2E fixture inserts from
  `PENDING` to `RUNNING`. Restored the intended pending command state in the E2E
  seed only.
- Repaired stale E2E fixture wiring by extending the primary V2 fixture through
  the requested 02:30 UTC period and adding a distinct incomplete-execution
  snapshot for the existing invalid-coverage flow. No frontend product or backend
  product code was changed.

### Files changed

- `backend/tests/e2e_seed.py`
- `backend/tests/integration/test_golden_flows.py`
- `tests/e2e/experiment-workflow.spec.ts`
- This task receipt

### Checks / evidence

- Complete Playwright E2E with the required dedicated database and alternate
  ports, without stopping or reusing PID `72514`:
  `ATLAS_E2E_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test'`
  `ATLAS_E2E_API_PORT='18080' ATLAS_E2E_WEB_PORT='13000' npm run test:e2e` —
  **5 passed**.
- Targeted web checks: `npm run test:web` — **23 passed**; web lint,
  typecheck, and production build — **passed**.
- Targeted formatting/lint: Prettier for the workflow spec — **passed**; Ruff for
  the changed E2E/golden fixture files — **passed**.
- Backend fixture regression:
  `ATLAS_TEST_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test'`
  `.venv/bin/pytest -q backend/tests/integration/test_golden_flows.py` —
  **2 passed**.
- `python -m compileall -q backend` and `git diff --check` — **passed**.
- Generated `tests/e2e/.fixtures.json` was restored after the run; no generated
  fixture IDs are part of this receipt's implementation diff.

### Concerns

- None for T008. Existing global quality/formatting baseline concerns remain
  recorded by prior receipts and were not changed here.
