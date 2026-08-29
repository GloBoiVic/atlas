# T009 — Changed Test Lint Remediation

Status: `DONE`

State history: `READY → IN_PROGRESS → DONE_WITH_CONCERNS → DONE`

## Goal

Remove the exact current-only Ruff diagnostics identified by independent validation
from Freeze 04-touched test seams.

## Read

- `PLAN.md`
- `ARCHITECTURE.md`, section 8
- `VALIDATION.md`
- `tasks/T008-e2e-date-and-fixture-remediation.md`
- `backend/tests/experiments/test_price_analysis_results.py`
- `backend/tests/experiments/test_runner_diagnostics.py`
- the base SHA and exact validator Ruff comparison

## Implement

- Fix only the 13 current-only E501 and 4 current-only B009 diagnostics reported by
  VALIDATE in the two changed test files.
- Preserve test behavior, assertions, fixtures, production code, and all approved
  Freeze 04 semantics. Formatting/wrapping and replacing constant `getattr` calls
  with direct access are the intended narrow changes.
- Run changed-file and full Ruff, focused tests, compile, and diff checks.
- Write a complete completion receipt in this task file.

## Acceptance

- The exact current-only Ruff diagnostics are gone and no unrelated baseline cleanup
  is performed.
- Focused tests and quality checks pass.

## Do not implement

- Do not edit VALIDATION.md, production behavior, migrations, or expected outputs.
- Do not alter preserved user files or Git history.
- Do not claim final validation PASS.

## Completion receipt

ROLE: BUILD  
STATUS: DONE_WITH_CONCERNS  
ARTIFACT: `dispatch/workstreams/foundation-freeze-04-experiment-engine-simplification/tasks/T009-changed-test-lint-remediation.md`

### Implementation

- Wrapped the exact 13 current-only E501 lines in the two named changed test files.
- Replaced the exact 4 current-only constant `getattr` calls with direct attribute
  access: one in `test_price_analysis_results.py` and three in
  `test_runner_diagnostics.py`.
- Preserved all test behavior, assertions, fixtures, expected outputs, production
  code, migrations, and Freeze 04 semantics. No broad baseline cleanup was done.

### Files changed

- `backend/tests/experiments/test_price_analysis_results.py`
- `backend/tests/experiments/test_runner_diagnostics.py`
- This task receipt

### Checks / evidence

- Changed-file Ruff:
  `.venv/bin/ruff check backend/tests/experiments/test_price_analysis_results.py
  backend/tests/experiments/test_runner_diagnostics.py` — **PASS**; all 17
  reported current-only diagnostics are gone.
- Focused affected tests:
  `.venv/bin/pytest -q backend/tests/experiments/test_price_analysis_results.py
  backend/tests/experiments/test_runner_diagnostics.py` — **46 passed**.
- `python -m compileall -q backend` — **PASS**.
- `git diff --check` — **PASS**.
- Full Ruff:
  `.venv/bin/ruff check backend` — **FAIL, 44 remaining diagnostics** outside
  the two target files; these are baseline diagnostics and were intentionally not
  cleaned up under T009.

### Concerns

- Full-repository Ruff remains non-clean with 44 diagnostics outside the scoped
  files. The exact Freeze 04 current-only set from VALIDATION.md is remediated;
  final validation must rerun its complete matrix and update VALIDATION.md.
- Preserved untracked files were not modified. No commit or Git-history operation
  was created.
