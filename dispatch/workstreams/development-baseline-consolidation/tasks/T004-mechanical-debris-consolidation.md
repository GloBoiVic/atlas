# T004 - Mechanical Debris Consolidation

- **Workstream:** `development-baseline-consolidation`
- **Status:** `DONE`
- **Role:** `BUILD`
- **Branch:** `solo/development-baseline-consolidation`
- **Base:** `611fe10b9b596f9e48339f305b99023d402c4514`
- **Dependency:** T003

## Outcome

Remove only mechanically proven duplicate or dead symbols from the approved candidate set,
without changing Atlas behavior or expanding existing oversized files.

## Scope

Candidate areas named by the approved PLAN:

- duplicated Experiment chart types and order helpers;
- unused imports or locals in files already touched by this workstream;
- genuinely unreferenced workflow helpers;
- runtime service aliases proven to have no consumer.

Required proof before removing any symbol:

- repository-wide import and reference search;
- nearby and repository tests;
- API exposure and generated surfaces where relevant;
- persistence/evidence responsibility review;
- compatibility inventory and natural-retirement review from T003.

Update or add only narrow regression coverage when a removed duplicate/dead symbol has a
direct test contract. Preserve the implementation that owns the current behavior; do not
redesign Experiment components or launch a frontend warning cleanup.

## Constraints

- Do not remove Strategy, indicator, EMA adaptor, historical-load, result-schema, snapshot,
  or other compatibility seams unless T003 evidence proves there is no current, evidence,
  API, persistence, test-contract, or planned-transition responsibility.
- Do not change Strategy, Risk, execution, reconciliation, protection, activation,
  broker-authority, or financial semantics.
- No migrations, data reset, broad refactor, new provider behavior, or new development-phase
  terminology.
- Do not materially grow existing oversized files; extract nothing unless required to keep a
  changed responsibility cohesive and within the approved scope.

## Checks

Run focused tests and lint/type checks for changed surfaces, plus `git diff --check`. Record
the exact symbols removed, proof of no responsibility, checks, and completion receipt in this
task file. If no candidate meets the proof standard, retain it and record that deliberate
decision rather than forcing a deletion.

## Worker Evidence

BUILD execution completed.

## Immutable BUILD Receipt

- **Status:** `DONE`
- **Files changed:**
  - `frontend/components/experiments/chart-support.ts`
  - `frontend/components/experiments/shared.ts`
  - `frontend/components/experiment-workflow.tsx`
  - `backend/runtime/activation.py`
  - `dispatch/workstreams/development-baseline-consolidation/tasks/T004-mechanical-debris-consolidation.md`
- **Removed symbols:**
  - `frontend/components/experiments/shared.ts:ChartPoint` and
    `strictlyAscending` - repository-wide search found only their local
    declaration; all chart callers use the canonical `chart-support.ts`
    implementation, and `frontend/tests/price_analysis.test.tsx` exercises it
    through the retained `experiment-workflow.tsx` export.
  - `frontend/components/experiments/chart-support.ts:chartTime`, `chartTick`,
    `Json`, and private `DisplayZone` - repository-wide search found no import,
    reference, route, test, API, or generated-surface consumer. Current chart
    owners use `frontend/lib/time.ts` directly; these wrappers did not read or
    write persisted Experiment/evidence data.
  - `frontend/components/experiment-workflow.tsx:WorkflowFeatureBoundaries` -
    repository-wide symbol search found only its declaration. Route callers and
    tests consume the five retained compatibility exports listed by the
    historical decomposition receipt; the null function had no API, generated
    surface, persistence/evidence path, or planned-transition responsibility.
    Its adjacent `PriceAnalysisChart` marker comment was retained because
    `frontend/tests/price_analysis.test.tsx` uses that source marker as a direct
    test contract.
  - `backend/runtime/activation.py:PaperRuntimeService._unsafe_attempt_exists` -
    repository-wide search found only its declaration. The activation path uses
    `_new_session_history_blocker_exists`; the durable repository predicates and
    their safety tests remain. This private forwarder had no API/import,
    persistence/evidence, test-contract, or planned-transition responsibility.
