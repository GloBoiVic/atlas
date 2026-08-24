# Atlas Phase 6 — Strategy Iteration: Validation

## Control

- **Workstream:** Atlas Phase 6 — Strategy Iteration
- **Root:** `/Users/vike/Desktop/atlas`
- **Branch:** `feature/phase-6-strategy-iteration`
- **Base SHA (validated against):** `f009be5fbe7cee7387ccda7cf3460833525ff303`
- **Owner:** Tester
- **Artifact:** this `VALIDATION.md`
- **Date:** 2026-08-23 (resumed after provider cancellation, per authorization)

## Scope and method

Ran the ARCHITECTURE §343–368 validation matrix. Reused valid task receipts where
covered, reran targeted backend/frontend suites, exercised the new HTTP routes
against the migrated dedicated `atlas_test` database, verified v1 byte-identity and
fingerprints, verified OpenAPI contract freshness by regenerating the client, and
ran the production frontend build (completion gate).

## Environment notes (not code changes)

PostgreSQL was not running. Started the local Postgres.app cluster. The
`atlas_test` database's `public` schema and its stale tables were owned by role
`vike`, which blocked the `atlas` role's migration/inserts ("no schema has been
selected to create in" / "permission denied"). Transferred ownership of the
`atlas_test` `public` schema and all tables to role `atlas` so the documented
test convention (`ATLAS_TEST_DATABASE_URL=...atlas_test`) could run. This is
environment provisioning, not an application change. No production database was
touched.

## Reusable receipts (PASS)

Reused from task reports and confirmed by reruns where noted:

| Receipt | Result | Source |
| --- | --- | --- |
| v1 source byte-identical | `git diff HEAD -- backend/strategies/ema_sweep_engulfing.py backend/strategies/indicators.py` empty | rerun |
| v1 fingerprint `20c2bf0f1d0b…` / v2 `56b236e6dc60…` | registry `catalog()` shows v1 then v2, matching Task 01 | rerun |
| v2 schema/bounds/indicator tests | 26 passed | Task 01 |
| Registry provenance / v1+v2 focused | 35 passed | Task 02 |
| Strategy persistence integration | 3 passed | Task 02 |
| API health (test-config repair) | 4 passed | Task 02 + rerun |
| Strategy catalog/history + domain | 93 passed | Task 03 |
| Configuration options | 3 passed | Task 04 |
| Comparison service/API | 5 passed | Task 05 + rerun |
| Experiment result/metric | 35 passed | Task 05 |
| Ruff / compileall | passed on changed backend | Tasks 01–06 |
| Frontend lint `npm run lint:web` | passed | Task 06 + rerun |
| Frontend typecheck `npm run typecheck:web` | passed | Task 06 + rerun |
| Frontend focused tests (comparison, list, results) | 7 passed | Task 06 |

## Final reruns performed this validation

| Suite | Command | Result |
| --- | --- | --- |
| Backend unit (strategies+domain+experiments) | `uv run pytest backend/tests/strategies backend/tests/domain backend/tests/experiments -q` | **128 passed** |
| API health | `uv run pytest backend/tests/test_api_health.py -q` | **4 passed** |
| Integration (migrated `atlas_test`) | `uv run pytest backend/tests/integration -q` | **38 passed** |
| Other unit (market_data/risk/execution/config/migration_revision/runtime) | `uv run pytest ...` | **45 passed** |
| Full non-integration backend | `uv run pytest backend/tests -m "not integration and not external"` | **195 passed, 40 deselected** |
| Frontend unit | `npm run test:web` | **11 passed** |
| Strategy routes functional | `GET /api/v1/strategies` → 200; `GET /api/v1/strategies/ema_sweep_engulfing` → 200 (`EMA Sweep Engulfing v2`) | PASS |

## Blockers (terminal for Phase 6 acceptance)

### B1 — Generated OpenAPI client is stale vs current backend (contract-freshness gate)

