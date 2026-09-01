# REVIEW — PAPER Readiness 01 Risk Lifecycle Boundary Cleanup

## Status

`PASS`

- **Workstream:** `paper-readiness-01-internal-trading-boundary-audit`
- **Task:** `T001`
- **Role:** `REVIEW`
- **Branch:** `solo/paper-readiness-01-internal-trading-boundary-audit`
- **Scope:** independently judge the approved PLAN/ARCHITECTURE, T001 BUILD
  receipt, focused VALIDATION evidence, implementation diff, lifecycle boundary,
  compatibility decision, and scope constraints.

## Review focus

- `RiskService` no longer accepts or evaluates Experiment lifecycle;
- `_run_v2()` remains the Experiment-owned PENDING/RUNNING gate;
- historical financial Risk results and rejection semantics are preserved;
- `EXPERIMENT_NOT_RUNNING` is retained only if historical vocabulary requires it
  and is no longer emitted by reusable Risk;
- no generic lifecycle flag, persistence/schema change, or excluded-area change
  was introduced;
- validation concerns are baseline-only and do not conceal an approved-scope
  defect.

## Independent judgment

- `RiskService.evaluate_pre_flight()`, `evaluate_pre_submission()`, and
  `_common()` no longer accept or inspect Experiment lifecycle state. No current
  backend call site still supplies `experiment_status`.
- `ExperimentRunner._run_v2()` retains the PENDING/RUNNING guard before the
  strategy and Risk path. The focused regression test uses an exploding Risk
  double and confirms a completed Experiment fails without reaching Risk.
- The financial Risk path is unchanged for valid historical inputs: instrument
  and currency capability, position/account checks, stop geometry, executable
  side, sizing, target resolution, and rejection codes remain intact.
- `RiskRejection.EXPERIMENT_NOT_RUNNING` is conservatively retained as readable
  historical vocabulary. It is no longer emitted by reusable Risk, and the
  persisted `rejection_code` is an unconstrained string column, so no migration
  or persistence change is required.
- The branch diff is limited to the approved Risk/runner implementation and
  focused tests, plus the expected workstream evidence/bookkeeping artifacts.
  No provider, execution, persistence, schema, runtime, frontend, activation,
  or broker-mutation behavior changed.

## Checks / evidence

- `uv run pytest -q backend/tests/risk/test_service.py backend/tests/experiments/test_runner_diagnostics.py` — **26 passed**.
- Targeted `uv run ruff check` — **PASS**.
- Targeted `uv run pyright backend/risk/service.py backend/tests/risk/test_service.py` — **0 errors, 0 warnings, 0 informations**.
- `git diff --check` — **PASS**.
- Targeted `uv run ruff format --check` still reports the four touched files as
  unformatted; VALIDATION independently confirms these same formatter failures
  exist at the workstream base. This is a pre-existing TOOLING concern, not an
  approved-scope product or regression defect.
- Strict Pyright findings remain in the pre-existing `runner.py` and diagnostics
  test baseline; the changed Risk files pass the targeted check and no changed
  call site is implicated.

## Findings and decision

- **CRITICAL:** none.
- **IMPORTANT:** none.
- **MINOR:** baseline formatter and strict-Pyright debt remains in touched files;
  non-blocking.

**Decision: `PASS` — T001 satisfies the approved boundary-cleanup contract and
is ready for explicit merge approval.**