- **Retained symbols and proof:**
  - `frontend/components/experiments/chart-support.ts:ChartPoint` and
    `strictlyAscending` remain canonical. Price, equity, and chart-support
    consumers use them, and the existing timestamp regression test remains
    unchanged.
  - All runtime aliases remain: `PaperRuntimeActivationService`,
    `PaperRuntimeControlService`, `PaperRuntimeReconciliationService`,
    `PaperRuntime`, `PaperRuntimeRunner`, and `PaperRuntimeLoop`. T003 found no
    internal consumers, but `backend/runtime/__init__.py` exposes them through
    `__all__`, lazy exports, and the module import surface; removal would be an
    import-compatibility decision. No alias was deleted.
  - No unused imports or locals were removed from the already touched Python
    files; focused Ruff `F401,F841` checks were clean. StrategyState, state
    codec fields, warm-up compatibility, snapshots/results/indicator modules,
    the EMA adaptor, historical-load fields, and all other T003 seams remain.
- **Checks/evidence:**
  - `uv run --frozen ruff check --select F401,F841 backend/domain/market_data.py backend/domain/strategy.py backend/domain/trading.py backend/strategies/contract.py backend/persistence/database.py backend/execution/contract.py backend/execution/fill_application.py backend/risk/service.py backend/tests/e2e_seed.py backend/tests/experiments/test_configuration.py` - passed before the T004 edit; no touched-file import/local debris was present.
  - Focused pre-change `uv run --frozen pyright backend/runtime/activation.py --outputjson` - exit `0`, Pyright `1.1.411`, `0` errors, `0` warnings, `0` informations; stderr empty.
  - Repository-wide import/reference searches covered each removed symbol,
    route callers, tests, `frontend/lib/api.generated.ts`, backend API imports,
    runtime lazy exports, persistence/evidence paths, and T003's compatibility
    inventory. No removed symbol had an API, generated, persistence, evidence,
    test-contract, or planned-transition responsibility.
  - `npx prettier --check frontend/components/experiment-workflow.tsx frontend/components/experiments/chart-support.ts frontend/components/experiments/shared.ts` - passed.
  - `npx eslint frontend/components/experiment-workflow.tsx frontend/components/experiments/chart-support.ts frontend/components/experiments/shared.ts` - passed.
  - `npm run typecheck:web` - passed.
  - `npm run test:web` - passed.
  - `uv run --frozen ruff check backend/runtime/activation.py` - passed.
  - Focused post-change `uv run --frozen pyright backend/runtime/activation.py --outputjson` - exit `0`, Pyright `1.1.411`, `0` errors, `0` warnings, `0` informations; no new diagnostics versus the pre-change probe.
  - Focused runtime activation tests - passed.
  - `git diff --check` - passed with no whitespace errors.
  - `git diff --no-index --check /dev/null dispatch/workstreams/development-baseline-consolidation/tasks/T004-mechanical-debris-consolidation.md` - passed with no whitespace diagnostics (normal untracked-file diff exit was accepted).
- **Regression coverage:**
  - No new test was required: the removed symbols had no direct test contract;
    the existing canonical `strictlyAscending` test and all existing workflow
    tests remained unchanged and passed.
- **Findings/concerns:**
  - No T004 semantic, compatibility, API, persistence, evidence, trading,
    Strategy, Risk, execution, reconciliation, protection, activation, broker,
    migration, or database-reset changes were made.
  - The inherited repository-wide Pyright baseline remains `3,011` errors as
    recorded in `PYRIGHT.md`; it was not rerun as a cleanup gate.
  - The inherited broad frontend formatting baseline remains the T003-recorded
    non-clean result; only the changed frontend files were checked here.
