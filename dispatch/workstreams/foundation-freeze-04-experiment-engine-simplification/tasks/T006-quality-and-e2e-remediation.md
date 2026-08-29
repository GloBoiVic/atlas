# T006 — Quality and E2E Validation Remediation

Status: `DONE`

State history: `READY → IN_PROGRESS → DONE_WITH_CONCERNS → DONE`

## Goal

Remove remaining Freeze 04-only strict Pyright diagnostics and unblock the required
Playwright gate without stopping the existing local process on port 8000.

## Read

- `PLAN.md`
- `ARCHITECTURE.md`, section 8
- `VALIDATION.md`
- `tasks/T005-validation-remediation.md`
- the base SHA `3521274d1f3f492176eec8be9434bc76c6e4341b`
- `backend/experiments/runner.py`
- changed backend test seams reported by the exact T005 Pyright comparison
- `playwright.config.ts` and `tests/e2e/`

## Implement

- Resolve only current-only strict Pyright diagnostics attributable to Freeze 04 in
  changed production/test files. Prefer precise imports, annotations, and typing
  casts at test doubles; do not alter runtime behavior or suppress diagnostics
  broadly. Preserve all frozen Strategy, runner, market-data, Risk, execution,
  accounting, persistence, and result semantics.
- Make Playwright API/web server ports configurable through explicit E2E-only
  environment variables, retaining current defaults. Use this only to run against
  an isolated alternate local port when 8000 is occupied; do not stop or reuse an
  unrelated process and do not change application runtime ports.
- Do not change database schema/configuration, migrations, product behavior, expected
  outputs, or preserved user files.

## Acceptance

- Exact base/current comparison has no unresolved Freeze 04-only strict Pyright
  diagnostics in changed production or test seams, or any remaining diagnostic is
  proven to be pre-existing with exact evidence.
- E2E harness supports explicit alternate ports while preserving default behavior.
- E2E runs with the dedicated `atlas_test` database and alternate ports without
  stopping PID 72514.
- Targeted tests, compile, lint, and diff checks pass.

## Do not implement

- Do not modify or stop PID 72514.
- Do not claim validation PASS or edit VALIDATION.md.
- Do not add pyright suppressions/config baselines or unrelated cleanup.

## Completion receipt

ROLE: BUILD  
STATUS: DONE_WITH_CONCERNS  
ARTIFACT: `dispatch/workstreams/foundation-freeze-04-experiment-engine-simplification/tasks/T006-quality-and-e2e-remediation.md`

### Implementation

- Removed the T005 current-only strict Pyright differential from changed production
  and test seams using import/type annotations, a typed terminal-result boundary,
  test-double casts, and typed AST/test callbacks. No runtime or public contract
  behavior was changed.
- Added explicit E2E-only `ATLAS_E2E_API_PORT` and `ATLAS_E2E_WEB_PORT` variables,
  defaulting to `8000` and `3000`. The API command, web command, proxy target, health
  URL, and Playwright base URL use those values; application runtime defaults were
  not changed.
- Updated the E2E seed harness to the current V2 golden seed API and to create its
  invalid-config fixture through the immutable Experiment creation boundary. No
  migration, schema, or product code was changed.

### Files changed

- `backend/experiments/runner.py`
- `backend/tests/e2e_seed.py`
- `backend/tests/experiments/test_price_analysis_results.py`
- `backend/tests/experiments/test_results.py`
- `backend/tests/experiments/test_runner_diagnostics.py`
- `backend/tests/strategies/test_ema_sweep_confirmation_break.py`
- `playwright.config.ts`
- This task receipt

### Checks / evidence

- Exact T005-style base/current strict Pyright comparison (path, severity, rule, and
  full message; line movement ignored): base `3521274d1f3f492176eec8be9434bc76c6e4341b`
  `3333` errors / `136` files; current `2673` errors / `130` files; **0
  current-only diagnostics in changed production/test files**. T005's earlier run
  recorded `3340` / `2930`; the final rerun used the same base SHA and invocation
  shape and records the exact final counts above.
- Focused backend tests: **61 passed**.
- Full non-integration backend tests: **316 passed, 6 skipped, 1 warning**.
- Full integration tests with
  `ATLAS_TEST_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test'`:
  **33 passed, 4 warnings**.
- Changed-file Ruff import-order check: **PASS**. `python -m compileall -q backend`
  and `git diff --check`: **PASS**.
- Web lint, typecheck, Vitest, and production build: **PASS** (23 web tests).
  Playwright config formatting: **PASS**.
- E2E was run with the required dedicated database and alternate ports, without
  stopping or reusing PID `72514`:
  `ATLAS_E2E_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test'`
  `ATLAS_E2E_API_PORT='18080' ATLAS_E2E_WEB_PORT='13000' npm run test:e2e`.
  The harness started API on `18080` and web on `13000`; **1 passed, 4 failed**.
  Port `8000` remained occupied by PID `72514` throughout.

### Concerns / exact remaining blockers

- T006 cannot claim a clean E2E gate: the workflow tests fail at their existing
  `getByLabel('StrategyVersion')` setup assertion because the selected value is
  blank, although the API configuration-options request returns `200` and the
  alternate-port harness starts correctly. The foundation E2E test passes. Fixing
  the workflow selector/UI expectation is outside this task's prohibition on
  changing product behavior or test expectations.
- Strict Pyright remains globally non-clean baseline debt (`2673` current errors),
  but its exact changed-file current-only differential is zero.
- Preserved `.codegraph/` and `frontend/.env.local` were not modified. No commit or
  other Git-history operation was created.
