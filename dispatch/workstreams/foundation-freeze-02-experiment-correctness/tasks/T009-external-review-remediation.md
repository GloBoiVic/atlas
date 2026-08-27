# T009 — External review remediation

Status: `DONE`

Fix maximum drawdown amount and percentage as independently tracked maxima over
the canonical persisted equity sequence. Remove exception-message keyword
classification from `classify_runner_value_error`; classify by the failing seam,
including explicit Strategy, Risk, Execution, Market Data, Validation/
Accounting, Persistence, and non-database unexpected failures. Add behavioral
regressions without changing canonical sampling or other Freeze 02 behavior.

Required regressions: an earlier smaller-dollar/larger-percentage drawdown must
coexist with a later larger-dollar/smaller-percentage drawdown; SQLAlchemy is
Persistence; Strategy, Risk rejection, Execution, and accounting invariant map
to their owning categories; an unexpected non-database engine exception is not
Persistence; and changing exception wording does not change classification.

## BUILD receipt

- **ROLE:** BUILD
- **WORKSTREAM:** foundation-freeze-02-experiment-correctness
- **BRANCH:** `solo/foundation-freeze-02-experiment-correctness`
- **CWD:** `/Users/vike/Desktop/atlas`
- **TASK:** T009
- **Status:** DONE — continuation added the required direct runner fallback
  regression for unexpected non-database engine failures.

Implemented independent amount/percentage drawdown maxima over canonical equity
order. Replaced message-keyword classification with typed seam/category mapping;
SQLAlchemy remains Persistence, accounting fill failures are Validation-owned,
and unexpected engine failures are Validation-owned rather than Persistence.

Files changed:

- `backend/experiments/metrics.py`
- `backend/experiments/runner.py`
- `backend/tests/experiments/test_metrics.py`
- `backend/tests/experiments/test_runner_diagnostics.py`

Checks: initial targeted metrics/runner diagnostics `23 passed`; experiments suite
`80 passed`; continuation diagnostics/metrics `24 passed`; experiments suite
rerun `81 passed`; `python -m compileall -q backend`; `git diff --check`.

Continuation files changed: `backend/tests/experiments/test_runner_diagnostics.py`
and this receipt. The new test invokes `_run_v2` with a deterministic exploding
non-database strategy repository and asserts durable `VALIDATION` /
`UNEXPECTED_ENGINE_FAILURE`, not `PERSISTENCE`.

Concerns: PostgreSQL integration tests were not rerun; no database-backed code
was changed.
