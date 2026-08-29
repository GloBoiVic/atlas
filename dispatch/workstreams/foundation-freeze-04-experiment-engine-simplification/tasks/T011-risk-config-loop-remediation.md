# T011 — Risk Config Loop Remediation

Status: `DONE`

State history: `READY → IN_PROGRESS → DONE`

## Goal

Remediate the Important review finding that moved `RiskConfig` construction inside
the V2 frame loop, restoring the approved fail-closed setup boundary and ordering.

## Read

- `PLAN.md`
- `ARCHITECTURE.md`
- `VALIDATION.md`
- `REVIEW.md`
- `backend/experiments/runner.py`
- base SHA `3521274d1f3f492176eec8be9434bc76c6e4341b`

## Implement

- Move the existing `RiskConfig` construction to the intended pre-frame-loop V2
  setup location, matching the pre-remediation behavior and preserving all existing
  validation/error semantics.
- Do not change Risk policy, Strategy methodology, execution, accounting, market
  data, result ownership, tests' expected behavior, or unrelated formatting.
- Add or update a focused regression only if needed to prove construction occurs
  before frame processing and failures remain fail-closed.
- Run focused runner/Risk/golden tests, full relevant backend suites, Ruff, Pyright
  differential, compile, and diff checks. Write the completion receipt here.

## Acceptance

- The Important review finding is fixed with no behavior drift.
- Focused and relevant tests/quality checks pass.
- The receipt identifies the exact before/after ordering evidence.

## Do not implement

- Do not edit VALIDATION.md or REVIEW.md.
- Do not change migrations, product contracts, or unrelated baseline debt.
- Do not commit or modify preserved user files.
- Do not claim READY_FOR_USER.

## Completion receipt

ROLE: BUILD  
STATUS: DONE  
ARTIFACT: `dispatch/workstreams/foundation-freeze-04-experiment-engine-simplification/tasks/T011-risk-config-loop-remediation.md`

### Implementation

- Dedented the existing `RiskConfig(_decimal(...))` construction out of the V2
  warm-up frame loop and into the `_run_v2` setup body.
- The ordering now matches the base V2 setup: warm-up processing completes first,
  `RiskConfig` is validated once, and only then does observation/decision processing
  begin. No Risk policy, configuration value, or downstream execution behavior was
  changed.
- Added a focused empty-frame regression using malformed risk input. It proves the
  runner fails and records a sanitized failure rather than completing through a
  no-decision path; completion is explicitly guarded against.

### Files changed

- `backend/experiments/runner.py`
- `backend/tests/experiments/test_runner_diagnostics.py`
- This task receipt

### Checks / evidence

- Focused runner/Risk tests:
  `.venv/bin/pytest -q backend/tests/experiments/test_runner_diagnostics.py
  backend/tests/risk/test_service.py` — **26 passed**.
- Golden integration replay:
  `ATLAS_TEST_DATABASE_URL=postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test
  .venv/bin/pytest -q backend/tests/integration/test_golden_flows.py` — **2 passed**.
- Full integration backend suite — **33 passed, 4 warnings**.
- Full non-integration backend suite — **317 passed, 6 skipped, 1 warning**.
- Changed runner/test Ruff:
  `.venv/bin/ruff check backend/experiments/runner.py
  backend/tests/experiments/test_runner_diagnostics.py` — **PASS**.
- Full Ruff exact base/current comparison — **base 43/current 42, 0 current-only,
  1 resolved**; remaining current findings are baseline findings.
- Exact strict Pyright base/current comparison using base SHA
  `3521274d1f3f492176eec8be9434bc76c6e4341b`, matching by path, severity, rule, and
  full message while ignoring line movement — **base 3,333/current 2,673 errors,
  0 current-only, 299 resolved**.
- `python -m compileall -q backend` — **PASS**.
- `git diff --check` — **PASS**.
- AST ordering check confirms the current `RiskConfig` assignment is in the `_run_v2`
  try body after the warm-up loop (line 415) and before the decision loop (line 528);
  the base placement was after its warm-up loop at base lines 580–595 and before
  decision processing.
- PID `72514` remained alive. `.codegraph/` and `frontend/.env.local` remain
  preserved and untouched. No commit or Git-history operation was performed.

### Concerns

- Full Ruff remains non-clean only for pre-existing baseline diagnostics; the exact
  base/current differential has zero current-only findings. No other concerns.
