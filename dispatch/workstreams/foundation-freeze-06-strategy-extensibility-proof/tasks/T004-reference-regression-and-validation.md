# T004 — Reference Regression and Validation Guards

## Assignment

- **Status:** `DONE` — validation remediation for F-006 completed.
- **Owner:** BUILD
- **Workstream:** `foundation-freeze-06-strategy-extensibility-proof`
- **Branch:** `solo/foundation-freeze-06-strategy-extensibility-proof`
- **Dependencies:** T001 DONE; T002 DONE; T003 DONE

Close the implementation with focused regression coverage and source/AST guards
for the frozen boundary. This task proves the original EMA path and shared
financial seams were not changed while the candidate remains genuinely generic.

## Required scope

- Run and, where necessary within the frozen scope, add regression tests for
  EMA parameters, provenance/fingerprint, state and evidence JSON, golden long/
  short/trigger/expiry flows, results/charts, API responses, and frontend
  compatibility.
- Add source/AST guards proving configuration/runner/Risk/execution/market-data/
  snapshot/result interpretation contain no candidate identity branch, no EMA
  parameter construction in generic layers, and no pip conversion in Risk or
  execution.
- Add checks proving no migration, checkpoint table/path/file, or durable
  mid-Experiment state was introduced; ensure forbidden legacy candidate
  `ema_sweep_engulfing` remains inactive.
- Run the repository quality gates relevant to the touched backend/frontend
  code and document exact commands/results in this receipt.

## Frozen constraints

This is evidence and guard work only. Do not broaden architecture, alter the
frozen candidate methodology, or redesign financial semantics. If a genuine
contradiction is discovered, stop and report it instead of reopening the
architecture unilaterally.

## Completion receipt

Before returning, update this file with `DONE`, files changed, checks/evidence,
and findings/concerns. Do not edit PLAN, ACTIVE, ARCHITECTURE, VALIDATION, or
REVIEW.

## Completion receipt

- **Status:** `DONE`
- **Files changed:**
  - `backend/tests/test_foundation_freeze_guards.py`
  - `dispatch/workstreams/foundation-freeze-06-strategy-extensibility-proof/tasks/T004-reference-regression-and-validation.md`
- **Checks/evidence:**
  - Exact EMA source/archive check passed: source bytes match base SHA
    `50c5e18b27d2d652c807f4ca3068ca66cd664687`, raw source SHA-256 is
    `02a285414ec17d514f7d688cc2683eee53ace9e275655c93225f0d9c03621480`,
    and framed archive fingerprint is
    `63e50101f73e64f28e4a0f9f0abb7abe3a3181bbf97b8e8841151de70d442156`.
  - `uv run pytest backend/tests/strategies -q` — **36 passed**.
  - `uv run pytest backend/tests/test_foundation_freeze_guards.py -q` — **5 passed**.
  - `uv run pytest backend/tests/test_foundation_freeze_guards.py backend/tests/experiments/test_results.py backend/tests/experiments/test_price_analysis_results.py -q` — **46 passed**.
  - `ATLAS_TEST_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test' uv run pytest backend/tests/integration/test_golden_flows.py -q` — **2 passed**.
  - `ATLAS_TEST_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test' uv run pytest backend/tests/integration/test_strategy_persistence.py -q` — **3 passed**.
  - `ATLAS_TEST_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test' uv run pytest backend/tests/integration/test_api_experiments.py -q` — **12 passed**, 4 existing warnings.
  - `uv run ruff check backend/tests/test_foundation_freeze_guards.py backend/strategies/production.py backend/tests/strategies/test_legacy_strategy_isolation.py && uv run python -m compileall -q backend/strategies/production.py backend/tests/test_foundation_freeze_guards.py && git diff --check` — passed.
  - `npm run typecheck:web && npm run test:web -- --run tests/strategy_setup.test.tsx tests/experiment_results.test.tsx tests/price_analysis.test.tsx` — **17 passed**.
- **Findings/concerns:**
  - T001 remediation is verified: EMA source provenance is restored and the
    generic behavior is supplied by the explicit production adaptor.
  - Guard coverage confirms no candidate identity branch in shared seams, no
    EMA parameter construction in generic configuration/runner layers, no pip
    conversion in Risk/execution, no migration/checkpoint artifact, and no
    active `ema_sweep_engulfing` registration.
  - API integration emitted the existing Starlette/httpx deprecation warning
    and three existing unregistered `price_analysis` mark warnings. No
    application code or other role artifact was changed by T004.
- The persistence/API combined invocation was not used as a gate because the
  existing persistence module fixture downgrades the shared test schema at
  teardown; isolated reruns of each command passed.

## Remediation packet — VALIDATE return 1 (F-006)

- **Classification:** `TOOLING`
- **Exact issue:** The combined five-target integration invocation exceeded the
  timeout after partial progress; isolated module runs pass, and shared schema
  teardown makes the combined persistence/API invocation unreliable as one gate.
- **Owning task:** `T004-reference-regression-and-validation`.
- **Affected files/seams:** integration fixture/schema lifecycle and the isolated
  module validation commands; no product behavior change is required.
- **Required fix:** Preserve application checks and document isolated module
  commands as the canonical gate (or isolate schema lifecycle only if required,
  without weakening checks).
- **Invalidated checks:** combined invocation only; isolated passing evidence
  remains valid.
- **Smallest revalidation:** rerun the four isolated PostgreSQL modules and the
  result-reader suite with the dedicated test URL.

## F-006 remediation receipt

- **Status:** `DONE`
- **Scope:** TOOLING only. Isolated PostgreSQL module invocations are the
  canonical integration gate; no application behavior, integration fixture, or
  other role artifact was changed.
- **Dedicated URL:**
  `postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test`, supplied inline
  through `ATLAS_TEST_DATABASE_URL` for every invocation below.
- **Checks/evidence:** The commands were run sequentially so each module owned
  its schema lifecycle:
  - `ATLAS_TEST_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test' uv run pytest backend/tests/integration/test_strategy_persistence.py -q` — **3 passed in 3.12s**.
  - `ATLAS_TEST_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test' uv run pytest backend/tests/integration/test_golden_flows.py -q` — **2 passed in 7.44s**.
  - `ATLAS_TEST_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test' uv run pytest backend/tests/integration/test_experiment_lifecycle.py -q` — **5 passed in 14.44s**.
  - `ATLAS_TEST_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test' uv run pytest backend/tests/integration/test_api_experiments.py -q` — **12 passed in 30.08s**, **4 warnings** (existing Starlette/httpx deprecation and three existing unregistered `price_analysis` marks).
  - `ATLAS_TEST_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test' uv run pytest backend/tests/experiments/test_results.py backend/tests/experiments/test_price_analysis_results.py -q` — **41 passed in 121.18s**.
  - `uv run pytest backend/tests/test_foundation_freeze_guards.py -q` — **5 passed in 0.83s**.
  - `git diff --check` — passed with no output.
- **Files changed for this remediation:**
  - `dispatch/workstreams/foundation-freeze-06-strategy-extensibility-proof/tasks/T004-reference-regression-and-validation.md`
- **Findings/concerns:** The combined integration invocation remains invalidated as a gate because shared schema teardown is order-sensitive; the isolated module results above are the accepted F-006 evidence. No new concerns.
