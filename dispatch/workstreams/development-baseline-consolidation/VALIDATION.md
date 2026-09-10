# VALIDATION - Development Baseline Consolidation

- **Status:** `PASS`
- **Role:** `VALIDATE`
- **Workstream:** `development-baseline-consolidation`
- **Branch:** `solo/development-baseline-consolidation`
- **Base:** `main` at `611fe10b9b596f9e48339f305b99023d402c4514`
- **Validator:** independent VALIDATE
- **Validated:** `2026-09-10`

## Decision

`PASS`. The approved Feature scope is implemented without an identified PRODUCT or
REGRESSION defect. The required safe backend and frontend gates pass. The known repository
typing, formatting, lint, and intermittent standalone Vitest issues are classified below as
TOOLING / NEW SCOPE and do not change the approved-scope result.

No application, test, fixture, selector, harness, workflow, schema, migration, or generated
implementation file was edited by VALIDATE. The only file edited by this role is this
artifact.

## Diff Audit

The following commands were run against the approved base:

```text
git status --porcelain=v1 -uall
git diff 611fe10b9b596f9e48339f305b99023d402c4514 --stat
git diff 611fe10b9b596f9e48339f305b99023d402c4514 --name-status
git log --oneline -10 --decorate
```

`HEAD` is the base commit `611fe10b9b596f9e48339f305b99023d402c4514`, so there is no
committed branch delta. The worktree delta contains 15 tracked files with 72 insertions and
55 deletions. The tracked implementation/documentation paths are:

```text
AGENTS.md
README.md
backend/domain/market_data.py
backend/domain/trading.py
backend/execution/contract.py
backend/execution/fill_application.py
backend/persistence/database.py
backend/risk/service.py
backend/runtime/activation.py
backend/tests/e2e_seed.py
backend/tests/experiments/test_configuration.py
dispatch/ACTIVE.md
frontend/components/experiment-workflow.tsx
frontend/components/experiments/chart-support.ts
frontend/components/experiments/shared.ts
```

The untracked workstream artifacts are PLAN, PYRIGHT, COMPATIBILITY, four task receipts,
and this VALIDATION artifact. No untracked application or test source is present.
`dispatch/ACTIVE.md` is operational workstream state and was observed, not changed by
VALIDATE.

```text
git diff --check 611fe10b9b596f9e48339f305b99023d402c4514 -- PASS
git diff --check -- PASS
```

The second command covers the tracked worktree diff. After this artifact was written, each
untracked workstream Markdown file was also checked with `git diff --no-index --check
/dev/null <file>`; every invocation reported no whitespace diagnostics and returned the
normal non-zero status for a non-empty no-index diff.

## Validation Gates

| Command | Result |
| --- | --- |
| `uv lock --check` | PASS; resolved 41 packages in 4 ms |
| `uv run --frozen pyright --version` | PASS; Pyright 1.1.411; non-failing update notice to 1.1.414 |
| `uv run --frozen ruff check backend/domain/market_data.py backend/domain/trading.py backend/execution/contract.py backend/execution/fill_application.py backend/persistence/database.py backend/risk/service.py backend/runtime/activation.py backend/tests/e2e_seed.py backend/tests/experiments/test_configuration.py` | PASS; all checks passed |
| `uv run --frozen ruff format --check backend/domain/market_data.py backend/domain/trading.py backend/execution/contract.py backend/execution/fill_application.py backend/persistence/database.py backend/risk/service.py backend/runtime/activation.py backend/tests/e2e_seed.py backend/tests/experiments/test_configuration.py` on base and current | Same result; 5 files would be reformatted and 4 were already formatted; no new changed-surface formatting debt |
| `uv run --frozen ruff check backend` | Exit 1 with 28 diagnostics, all in unrelated pre-existing migration/repository/test files; none in a changed path |
| `uv run --frozen ruff format --check backend` | Exit 1 with the recorded repository baseline of 68 files to reformat and 147 already formatted |
| `uv run pytest -m "not integration and not external"` | PASS; 1,296 passed, 4 skipped, 115 deselected, 4 warnings in 43.49 s |
| `npx prettier --check frontend/components/experiment-workflow.tsx frontend/components/experiments/chart-support.ts frontend/components/experiments/shared.ts` | PASS |
| `npx eslint frontend/components/experiment-workflow.tsx frontend/components/experiments/chart-support.ts frontend/components/experiments/shared.ts` | PASS |
| `npm run typecheck:web` | PASS |
| `npm run check:web` | PASS; format, lint, typecheck, 20 frontend test files with 146 tests, and Next build all completed; lint reported 240 existing warnings and 0 errors |

The backend warning set was the existing Starlette deprecation warning plus three unknown
pytest marker warnings from an excluded integration test module. The frontend warning set is
the existing unused-import/unused-symbol baseline; no changed frontend file caused a gate
error.

