# T007 — E2E Selector Validation Remediation

Status: `DONE`

State history: `READY → IN_PROGRESS → DONE_WITH_CONCERNS → DONE`

## Goal

Remove the stale accessibility-selector blocker from the existing Playwright
workflow tests so the required E2E acceptance gate tests the current form rather
than failing before any workflow action.

## Read

- `PLAN.md`
- `ARCHITECTURE.md`, section 8
- `VALIDATION.md`
- `tasks/T006-quality-and-e2e-remediation.md`
- `tests/e2e/experiment-workflow.spec.ts`
- `frontend/components/experiments/experiment-setup.tsx`

## Implement

- Align only stale `getByLabel` selectors with the accessible labels rendered by
  the current Experiment setup form (`Strategy` and `Data`).
- Do not change product code, API behavior, test assertions, fixture semantics, or
  default ports.
- Run the complete Playwright suite using the dedicated `atlas_test` database and
  explicit alternate API/web ports; leave PID 72514 untouched.
- Write a complete completion receipt in this task file.

## Acceptance

- All Playwright E2E tests pass against the dedicated test database on alternate
  ports.
- Targeted web checks and diff checks pass.
- No product behavior or assertion semantics changed.

## Do not implement

- Do not edit frontend product components.
- Do not stop or reuse PID 72514.
- Do not modify VALIDATION.md or claim final validation PASS.
- Do not commit.

## Completion receipt

ROLE: BUILD  
STATUS: DONE_WITH_CONCERNS  
ARTIFACT: `dispatch/workstreams/foundation-freeze-04-experiment-engine-simplification/tasks/T007-e2e-selector-remediation.md`

### Implementation

- Updated only the existing workflow-test Strategy selectors from `StrategyVersion`
  to the current accessible label `Strategy`.
- Updated only the existing workflow-test snapshot selectors from
  `DatasetSnapshot` to the current `Data` label, selecting the first matching
  labelled control because the form also renders a `Data available` labelled
  region. No product code, API behavior, fixture semantics, assertions, or ports
  were changed.

### Files changed

- `tests/e2e/experiment-workflow.spec.ts`
- This task receipt

### Checks / evidence

- Complete Playwright suite with the required dedicated database and alternate
  ports, without stopping or reusing PID `72514`:
  `ATLAS_E2E_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test'`
  `ATLAS_E2E_API_PORT='18080' ATLAS_E2E_WEB_PORT='13000' npm run test:e2e`.
  Result: **1 passed, 4 failed**; the API started on `18080` and web started on
  `13000`.
- Web tests: **23 passed** (`npm run test:web`).
- Web lint: **0 errors, 365 warnings** (`npm run lint:web`).
- Web typecheck: **passed** (`npm run typecheck:web`).
- Web production build: **passed** (`npm run build:web`).
- Targeted Prettier and ESLint checks for the changed workflow spec: **passed**.
- Full web formatting check remains baseline non-clean: 5 pre-existing files are
  reported; the changed workflow spec is formatted.
- `git diff --check`: **passed**. PID `72514` remained running on port `8000`.

### Concerns / exact remaining blockers

- The three setup workflows now pass the Strategy/Data selector steps, then fail
  at the pre-existing `page.getByLabel('Trading start').fill(...)` call. Playwright
  reports strict-mode resolution to two current-form elements: the `Trading start
  date` button and the `Trading start time in UTC` select. Remediating that date
  picker would exceed T007's Strategy/Data-only selector scope.
- The failed-Experiment workflow times out after 30 seconds waiting for
  `getByRole('button', { name: 'Run Experiment' })` at line 90; no assertion was
  changed to mask it.
- Because the full E2E suite did not pass, this task is correctly marked
  `DONE_WITH_CONCERNS`, not `DONE`.
