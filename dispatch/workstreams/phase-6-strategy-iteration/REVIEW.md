# Phase 6 — Strategy Iteration: R1 Review

## Control

- **Reviewer:** reviewer-premium
- **Scope:** fresh R1 review of approved I1/M1 remediation (Task 08): public comparison query contract, generated-client freshness, HTTP integration evidence, regressions, and scope.
- **Result:** **PASS — ready for dispatch closure.**

## Task 08 receipt verification

| Area | Independent evidence | Result |
| --- | --- | --- |
| Public HTTP contract (I1) | `backend/api/experiments.py:391-410` binds `experiment_id` with `alias="experimentId"` and passes the ordered list directly to the comparison service. Fresh OpenAPI inspection asserted the operation ID and its sole required query parameter: `experimentId: array[uuid]`. | **PASS** |
| Client and wrapper alignment | `frontend/lib/api.generated.ts:803-811` declares `compare_api_v1_experiments_comparison_get` with `experimentId: string[]`; `frontend/lib/api-client.ts:71-76` appends repeated `experimentId` values in caller order. | **PASS** |
| Generated-client freshness | Regenerated from `create_app().openapi()` using local `openapi-typescript`, formatted with Prettier using `frontend/lib/api.generated.ts` as the stdin filepath, and exact-diffed against the committed generated client. | **PASS** — no diff. |
| HTTP integration evidence (M1) | `backend/tests/integration/test_api_experiments.py:196-295` persists and completes two Experiments, calls the actual `TestClient` route with repeated `experimentId` values in reverse order, asserts returned order and all eight canonical metric envelopes, rejects `experiment_id`, and asserts experiment/result/equity row counts are unchanged. This directly covers the previously missing success path. | **PASS by inspection and Task 08 receipt.** |
| Frontend regression gates | Ran `npm run test:web`, `npm run lint:web`, `npm run typecheck:web`, and `ATLAS_API_BASE_URL=http://127.0.0.1:8000 npm run build:web`. | **PASS** — 12 tests passed; lint/typecheck passed; `/experiments/compare` builds and prerenders. |
| Backend regression gates | Ran `uv run pytest backend/tests -m 'not integration and not external' -q`. | **PASS** — 191 passed, 4 skipped, 41 deselected, one existing Starlette warning. |
| Targeted quality/scope checks | Ran Ruff check and format check on the route and HTTP test, plus `git diff --check`. Compared changed tracked paths with the approved Phase 6 workstream scope. | **PASS** — no style or whitespace errors; changed paths are Phase 6 strategy/catalog/history/comparison/UI work and its tests, with no unrelated product-area change. |

## Findings

### Critical

- None.

### Important

- None.

### Minor

- None.

## Coverage limitation

The review shell did not export `ATLAS_TEST_DATABASE_URL`. Consequently, a fresh run of `uv run pytest backend/tests -m 'not external' -q` executed 191 tests but reported 12 integration setup errors solely because the required dedicated test-database URL was absent. It did not expose an application-test failure. Task 08 records the required explicit-URL run as **235 passed, 1 deselected** and the inspected HTTP test provides direct durable-database coverage. Re-run that command with the dedicated test URL if an environment-level reproduction is required; no code disposition is indicated.

## Counts and terminal verdict

| Category | Critical | Important | Minor |
| --- | ---: | ---: | ---: |
| Security / trading safety | 0 | 0 | 0 |
| Architecture / API correctness | 0 | 0 | 0 |
| **Total** | **0** | **0** | **0** |

**Terminal verdict: PASS.** I1 is resolved by the exact approved repeated `experimentId` contract, and M1 is resolved by migrated-database HTTP success-path coverage. Generated client, wrapper, frontend build, focused backend regression, and scope checks are consistent with the approved remediation. The developer owns all fix decisions.