## Pyright Evidence

The locked repository-wide structured run was:

```text
uv run --frozen pyright backend --outputjson
```

It produced valid JSON, exit `1` for diagnostics, Pyright `1.1.411`, 214 files analyzed,
3,011 errors, 0 warnings, and 0 informations. The diagnostic split was 1,845 production
errors across 25 files and 1,166 test errors across 27 files. The leading rules were:

```text
584 reportUnknownArgumentType
567 reportUnknownMemberType
539 reportUnknownParameterType
528 reportMissingParameterType
265 reportArgumentType
183 reportUnknownVariableType
 87 reportUnknownLambdaType
 68 reportAttributeAccessIssue
```

The highest-concentration files were `backend/experiments/runner.py` with 861 diagnostics,
`backend/market_data/freeze03_benchmark.py` with 263, and then the existing test and
historical-load files recorded in `PYRIGHT.md`.

The exact historical command was independently rerun:

```text
uv run pyright backend
```

It returned exit `1` with `3011 errors, 0 warnings, 0 informations`. Pyright output was
valid; the non-zero status is a diagnostic result, not a runtime or tool invocation failure.
The current locked version and the structured count agree with the historical command scope.

The historical success receipt was independently located at
`319ed6317df4e1025cd13e2b1c7c3b330d43bed4` and records:

```text
uv run pyright backend | PASS - no type errors; tool update notice only
```

The comparison below produced no output:

```text
git diff --name-status e2ad47c5cbfbca89d58f915745f81180c4864db9 \
  611fe10b9b596f9e48339f305b99023d402c4514 -- pyproject.toml uv.lock backend
```

Therefore the historical receipt has no tracked difference in relevant configuration, lock
state, command scope, or included backend source that explains the contradiction. The
receipt has no raw output, version, exit status, or execution-environment record. An
alternate environment, stale or partial output, or incorrect status interpretation remains
possible, but no one cause is asserted. `PYRIGHT.md` correctly bounds this as typing debt
and does not claim a completed root-cause analysis.

The changed-surface comparison used the same locked environment and the nine changed Python
files (seven production files and two test files) against a clean base worktree:

```text
uv run --frozen pyright backend/domain/market_data.py backend/domain/trading.py \
  backend/execution/contract.py backend/execution/fill_application.py \
  backend/persistence/database.py backend/risk/service.py \
  backend/runtime/activation.py backend/tests/e2e_seed.py \
  backend/tests/experiments/test_configuration.py --outputjson
```

Both before and after reports were valid Pyright 1.1.411 reports with 9 files analyzed,
37 errors, 0 warnings, and 0 informations. Normalized file/rule/message diagnostics were
identical. The only location changes were line shifts caused by comment edits in
`fill_application.py`; no new diagnostic was introduced in a production or test file.

The clean probes required by `PYRIGHT.md` were independently rerun:

```text
uv run --frozen pyright backend/domain/strategy.py backend/strategies/contract.py --outputjson
  exit 0; 0 errors, 0 warnings, 0 informations
uv run --frozen pyright backend/tests/integrations/test_oanda_risk_projection.py --outputjson
  exit 0; 0 errors, 0 warnings, 0 informations
```

This supports the temporary changed-surface policy in `AGENTS.md`: no new diagnostics in
touched files, clean isolated surfaces remain clean, and repository-wide debt is reported
separately rather than normalized or hidden.

## Acceptance Coverage

