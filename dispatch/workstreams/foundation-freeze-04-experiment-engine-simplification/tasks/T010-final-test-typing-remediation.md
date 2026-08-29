# T010 — Final Test Typing Remediation

Status: `DONE`

State history: `READY → IN_PROGRESS → DONE_WITH_CONCERNS → DONE`

## Goal

Remove the three exact current-only strict Pyright diagnostics identified by final
validation from changed test seams, without weakening the strict gate.

## Read

- `PLAN.md`
- `ARCHITECTURE.md`, section 8
- `VALIDATION.md`
- `tasks/T009-changed-test-lint-remediation.md`
- `backend/tests/experiments/test_price_analysis_results.py`
- `backend/tests/experiments/test_runner_diagnostics.py`

## Implement

- Resolve only the three listed current-only diagnostics: protected `_chart` access,
  private `_PendingPriceTrigger` test access, and `__dataclass_params__` access.
- Use precise test-side typing/module access or casts as necessary; do not add broad
  ignores, Pyright configuration, runtime changes, or altered assertions.
- Run exact base/current Pyright differential, affected tests, Ruff, compile, and
  diff checks.
- Write a complete completion receipt in this task file.

## Acceptance

- No current-only strict Pyright diagnostics remain in changed production/test seams.
- Affected tests and quality checks pass with behavior unchanged.

## Do not implement

- Do not edit VALIDATION.md, product code, migrations, expected outputs, or E2E tests.
- Do not weaken/suppress the strict type gate or perform baseline cleanup.
- Do not alter preserved user files or Git history.
- Do not claim final validation PASS.

## Completion receipt

ROLE: BUILD  
STATUS: DONE_WITH_CONCERNS  
ARTIFACT: `dispatch/workstreams/foundation-freeze-04-experiment-engine-simplification/tasks/T010-final-test-typing-remediation.md`

### Implementation

- Replaced the protected `ExperimentResultReadService._chart` test access with a
  test-side class-dictionary lookup, explicit callable cast, and `MethodType` binding.
- Replaced the private `runner_module._PendingPriceTrigger` test access with a typed
  module-dictionary lookup.
- Added a narrow test-side Protocol view for `__dataclass_params__` and accessed the
  dataclass parameters through that cast.
- Preserved all assertions, fixtures, expected outputs, runtime/product code, Pyright
  configuration, migrations, and Freeze 04 behavior. No broad ignores or baseline
  cleanup were performed.

### Files changed

- `backend/tests/experiments/test_price_analysis_results.py`
- `backend/tests/experiments/test_runner_diagnostics.py`
- This task receipt

### Checks / evidence

- Exact base/current strict Pyright differential, comparing path/severity/rule/full
  message with line movement ignored, using base SHA
  `3521274d1f3f492176eec8be9434bc76c6e4341b` and the recorded `.venv` invocation:
  **base 3,333 errors / 136 files; current 2,673 errors / 130 files; 0 current-only,
  299 resolved**. The three named diagnostics are absent from the differential.
- Affected tests:
  `.venv/bin/pytest -q backend/tests/experiments/test_price_analysis_results.py
  backend/tests/experiments/test_runner_diagnostics.py` — **46 passed**.
- Affected Ruff:
  `.venv/bin/ruff check backend/tests/experiments/test_price_analysis_results.py
  backend/tests/experiments/test_runner_diagnostics.py` — **PASS**.
- `.venv/bin/pyright backend/tests/experiments/test_price_analysis_results.py
  backend/tests/experiments/test_runner_diagnostics.py` — **222 baseline errors,
  0 warnings**; the exact base/current differential is the authoritative regression
  evidence above.
- `python -m compileall -q backend` — **PASS**.
- `git diff --check` — **PASS**.
- Full `.venv/bin/ruff check backend` — **FAIL, 44 baseline diagnostics**; no target
  file diagnostics were reported and no unrelated cleanup was performed.

### Concerns

- The repository-wide strict Pyright and Ruff commands remain non-clean on pre-existing
  baseline debt, but the exact current-only Freeze 04 Pyright set is zero and the
  affected tests/Ruff checks pass.
- `VALIDATION.md` remains VALIDATE-owned and was not edited; final validation must rerun
  its complete matrix and determine final disposition.
- PID `72514`, `.codegraph/`, and `frontend/.env.local` were preserved. No commit or
  other Git-history operation was created.
