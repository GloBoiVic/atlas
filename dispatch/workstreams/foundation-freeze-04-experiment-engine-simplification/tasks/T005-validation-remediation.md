# T005 — Validation Remediation

Status: `DONE`

State history: `READY → IN_PROGRESS → DONE_WITH_CONCERNS → DONE`

## Goal

Remediate validation findings that are attributable to Freeze 04 without expanding
the approved architecture or silently accepting new quality regressions.

## Read

- `PLAN.md`
- `ARCHITECTURE.md`, section 8
- `VALIDATION.md`
- `tasks/T002-legacy-read-and-ingestion-isolation.md`
- `backend/experiments/results.py`
- the base SHA `3521274d1f3f492176eec8be9434bc76c6e4341b`

## Implement

- Fix the newly introduced Ruff import-order finding in
  `backend/experiments/results.py` without broad unrelated lint cleanup.
- Reconcile T002's header status with its completion receipt and PLAN state.
- Compare strict Pyright findings at the recorded base SHA with the current branch
  for Freeze 04-touched files. Identify any newly introduced errors and remediate
  only those required by this workstream; if all findings are baseline debt, record
  exact evidence in the receipt rather than adding a speculative type-system
  configuration or unrelated cleanup.
- Do not modify database configuration, migrations, product behavior, Strategy
  methodology, Risk, execution, accounting, or existing test expectations.

## Acceptance

- Changed-file Ruff has no new import-order finding.
- T002 metadata is internally consistent.
- The receipt states the base/current strict Pyright comparison and any remaining
  baseline debt precisely.
- All changes remain within the approved Freeze 04 scope.

## Do not implement

- Do not claim PostgreSQL or E2E validation passed; those remain VALIDATE-owned gates.
- Do not alter unrelated pre-existing Ruff/Pyright violations.
- Do not commit or modify preserved untracked user files.

## Completion receipt

ROLE: BUILD  
STATUS: DONE_WITH_CONCERNS  
ARTIFACT: `dispatch/workstreams/foundation-freeze-04-experiment-engine-simplification/tasks/T005-validation-remediation.md`

### Files changed

- `backend/experiments/results.py` — reordered the two snapshot-schema imports and
  annotated the chart candle payload so the new result-reader code has the declared
  `ChartContext` type.
- `backend/market_data/ingestion.py` — made `NativeFetchResult` attributes read-only
  protocol properties. This preserves the existing provider result shape while
  removing the newly introduced structural-protocol mismatch in the application and
  Freeze 03 native-source checks.
- `dispatch/workstreams/foundation-freeze-04-experiment-engine-simplification/tasks/T002-legacy-read-and-ingestion-isolation.md`
  — reconciled the header and state history to `DONE_WITH_CONCERNS`, matching its
  existing completion receipt and PLAN state.

No database configuration, migration, product behavior, Strategy methodology, Risk,
execution, accounting, or preserved untracked user file was changed. No commit was
created.

### Checks / evidence

- Changed-file import-order check:
  `.venv/bin/ruff check --select I` over all Freeze 04 changed Python files: **PASS**.
  `ruff check backend/experiments/results.py` now reports no I001; its remaining 14
  E501 findings are the same logical pre-existing findings recorded by VALIDATE.
- Targeted remediation/regression tests:
  `.venv/bin/pytest -q backend/tests/experiments/test_results.py
  backend/tests/experiments/test_price_analysis_results.py
  backend/tests/experiments/test_runner_diagnostics.py
  backend/tests/market_data/test_freeze03_regressions.py`: **80 passed**.
  Historical-load/task checks: **39 passed, 1 skipped**.
- `python -m compileall -q backend`: **PASS**.
- `git diff --check`: **PASS**.
- Strict Pyright was run from the recorded base and current source, using the same
  `.venv` and strict project settings. Base was archived from SHA
  `3521274d1f3f492176eec8be9434bc76c6e4341b` and checked with:
  `.venv/bin/pyright -p <base>/pyproject.toml --venvpath /Users/vike/Desktop/atlas
  --outputjson <base>/backend`; current was checked with
  `.venv/bin/pyright --outputjson`.
  Whole-repository result: **base 3,340 errors / 136 files; current 2,930 errors /
  130 files**. For the 21 current Freeze 04-touched Python paths (20 tracked at
  base plus the new isolation test), the exact total was **base 1,962 / current
  1,723**. Per-file current/base counts were:
  `api/app.py 17/18`, `domain/strategy.py 0/0`,
  `domain/strategy_requirements.py 6/6`, `experiments/results.py 53/97`,
  `experiments/runner.py 986/1208`, `market_data/aggregation.py 0/0`,
  `market_data/coverage.py 0/0`, `market_data/ingestion.py 77/115`,
  `persistence/models.py 0/0`, `strategies/contract.py 0/0`,
  `tests/e2e_app.py 0/4`, `tests/experiments/test_clock.py 0/0`,
  `tests/experiments/test_price_analysis_results.py 242/188`,
  `tests/experiments/test_results.py 145/122`,
  `tests/experiments/test_runner_diagnostics.py 86/79`,
  `tests/integration/test_golden_flows.py 0/2`,
  `tests/market_data/test_task3.py 3/3`,
  `tests/strategies/test_ema_sweep_confirmation_break.py 1/12`,
  `tests/strategies/test_legacy_strategy_isolation.py 0/0`,
  `tests/test_historical_data_load.py 107/108`.
- Location-independent exact diagnostic comparison (path, severity, rule, full
  message; line movement ignored) reduced the production/source differential to
  **17 current-only diagnostics, all in `backend/experiments/runner.py`**, and
  **322 resolved**. The 17 are the removed-loop/renamed-terminal-method Pyright
  reports (13 unused-import reports for names still used by the V2 loop, one unused
  private handoff report despite its runtime construction, and three unknown-type
  reports at the renamed `_complete_result` call). They were not “fixed” with broad
  annotations or suppressions because that would be unrelated typing cleanup and
  could obscure the frozen runner behavior.
- Across all touched existing files, the same exact comparison reports **163
  current-only / 402 resolved** diagnostics; the additional current-only findings
  are in changed test doubles and intentionally changed result-reader test seams.
  They remain strict-Pyright debt rather than a clean type gate. The concrete newly
  introduced source protocol/payload mismatches found by this comparison were
  remediated above.
- PostgreSQL, integration, golden-replay, and Playwright E2E validation were not
  claimed or rerun by this BUILD task.

### Concerns

- Strict Pyright remains non-clean. The exact base/current evidence above separates
  the reduced existing debt from the remaining runner and changed-test differential;
  resolving it would exceed T005's narrow remediation scope.
- The previously recorded isolated PostgreSQL and E2E validation blockers remain
  VALIDATE-owned and unresolved.
