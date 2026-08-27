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

Final review correction: scope Strategy implementation lookup failure to the
registry/`implementation_for_version` seam; unrelated `KeyError`/`IndexError`
must not become `STRATEGY_VERSION_UNAVAILABLE`. Advance V2 seam ownership before
operations that can emit `ValueError`, or use narrow explicit typed failures, so
entry, protection, accounting/equity, and completion/metrics cannot inherit
Strategy ownership. Prove Strategy, Market Data, accounting, completion/metrics,
SQLAlchemy, unrelated LookupError, and unexpected engine behavior. Normal Risk
rejection remains a persisted RiskDecision.

## BUILD receipt

- **ROLE:** BUILD
- **WORKSTREAM:** foundation-freeze-02-experiment-correctness
- **BRANCH:** `solo/foundation-freeze-02-experiment-correctness`
- **CWD:** `/Users/vike/Desktop/atlas`
- **TASK:** T009
- **Status:** DONE — final external-review failure-ownership correction complete.

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

Final correction files changed: `backend/experiments/runner.py`,
`backend/tests/experiments/test_runner_diagnostics.py`, and this receipt. V2 now
maps only `StrategyVersionUnavailableError` from the registry implementation seam
to `STRATEGY_VERSION_UNAVAILABLE`; unrelated `KeyError`/`IndexError` use the
unexpected-engine path. V2 stage ownership advances through Strategy, market
data, entry/protection/equity, and result finalization seams, preserving typed
accounting and Risk rejection behavior.

Checks: focused diagnostics/metrics `27 passed`; experiments suite `84 passed`;
`python -m compileall -q backend`; `git diff --check`.

Concerns: PostgreSQL integration tests were not rerun; no database-backed code
was changed. Existing unrelated coordination edits (`PLAN.md`, `.codegraph/`,
`frontend/.env.local`) were not modified.
