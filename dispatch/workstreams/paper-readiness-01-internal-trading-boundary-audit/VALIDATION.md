# VALIDATION — PAPER Readiness 01 Risk Lifecycle Boundary Cleanup

## Status

`PASS_WITH_CONCERNS`

- **Workstream:** `paper-readiness-01-internal-trading-boundary-audit`
- **Task:** `T001`
- **Role:** `VALIDATE`
- **Branch:** `solo/paper-readiness-01-internal-trading-boundary-audit`
- **Scope:** independently verify the approved Risk boundary cleanup, T001 BUILD
  receipt, focused financial-risk regressions, preserved Experiment lifecycle gate,
  enum compatibility decision, and targeted quality checks.

## Required validation boundary

Run focused checks only:

```bash
uv run pytest \
  backend/tests/risk/test_service.py \
  backend/tests/experiments/test_runner_diagnostics.py

uv run ruff format --check \
  backend/risk/service.py \
  backend/experiments/runner.py \
  backend/tests/risk/test_service.py \
  backend/tests/experiments/test_runner_diagnostics.py

uv run ruff check \
  backend/risk/service.py \
  backend/experiments/runner.py \
  backend/tests/risk/test_service.py \
  backend/tests/experiments/test_runner_diagnostics.py

uv run pyright \
  backend/risk/service.py \
  backend/tests/risk/test_service.py

git diff --check
```

Do not run the full backend, database, OANDA, frontend, browser, or migration
suites unless the actual diff demonstrates a broader blast radius.

## Verification focus

- public Risk methods and `_common()` have no Experiment lifecycle input;
- reusable Risk emits no `EXPERIMENT_NOT_RUNNING` rejection;
- `_run_v2()` retains its PENDING/RUNNING gate before Risk is reached;
- financial Risk outputs and rejection semantics remain unchanged;
- no generic lifecycle authorization flag was introduced;
- the retained enum is justified as historical vocabulary without persistence
  changes;
- only approved implementation, focused test, and workstream artifacts changed.

## Independent result

### Functional and boundary checks

- `uv run pytest -q backend/tests/risk/test_service.py backend/tests/experiments/test_runner_diagnostics.py` — **PASS** (`26 passed`).
- `uv run ruff check backend/risk/service.py backend/experiments/runner.py backend/tests/risk/test_service.py backend/tests/experiments/test_runner_diagnostics.py` — **PASS**.
- `uv run pyright backend/risk/service.py backend/tests/risk/test_service.py` — **PASS** (`0 errors`).
- `git diff --check` — **PASS**.
- Backend source search finds no active `experiment_status` usage beyond the retained `RiskRejection.EXPERIMENT_NOT_RUNNING` enum member.
- The `_run_v2()` PENDING/RUNNING guard remains before Risk invocation; the focused regression test confirms a completed Experiment fails at validation without reaching Risk.
- No generic lifecycle or activation flag was added, and no persistence/schema/provider/runtime behavior changed.

### Concerns

- `uv run ruff format --check` reports the four touched implementation/test files as unformatted. The same files already fail the formatter check at the workstream base (`d8219d5`); no broad baseline reformat was applied.
- An additional strict-Pyright check over `backend/experiments/runner.py` and `backend/tests/experiments/test_runner_diagnostics.py` remains non-zero with the pre-existing diagnostics recorded by BUILD. The changed Risk files pass Pyright, and the focused tests pass.

## Validation conclusion

The T001 Risk lifecycle boundary cleanup meets its functional and architectural acceptance criteria. It is **ready for independent REVIEW**, with the known baseline formatting and strict-Pyright diagnostics retained as non-blocking concerns.