Regenerating the client from the current backend OpenAPI does **not** reproduce the
committed `frontend/lib/api.generated.ts`. The committed file names operations
`comparison_api_v1_experiments_comparison_get`, `list_strategies_api_v1_strategies_get`,
`get_strategy_api_v1_strategies__strategy_key__get`, but the current backend
operationIds are `compare_api_v1_experiments_comparison_get`,
`listing_api_v1_strategies_get`, and `detail_api_v1_strategies__strategy_key__get`
(FastAPI derives them from the route functions `compare`, `listing`, `detail`).

Evidence:
- `diff frontend/lib/api.generated.ts <(openapi-typescript /tmp/atlas_openapi.json)` is non-empty and operation keys differ.
- Backend route names confirmed: `backend/api/experiments.py:392 def compare`, `backend/api/strategies.py:83 def listing`, `:109 def detail`.
- `GET /api/v1/experiments/comparison?experiment_id=…` reaches the service (returns `COMPARISON_SELECTION_INVALID` for 1 id → correct bound behavior).

Violates: ARCHITECTURE §329 "API drift: generated OpenAPI freshness is a completion
gate", validation matrix row "Contract freshness → Generated client is current and
byte-stable", acceptance criterion 11, and PLAN scope ("Regenerate the OpenAPI
client … a completion gate").

### B2 — Comparison feature is broken at runtime (query-param name mismatch)

The frontend `atlasApi.compareExperiments` sends `experimentId` as the query key
(`frontend/lib/api-client.ts:72-75`), but the backend `compare` route declares
`experiment_id: list[UUID] = Query(...)` (`backend/api/experiments.py:392-393`).
Every comparison request therefore returns **422 `VALIDATION_ERROR`** ("Field
required … experiment_id"). The committed stale client also declares
`experimentId` (`api.generated.ts`), so typecheck passes while the runtime call
always fails.

Evidence:
- `GET /api/v1/experiments/comparison?experimentId=<uuid>` → 422 field `experiment_id` missing.
- `GET /api/v1/experiments/comparison?experiment_id=<uuid>` → passes param validation (reaches bound check).

Violates acceptance criterion 6 ("select two to four COMPLETED Experiments and see
configuration differences before canonical metrics") and the comparison
API contract (§260).

### B3 — Production frontend build fails on `/experiments/compare` (regression)

`npm run build:web` exits with:
`⨯ useSearchParams() should be wrapped in a suspense boundary at page "/experiments/compare"`.

The new `/experiments/compare` route (`frontend/app/experiments/compare/page.tsx` →
`ExperimentComparisonPage`) is a static route using `useSearchParams` without a
Suspense boundary. It is untracked/new in Phase 6. This blocks the build/completion
gate and is a Phase 6 regression (no other page fails prerender; the dynamic
`[experimentId]`/`[strategyKey]` routes are unaffected).

## Non-blocking observations

- `npm run format:check:web` fails only on pre-existing `tests/e2e/.fixtures.json`
  drift; not modified by this workstream (matches Task 06 report).
- Backend unit/integration, v1 identity/fingerprint, v2 registration, strategy
  history reads, health, and frontend lint/typecheck/tests all pass.

## Verification-matrix coverage

Rows verified PASS by receipts/reruns: v1 provenance, registry, catalog sync,
v2 schema, version semantics, methodology change, indicators, strategy behavior,
warm-up, stop/target, experiment create, history API/UI reads, regression.
Rows FAILED: comparison selection (runtime — B2), contract freshness (B1),
UI/regression build (B3).

## Verdict

**NOT READY for R1 review.** Backend domain/persistence and strategy-version work
are verified; the comparison API contract, generated-client freshness, and the
production build have three concrete, reproducible failures (B1–B3). These must be
resolved (client regeneration + `experiment_id` query key + Suspense boundary on
`/experiments/compare`) and revalidated before dispatch proceeds to review.