| Acceptance area | Independent evidence | Result |
| --- | --- | --- |
| Repository truth | `README.md` and `AGENTS.md` state historical Experiment capability, guarded OANDA Practice PAPER execution/runtime/activation/reconciliation capability, undeployed status, non-authorization from startup/broker inspection/configured credentials, and no committed-main LIVE capability. Current `api/app.py`, `api/paper.py`, `runtime/main.py`, and activation code support those claims. | PASS |
| Provider-first and complexity guidance | Exact approved provider-first rule and complete generated-file/400/600/800/1,200-line complexity ratchet are present in `AGENTS.md`, including the future PLAN file/growth-exception requirement. | PASS |
| Compatibility inventory | `COMPATIBILITY.md` explicitly classifies every required seam: StrategyState schema 1 PROTOTYPE; `window_bars`/`AWAITING_CONFIRMATION` PROTOTYPE; `warm_up_bars` DEFERRED; snapshot V1 EVIDENCE; legacy metric states EVIDENCE; historical/current result identifiers CURRENT plus EVIDENCE responsibility; `indicators.py` EVIDENCE; `indicators_v2.py` CURRENT; EMA adaptor CURRENT; historical-load fields CURRENT; runtime aliases DEFERRED. Current callers, persistence/evidence use, API/test/generated responsibility, and retirement points are recorded for each. | PASS |
| Compatibility preservation | Searches confirmed V1 result reads, legacy metric projection, warm-up fallback/synonym, historical-load counters, both indicator modules, the registered EMA adaptor, and runtime alias exports still exist. No retained CURRENT or EVIDENCE seam was removed. | PASS |
| Phase terminology | The changed backend diff contains only deletion or rewording of current comments/docstrings, the local `phase4` rename, and a test identifier rename. No historical migration revision, persisted identifier, benchmark, constraint, trigger, function, or compatibility enum was renamed. | PASS |
| Removed symbol proof | Base/current `git grep` shows `WorkflowFeatureBoundaries`, `chartTime`, `chartTick`, and `_unsafe_attempt_exists` only as base declarations and no current tracked references. The duplicate `ChartPoint`/`strictlyAscending` declarations were removed from `shared.ts`; canonical `chart-support.ts` declarations and all chart consumers plus the direct timestamp regression test remain. Runtime aliases remain exported through lazy package exports. | PASS |
| Persistence/API/generated boundaries | `git diff --name-status 611fe10b9b596f9e48339f305b99023d402c4514 -- backend/persistence/migrations backend/api frontend/lib/api.generated.ts backend/api/schemas.py backend/persistence/models.py` produced no output. `backend/persistence/database.py` changed only a comment. No migration, schema, HTTP contract, generated client, persisted data, or evidence changed. | PASS |
| Safety and financial boundaries | The only executable Python edits are the `phase4` local rename and removal of an unreferenced private forwarder. Model-version values and fill exit-reason logic are unchanged. No Strategy, Risk, execution accounting, reconciliation, protection, activation fencing, broker-authority, or financial semantics changed. | PASS |
| Browser scope | The frontend edits remove unused exports/types/wrappers and retain the canonical chart owner; they do not change rendered UI, data fetching, event behavior, or browser-visible layout. The full frontend typecheck, tests, and production build passed, so Safari validation was not material for this cleanup. | PASS |

## Safety Confirmation

No database reset, database migration, Alembic upgrade/current/check, credential creation or
change, `atlas-runtime` start, API server start, real OANDA or broker request, PAPER activation,
PAPER reconciliation, broker mutation, or capital-capable operation was performed by this
validator. The safe backend suite used unit, recorded-shape, and mocked provider tests; no
credentialed external marker was run and no real secret was read or logged. The BUILD
receipts independently record the same boundary and report no such operation.

## Findings And Limitations

| Classification | Finding | Disposition |
| --- | --- | --- |
| `TOOLING / NEW SCOPE` | Repository-wide Ruff format remains non-clean at 68 files, repository-wide Ruff lint reports 28 unrelated diagnostics, and repository-wide Pyright reports 3,011 errors. | Explicitly accepted baseline in the approved PLAN, `PYRIGHT.md`, and T003/T004 receipts. Focused changed-surface Ruff/Pyright checks add no regression. No remediation opened. |
| `TOOLING / NEW SCOPE` | Two standalone current-worktree `npm run test:web` invocations returned exit 1 after all 146 tests passed because Vitest reported one late `ReferenceError: window is not defined` from `home_page.test.tsx`. The focused home-page test passed in both current and base worktrees; the base full suite passed twice; the required `npm run check:web` passed twice, including the same 146-test suite and build. | Treated as an intermittent existing test-harness/teardown issue outside this cleanup scope, not a product or approved-scope regression. The required frontend gate is PASS. No remediation opened. |

No `PRODUCT / DEFECT`, `PRODUCT / NEW SCOPE`, `REGRESSION / DEFECT`, or
`REGRESSION / NEW SCOPE` finding was identified. No approved-scope blocker was found, so
Solo remediation was not requested.

The following checks were intentionally not run because this Feature changed no migration,
database contract, external-provider behavior, or browser-visible behavior:

```text
ATLAS_TEST_DATABASE_URL=<dedicated *_test database> uv run pytest -m integration
uv run pytest -m external
npm run test:e2e
```

Those omissions do not reduce coverage of the approved cleanup; they avoid database access,
credentialed provider activity, and browser/runtime operation at a boundary where no such
change occurred.

## VALIDATE Receipt

```text
ROLE: VALIDATE
STATUS: PASS
ARTIFACT: dispatch/workstreams/development-baseline-consolidation/VALIDATION.md
FILES CHANGED: dispatch/workstreams/development-baseline-consolidation/VALIDATION.md only
CHECKS / EVIDENCE: Base diff audited; focused Ruff and Pyright checks show no changed-surface regression; safe backend tests pass; npm run check:web passes; compatibility, phase, API, persistence, generated, and safety boundaries verified.
FINDINGS / CONCERNS: TOOLING / NEW SCOPE only: accepted repository baseline debt and an intermittent standalone Vitest teardown error; no approved-scope defect or product/regression finding.
```
