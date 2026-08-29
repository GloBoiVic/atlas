# T003 — Experiment and Inspection Proof

## Assignment

- **Status:** `DONE` — developer-approved narrow remediation for R-004;
  prior validation remediation for F-004 completed; repository-
  wide format gate retains unrelated baseline failures documented in the receipt.
- **Owner:** BUILD
- **Workstream:** `foundation-freeze-06-strategy-extensibility-proof`
- **Branch:** `solo/foundation-freeze-06-strategy-extensibility-proof`
- **Dependencies:** T001 DONE; T002 DONE

Complete the candidate's existing vertical path through configuration,
Experiment creation/execution, persistence, result/Trade inspection, and setup
UI. Use generic persisted metadata and the sole V2 runner; do not encode the
candidate's identity in shared financial or scheduling code.

## Required scope

- Remove remaining EMA-shaped configuration/runner/result assumptions at the
  frozen seams. Configuration and runner must resolve exact provenance and call
  the same Strategy-owned parser; immutable Experiment snapshots retain exact
  canonical values.
- Make result/API schemas and readers pass generic rationale/evidence and
  market/pip requirements through while retaining optional EMA compatibility
  projections and existing response compatibility.
- Prove candidate Experiment creation against native M15 MID and sparse native
  M1 BID/ASK coverage, then execute through the existing V2 clock, immediate
  entry, Risk, Order/Fill, Position/Trade, accounting, and result graph.
- Update setup/result/Trade presentation to render selected persisted parameter
  schema, market requirements, and opaque evidence; EMA-only labels appear only
  when the compatibility projection exists. Do not infer candle methodology in
  the browser.
- Add focused API/integration/UI tests for valid defaults/bounds, invalid input
  before graph creation, immutable snapshots, candidate evidence/stop lineage,
  zero-Trade completion, fail-closed reads, and schema-driven rendering.

## Frozen constraints

Preserve native dataset semantics, no-lookahead, clock, Risk, execution,
accounting, protection, OANDA normalization, and completed-result authority.
No candidate-specific branch in the runner/Risk/execution/market-data/result
interpretation and no database migration/checkpoint persistence.

## Completion receipt

Before returning, update this file with `DONE`, files changed, checks/evidence,
and findings/concerns. Do not edit PLAN, ACTIVE, ARCHITECTURE, VALIDATION, or
REVIEW.

## Current receipt

### Files changed

- Backend generic StrategyVersion configuration, V2 runner, result projection,
  API schemas/routes, OANDA capability metadata, Strategy registration, and the
  `candle_confirmation_break` candidate Strategy.
- Backend focused tests for candidate configuration, runner diagnostics, result
  evidence/stop lineage, and candidate Strategy behavior.
- Experiment setup/results/price-analysis/lineage/Trade UI to render persisted
  parameter schemas, market/pip requirements, opaque evidence, and optional EMA
  compatibility content without browser-side candle inference.
- Frontend focused tests for schema-driven setup and non-EMA result/evidence
  rendering.

### Checks and evidence

- `uv run python -m compileall -q backend/api backend/experiments backend/strategies` — passed.
- `uv run ruff check backend/api/experiments.py backend/api/schemas.py backend/api/strategies.py backend/experiments/results.py backend/tests/experiments/test_price_analysis_results.py` — passed.
- Focused backend suite — **62 passed** in 113.71s:
  `test_price_analysis_results.py`, `test_configuration.py`,
  `test_runner_diagnostics.py`, and `test_candle_confirmation_break.py`.
- Frontend typecheck — passed.
- Focused frontend suite — **17 passed**:
  `strategy_setup.test.tsx`, `experiment_results.test.tsx`, and
  `price_analysis.test.tsx`.
- PostgreSQL-backed integration and result proof, run with the documented URL
  supplied only in the process environment:
  `ATLAS_TEST_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test' uv run pytest backend/tests/integration/test_strategy_persistence.py backend/tests/integration/test_experiment_lifecycle.py backend/tests/integration/test_api_experiments.py backend/tests/integration/test_golden_flows.py backend/tests/experiments/test_price_analysis_results.py -q`
  — **51 passed** in 187.68s.
- Integration-targeted Ruff and `git diff --check` — passed.

### Findings and concerns

- The integration run initially exposed one stale exact-response expectation
  for the newly exposed `pipSize`; the expectation was updated and the rerun
  passed.
- No migrations, checkpoint persistence, or candidate-specific runner/Risk/
  execution/market-data branches were added.
- The integration run emitted four non-failing warnings: one Starlette/httpx
  deprecation warning and three existing unregistered `price_analysis` mark
  warnings.
- The working tree also contains uncommitted T001/T002 work and untracked
  `.codegraph/` and `frontend/.env.local`; these were not altered as part of
  this receipt update.

## Remediation packet — VALIDATE return 1 (F-004)

- **Classification:** `TOOLING`
- **Exact issue:** `npm run format:check:web` fails in changed
  `frontend/components/experiments/experiment-setup.tsx` and
  `frontend/components/experiments/shared.ts` (plus five pre-existing files).
