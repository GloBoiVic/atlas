# Task 07 — Validation Remediation B1–B3

## Status

**COMPLETE** — the approved narrow remediation is implemented. No material
conflict was found and no backend semantic change was made.

## Changes

- Regenerated `frontend/lib/api.generated.ts` from the current backend OpenAPI
  document using `openapi-typescript` 7.13.0. The regenerated operations now
  match the backend-derived operation IDs, including
  `compare_api_v1_experiments_comparison_get`, and the comparison query schema
  uses `experiment_id`.
- Updated the thin `atlasApi.compareExperiments` wrapper to append repeated
  `experiment_id` values while preserving request order.
- Added `frontend/tests/api_client.test.ts`, covering ordered comparison
  requests with 2, 3, and 4 IDs and asserting that the stale `experimentId`
  key is absent.
- Wrapped `/experiments/compare` in the minimal React `Suspense` boundary
  required by its `useSearchParams` client component.

## Validation receipts

- OpenAPI regeneration from `create_app().openapi()` completed successfully.
- Freshness proof: regenerated a second copy from the same OpenAPI document,
  formatted both outputs with the repository Prettier config, and `diff -u`
  returned no differences.
- `npm run test:web` — **12 passed**.
- Focused comparison/client tests — **3 passed**.
- `npm run lint:web` — **passed**.
- `npm run typecheck:web` — **passed**.
- `ATLAS_API_BASE_URL=http://127.0.0.1:8000 npm run build:web` — **passed**;
  `/experiments/compare` generated successfully as a static route.
- `git diff --check` on remediation files — **passed**.

## Scope receipt

Only B1–B3 were remediated: generated contract freshness, frontend/backend
comparison query alignment, regression coverage for 2–4 IDs, and the required
Suspense boundary. No persistence, backend domain, API semantic, or unrelated
dispatch artifact changes were introduced by this task.
