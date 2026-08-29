# T001 — Read Projections and Navigation

- **Status:** `DONE`
- **Role:** BUILD
- **Workstream:** `foundation-freeze-05-trader-product-ui-completion`
- **Branch:** `solo/foundation-freeze-05-trader-product-ui-completion`
- **Owner:** fresh `solo-flow-worker`

## Approved remediation packet

- **Classification:** PRODUCT BLOCKER
- **Finding:** The optimized Experiment list can pass projected result/metric
  facts through for non-`COMPLETED` statuses, bypassing the existing fail-closed
  result contract.
- **Required fix:** Only `COMPLETED` Experiments may receive projected
  result/metric facts. Preserve the bounded completed-row query improvement and
  add a regression for a non-completed Experiment with a persisted result row.
- **Affected seam:** `backend/api/experiments.py` list projection and its focused
  API/integration regression.
- **Invalidated evidence:** Only the affected list result-gating,
  response-equivalence, and query-bound evidence require targeted revalidation;
  unrelated validation evidence remains preserved.
- **Scope limit:** No broader API, persistence, financial, UI, or semantic
  changes; do not create a new task.

## Objective

Add only the smallest bounded batch/projected read path needed to remove
avoidable per-row metadata composition from Strategy and Experiment list screens.
Preserve the existing authoritative response facts and OpenAPI meaning. Consume
the existing Experiment `nextCursor` where useful, and establish shared helpers
for human-readable identity, status, period, and canonical headline metrics.

## Constraints

- No new read model, cache, persistence layer, pagination redesign, or financial
  semantics.
- Do not recompute metrics in the client or introduce fake labels/fallback facts.
- Preserve raw IDs for links/reconciliation but do not use them as normal labels.
- Keep completed-only comparison eligibility and all canonical metric states.
- Follow the relevant API and frontend conventions and inspect CodeGraph before
  changing indexed symbols.

## Dependencies

- None. T002 and later tasks may consume the helpers/payload path created here.

## Required checks

- Focused backend/API response-equivalence and query-shape regression evidence.
- Focused frontend tests for identity/status/metric presentation and cursor use.
- Relevant type/lint/test checks for changed packages.

## Completion receipt

```text
ROLE: BUILD
STATUS: DONE
ARTIFACT: dispatch/workstreams/foundation-freeze-05-trader-product-ui-completion/tasks/T001-read-projections-and-navigation.md
FILES CHANGED: Remediation touched backend/api/experiments.py and backend/tests/integration/test_api_experiments.py. Prior T001 implementation files remain: backend/api/strategies.py; backend/experiments/results.py; backend/persistence/result_repository.py; backend/persistence/strategy_repository.py; frontend/components/experiments/experiment-list.tsx; frontend/components/experiments/shared.ts; frontend/tests/experiment_list.test.tsx; frontend/tests/experiment_formatters.test.ts.
CHECKS / EVIDENCE: `ATLAS_TEST_DATABASE_URL=postgresql+psycopg://... pytest -q backend/tests/integration/test_api_experiments.py -k 'completed_experiment_list or non_completed_experiment_list'` passed (2 tests, 10 deselected), covering completed response-equivalence, the 3-SELECT bounded list query, and a persisted-result non-COMPLETED regression asserting result/metric payloads are absent. `ruff check backend/api/experiments.py backend/tests/integration/test_api_experiments.py`, targeted Python compileall, and targeted `git diff --check` passed. Existing bounded projection and nextCursor behavior preserved; full validation matrix intentionally not rerun.
FINDINGS / CONCERNS: Pytest emitted existing Starlette deprecation and unregistered `price_analysis` mark warnings only. No new concerns from the final remediation.
```