- **Owning task:** `T003-experiment-and-inspection-proof`.
- **Affected files/seams:** the two changed frontend files and the repository
  Prettier gate.
- **Required fix:** Format the two changed files without behavior changes; do not
  rewrite unrelated pre-existing files unless needed to establish the documented
  gate baseline.
- **Invalidated checks:** web format/aggregate quality gate only.
- **Smallest revalidation:** run `npm run format:check:web` and the focused UI
  tests/typecheck.

## Review return 2 disposition — automatic cycling stopped

- **Classification:** `PRODUCT BLOCKER` (acceptance evidence gap)
- **Exact issue:** Candidate PostgreSQL V2 execution and inspection proof exists
  only as an ad-hoc run; no committed integration regression test creates and
  executes a candidate Experiment through native M15 plus sparse M1 and asserts
  the full Risk/Order/Fill/Position/Trade/accounting/result/evidence/stop
  lineage (R-004).
- **Owning task:** `T003-experiment-and-inspection-proof`.
- **Affected files/seams:** candidate integration fixtures/tests under
  `backend/tests/integration` and the existing real V2 runner/persistence/result
  seams; no candidate branch is authorized.
- **Smallest next action after approval:** add one deterministic isolated
  PostgreSQL-backed candidate vertical regression test (plus the smallest
  zero-trade or fail-closed assertion needed by the frozen matrix), then run it
  with the dedicated URL, existing EMA golden flows, result readers, and guards.

## F-004 remediation receipt

### Files changed

- `frontend/components/experiments/experiment-setup.tsx` — formatted with the
  repository Prettier command; no behavior changes.
- `frontend/components/experiments/shared.ts` — formatted with the repository
  Prettier command; no behavior changes.
- This T003 receipt.

### Checks and evidence

- `npx prettier --write frontend/components/experiments/experiment-setup.tsx frontend/components/experiments/shared.ts` — passed.
- Focused changed-file format check — passed:
  `npx prettier --check frontend/components/experiments/experiment-setup.tsx frontend/components/experiments/shared.ts`.
- `npm run typecheck:web` — passed.
- Focused UI suite — **17 passed** across `strategy_setup.test.tsx`,
  `experiment_results.test.tsx`, and `price_analysis.test.tsx`.
- `git diff --check` for both changed files — passed.
- `npm run format:check:web` — still fails only on the following five
  unrelated pre-existing files: `frontend/app/providers.tsx`,
  `frontend/components/ui/select.tsx`, `frontend/lib/time.ts`,
  `frontend/tests/time.test.ts`, and `tests/e2e/.fixtures.json`.

### Findings and concerns

- `DONE_WITH_CONCERNS`: the two T003 changed files are clean under Prettier,
  but the repository-wide formatting gate remains red due to the exact five
  unrelated baseline files listed above.
- No behavior issue was revealed; no unrelated files or role artifacts were
  edited.

## R-004 remediation receipt

### Files changed

- `backend/tests/integration/test_candidate_vertical_flow.py` — added one
  deterministic PostgreSQL-backed candidate V2 regression covering the explicit
  production registration, immutable candidate parameter snapshot, native M15
  analytical membership, sparse native M1 BID/ASK membership, post-frontier
  immediate entry, generic evidence, pip-derived stop, and the persisted
  Risk/Order/Fill/Position/Trade/accounting/result graph through the result
  readers.
- This T003 receipt.

### Checks and evidence

- Dedicated isolated integration module — **1 passed**:
  `ATLAS_TEST_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test' uv run pytest backend/tests/integration/test_candidate_vertical_flow.py -q`
- Directly affected candidate, configuration, result, runner, API, and EMA
  golden-flow tests — **88 passed** in 156.48s:
  `backend/tests/integration/test_candidate_vertical_flow.py backend/tests/integration/test_golden_flows.py backend/tests/integration/test_api_experiments.py backend/tests/strategies/test_candle_confirmation_break.py backend/tests/experiments/test_configuration.py backend/tests/experiments/test_runner_diagnostics.py backend/tests/experiments/test_price_analysis_results.py`
- `uv run ruff check backend/tests/integration/test_candidate_vertical_flow.py` — passed.
- `uv run python -m compileall -q backend/tests/integration/test_candidate_vertical_flow.py` — passed.
- `uv run pyright backend/tests/integration/test_candidate_vertical_flow.py` — passed with 0 errors.
- `git diff --check` for the new test and this receipt — passed.

### Findings and concerns

- The committed test uses `ExperimentConfigurationService`,
  `ExperimentRunService`, the real persisted V2 `ExperimentRunner`, and
  `ExperimentResultReadService`; it does not bypass scheduling, persistence,
  Risk, execution, or result inspection.
- The focused integration run emitted the existing Starlette/httpx deprecation
  warning and three existing unregistered `price_analysis` mark warnings.
- Pre-existing T001/T002 work, `.codegraph/`, and `frontend/.env.local` remain
  untouched and are outside this remediation.
