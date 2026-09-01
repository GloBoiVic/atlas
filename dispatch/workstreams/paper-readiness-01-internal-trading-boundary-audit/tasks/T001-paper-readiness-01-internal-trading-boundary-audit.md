# T001 — Risk Lifecycle Boundary Cleanup

- **Workstream:** `paper-readiness-01-internal-trading-boundary-audit`
- **Role:** `BUILD`
- **Status:** `DONE`
- **State history:** `READY → IN_PROGRESS → DONE`
- **Owned artifact:** `dispatch/workstreams/paper-readiness-01-internal-trading-boundary-audit/tasks/T001-paper-readiness-01-internal-trading-boundary-audit.md`
- **Branch:** `solo/paper-readiness-01-internal-trading-boundary-audit`
- **Approval:** developer approved the reconciled PLAN/ARCHITECTURE and this implementation scope on 2026-09-01.

## Objective

Remove Experiment lifecycle coupling from reusable `RiskService` while preserving
historical Experiment behavior and all existing financial Risk semantics.

Current boundary:

```text
ExperimentRunner -- experiment_status --> RiskService
RiskService -- EXPERIMENT_NOT_RUNNING --> caller
```

Target boundary:

```text
ExperimentRunner owns and validates Experiment lifecycle
        ↓
RiskService evaluates financial Risk facts only
```

## Required implementation

1. Remove `experiment_status: str` from `RiskService.evaluate_pre_flight()`.
2. Remove `experiment_status: str` from `RiskService.evaluate_pre_submission()`.
3. Remove `experiment_status` from `_common()`.
4. Remove the active `experiment_status != "RUNNING"` Risk rule and its
   `EXPERIMENT_NOT_RUNNING` emission.
5. Update all current Risk call sites.
6. Update focused Risk tests so Experiment lifecycle is not tested as a Risk
   responsibility.
7. Inspect every usage of `RiskRejection.EXPERIMENT_NOT_RUNNING`. Preserve the
   enum value if historical compatibility or persisted vocabulary requires it;
   remove it only if no such requirement exists. Do not make persistence/schema
   changes solely for this decision. Stop `BLOCKED` if persistence changes appear
   necessary.
8. Preserve the existing `_run_v2()` Experiment lifecycle gate:

   ```python
   if experiment.status == "PENDING":
       ...
   elif experiment.status != "RUNNING":
       ...
   ```

## Preserve exactly

Do not change `AccountState`, `TradeIntent`, `RiskConfig`, `ExecutableQuote`,
`RiskDecision` financial semantics, PRE_FLIGHT/PRE_SUBMISSION meaning, EUR/USD/USD
capability, LONG-ask/SHORT-bid behavior, stop geometry, risk budget, whole-unit
floor sizing, target resolution, historical Strategy methodology, simulated
execution, persistence, OANDA integrations, runtime, or any PAPER/LIVE activation
or broker mutation behavior.

Do not replace `experiment_status` with `authorized`, `eligible`, `paper_active`,
`live_active`, `reconciled`, `runtime_ready`, or another generic lifecycle flag.

## Expected scope

Expected product/test files:

```text
backend/risk/service.py
backend/experiments/runner.py
backend/tests/risk/test_service.py
focused ExperimentRunner tests if needed
```

Package exports may change only if required by the enum compatibility decision.
Unexpected changes to OANDA, execution, persistence, domain, strategies, runtime,
frontend, or migrations are out of scope; stop `BLOCKED` rather than broadening.

## Acceptance and evidence

- Valid historical Experiment inputs produce identical financial Risk results:
  approval/rejection, entry, stop, target, risk budget, quantity, actual risk, and
  financial rejection codes.
- Experiment lifecycle failure remains owned and enforced by Experiment
  orchestration, not reusable Risk.
- No generic lifecycle authorization enters Risk.
- Focused tests cover both Risk financial behavior and the preserved Experiment
  lifecycle interaction.
- Run at minimum:

  ```bash
  uv run pytest backend/tests/risk/test_service.py <smallest relevant ExperimentRunner test files covering Risk/lifecycle interaction>
  ```

  Then run targeted Ruff, Pyright, and `git diff --check`. Do not run the full
  backend, database, OANDA, frontend, browser, or migration suites unless the
  actual diff demonstrates a broader blast radius.

## Worker Evidence

Record changed files, implementation decisions, focused checks, and any concerns
here when the task is complete. Do not edit the approved PLAN or ARCHITECTURE.

ROLE: BUILD
STATUS: DONE
ARTIFACT: `dispatch/workstreams/paper-readiness-01-internal-trading-boundary-audit/tasks/T001-paper-readiness-01-internal-trading-boundary-audit.md`

### Implementation

- Removed `experiment_status` from both public `RiskService` evaluation methods and
  `_common()`. Risk now evaluates only the supplied financial facts and continues to
  preserve the existing sizing, geometry, currency, instrument, and rejection
  semantics.
- Removed lifecycle arguments from both ExperimentRunner Risk call sites.
- Preserved the `_run_v2()` PENDING/RUNNING lifecycle gate and added a focused test
  proving a non-running Experiment fails before Risk is reached.
- Retained `RiskRejection.EXPERIMENT_NOT_RUNNING` as historical rejection vocabulary;
  the reusable Risk service no longer emits it.
- Updated focused Risk tests so Experiment lifecycle is not a Risk input or test
  responsibility.

### Files changed

- `backend/risk/service.py`
- `backend/experiments/runner.py`
- `backend/tests/risk/test_service.py`
- `backend/tests/experiments/test_runner_diagnostics.py`
- This task artifact

### Checks / evidence

- `uv run pytest -q backend/tests/risk/test_service.py backend/tests/experiments/test_runner_diagnostics.py` — **26 passed**.
- `uv run ruff check backend/risk/service.py backend/experiments/runner.py backend/tests/risk/test_service.py backend/tests/experiments/test_runner_diagnostics.py` — **PASS**.
- `uv run pyright backend/risk/service.py` — **0 errors**.
- `uv run pyright backend/tests/risk/test_service.py` — **0 errors**.
- `git diff --check` — **PASS**.
- Source search confirms no active `experiment_status` usage remains under
  `backend/`; only the retained historical enum member remains.

### Concerns

- `backend/experiments/runner.py` and its diagnostics test retain pre-existing
  strict-Pyright findings unrelated to this boundary cleanup (861 and 60 errors,
  respectively); no diagnostics were reported at the changed Risk call lines or
  in the new lifecycle test body. `ruff format --check` also reports existing
  formatting differences in the touched baseline files; no broad reformat was
  applied. No persistence, schema, OANDA, runtime, execution, frontend, or
  activation behavior was changed.
