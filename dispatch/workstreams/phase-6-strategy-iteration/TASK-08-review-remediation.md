# Task 08 — Review Remediation I1/M1

## Status

**COMPLETE** — restored the approved public comparison query contract and added
migrated-database HTTP integration coverage. No material conflict was found.

## Changes

- Restored `GET /api/v1/experiments/comparison` to accept exactly repeated
  `experimentId` query values in request order. The prior snake-case key is not
  accepted as a compatibility contract.
- Regenerated `frontend/lib/api.generated.ts` from the current FastAPI OpenAPI
  document with `openapi-typescript` 7.13.0 and Prettier 3.9.6; the generated
  query schema now declares `experimentId`.
- Updated the handwritten `atlasApi.compareExperiments` wrapper and its focused
  contract test to send repeated `experimentId` values and preserve ordering.
- Added a migrated-PostgreSQL direct `TestClient` integration test covering two
  persisted COMPLETED Experiments, request ordering, the complete canonical
  metric envelope set, rejection of the old key, and unchanged row counts after
  the read.

## Validation receipts

- `ATLAS_TEST_DATABASE_URL=<dedicated local atlas_test URL> uv run pytest backend/tests/integration/test_api_experiments.py -q` — **5 passed**, 1 existing Starlette warning.
- `ATLAS_TEST_DATABASE_URL=<dedicated local atlas_test URL> uv run pytest backend/tests/integration/test_api_experiments.py::test_http_comparison_uses_public_repeated_ids_and_is_read_only backend/tests/experiments/test_comparison.py -q` — **6 passed**, 1 existing Starlette warning.
- `ATLAS_TEST_DATABASE_URL=<dedicated local atlas_test URL> uv run pytest backend/tests -m 'not external' -q` — **235 passed, 1 deselected**, 1 existing warning.
- `npm run test:web` — **12 passed**.
- `npm run lint:web` — **passed**.
- `npm run typecheck:web` — **passed**.
- `ATLAS_API_BASE_URL=http://127.0.0.1:8000 npm run build:web` — **passed**; `/experiments/compare` generated successfully.
- OpenAPI freshness: regenerated a second client from `create_app().openapi()` with `openapi-typescript` 7.13.0, formatted with Prettier 3.9.6, and `diff -u frontend/lib/api.generated.ts /tmp/atlas_api_generated_fresh.ts` returned no differences. Temporary files were removed.
- `uv run ruff check backend/api/experiments.py backend/tests/integration/test_api_experiments.py`, format check, and `git diff --check` — **passed**.

## Scope receipt

Only review findings I1/M1 were remediated: the exact public repeated
`experimentId` contract, generated-client freshness, thin-wrapper alignment, and
successful migrated-database HTTP coverage. No schema, persistence, domain,
metric, execution, PAPER/LIVE, or unrelated dispatch artifact changes were
introduced.
