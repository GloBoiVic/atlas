# VALIDATION - UI 01 Trader Shell and Read-Only Overview

- **Status:** `FAIL`
- **Role:** VALIDATE
- **Workstream:** `ui-01-trader-shell-read-only-overview`
- **Branch:** `solo/ui-01-trader-shell-read-only-overview`
- **Base:** `459e4a298c80b87b28b2875069fd49795ddef478`
- **Artifact:** `dispatch/workstreams/ui-01-trader-shell-read-only-overview/VALIDATION.md`

## Scope

Independent validation of PLAN.md, ACTIVE.md, the T001-T003 receipts, changed
frontend/e2e source, the read-only PAPER safety boundary, and the definition of
done. No application, test, fixture, selector, harness, workflow, backend, or
implementation file was modified by validation.

## Boundary Evidence

- Branch is `solo/ui-01-trader-shell-read-only-overview`; ACTIVE.md reports VALIDATE with no task.
- Tracked implementation changes are limited to `frontend/**` and `tests/e2e/foundation.spec.ts`, plus the expected coordination change in `dispatch/ACTIVE.md`.
- Untracked implementation files are limited to the new frontend pages/components/tests; untracked workstream files are PLAN.md, T001-T003 receipts, and this artifact.
- `git diff --name-only BASE -- backend/runtime backend/paper backend/risk backend/integrations/oanda backend/persistence backend/strategies backend/persistence/migrations` returned no paths.
- The only backend-prefixed worktree item is the pre-existing untracked `backend/.DS_Store`; no backend source, runtime, PAPER, Risk, OANDA, persistence, Strategy, or migration path changed.
- `frontend/lib/api.generated.ts` is a generated OpenAPI expansion. The handwritten client additions are GET-only PAPER/historical methods; no PAPER activation, stop, reconcile, broker, or other mutation method was added or called.
- No `atlas-runtime` command, credentialed operation, PAPER activation, broker mutation, reconciliation, migration, or Dogfood 02/Trade 11 action was run.
- `git diff --check` passed for the tracked diff; changed-source Prettier check passed.

## Checks

- Focused Vitest: passed, 7 files and 21 tests (`home_page`, `app_shell`, `api_status`, `api_client`, `overview`, `paper_status`, `data_overview`).
- Full frontend Vitest: passed, 16 files and 57 tests (`npm run test:web`).
- Changed-file ESLint: passed with 0 errors and no output.
- `npm run lint:web`: passed with 0 errors and 242 warnings, all in pre-existing Experiment workflow files.
- `npm run typecheck:web`: passed.
- `ATLAS_API_BASE_URL=http://127.0.0.1:8000 npm run build:web`: passed; emitted `/`, `/paper`, and `/data` routes.
- `npm run check:web`: blocked at `format:check:web` by five pre-existing files: `frontend/app/providers.tsx`, `frontend/components/ui/select.tsx`, `frontend/lib/time.ts`, `frontend/tests/time.test.ts`, and `tests/e2e/.fixtures.json`. The aggregate did not reach later steps; the individual lint, typecheck, test, and build gates above passed.
- Playwright discovery with alternate non-standard ports passed and listed 2 tests in `foundation.spec.ts`.
- Standard Playwright discovery/execution was blocked before browser launch because `http://127.0.0.1:8000/health/ready` was already occupied by PID 2922. An isolated-port execution retry was not substituted with a database: it failed before browser launch because `ATLAS_E2E_DATABASE_URL` is unset and the API rejected the empty value (`database_url must use postgresql+psycopg`). No E2E database was inferred or substituted.

## Safari Evidence

- Safari Technology Preview MCP independently loaded `/`, `/paper`, and `/data` from the already-running local app. `/` showed the Overview heading and current navigation; `/paper` showed capability, inactive current status, and the evidence boundary; `/data` showed capability, DatasetSnapshots, and inactive load status.
- Actual empty responses were rendered as `PAPER_ACTIVATION_NOT_ACTIVE` and `HISTORICAL_LOAD_NOT_ACTIVE` empty states. No PAPER buttons, mutation links, form controls, or broker controls were present; only navigation links and the timezone select were present.
- A fetch recorder while navigating `/data` to `/paper` observed only GET requests, including `/atlas-api/api/v1/paper/capability` and `/atlas-api/api/v1/paper/activations/active`; no non-GET traffic occurred.
- At viewport `390x844`, Safari showed the nav as `clientWidth: 0`, `scrollWidth: 568`, and the document as `scrollWidth: 610`. A Tab attempt landed on the timezone select rather than the first nav link, consistent with the zero-width/clipped nav. Direct route content remained readable.
- At the same viewport, a DatasetSnapshot fingerprint fact measured about `538.89px` wide against a `390px` viewport. The Data page therefore produced horizontal overflow from an unwrapped 64-character identifier.
- Safari console warnings/errors were empty during these checks.

## Blocking Findings

1. **PRODUCT | DEFECT | blocking:** The responsive shell does not provide usable mobile horizontal navigation. `frontend/components/app-shell.tsx:43-46` renders the primary nav with `overflow-x-auto` but no width/flex constraint; at 390px it computes to zero width and clips the labels, while the document overflows horizontally. Remediation: give the nav a constrained available width such as `min-w-0 flex-1`, adjust the narrow header spacing if required, and verify visible/focusable links without document overflow.
2. **PRODUCT | DEFECT | blocking:** The Data surface is not responsive for returned DatasetSnapshot identifiers. `frontend/components/data-overview.tsx:32-37` and `129-145` render the fingerprint through an unconstrained `Fact`; Safari measured the value at 538.89px on a 390px viewport. Remediation: constrain the fact/grid and wrap long fingerprint/integrity values (`min-w-0` plus an appropriate break/wrap rule), then test the 390px surface.
3. **TOOLING | DEFECT | blocking:** The focused smoke spec asserts the wrong surface after its navigation loop. `tests/e2e/foundation.spec.ts:62-70` ends on `/data`, but `:72-80` then expects PAPER content and safety text, so the test cannot pass as written; the Data assertions follow at `:82-85`. Remediation: perform PAPER assertions immediately after the `/paper` step or navigate back to `/paper`, and keep Data assertions on `/data`; assert the no-mutation boundary on the actual PAPER page.
4. **PRODUCT | DEFECT | blocking:** New read-error retry controls have no visible keyboard focus replacement. `frontend/components/read-resource.tsx:106-110` applies `focus-visible:outline-none` without a focus ring, overriding the shared focus outline for the new Overview/PAPER/Data error states. Remediation: remove the outline suppression or add an explicit visible `focus-visible` ring and cover the retry control in keyboard-focused tests.

No finding is classified as NEW SCOPE. The responsive shell issue uses the existing shell layout pattern, but the approved UI 01 responsive definition of done is still unmet; it is not a request to expand scope.

## Baseline Concerns

- The five format failures and 242 lint warnings above predate the changed UI 01 paths and are separated from the blocking findings.
- The standard local API port occupancy is pre-existing environment state. The missing dedicated E2E database is an environment limitation, not evidence of a passing smoke flow.
- Safari browser checks were read-only observations against the already-running local app/API, not a substitute Playwright E2E database or a capital-capable runtime.

## Completion Receipt

```text
ROLE: VALIDATE
STATUS: FAIL
ARTIFACT: dispatch/workstreams/ui-01-trader-shell-read-only-overview/VALIDATION.md
FILES CHANGED BY VALIDATION: dispatch/workstreams/ui-01-trader-shell-read-only-overview/VALIDATION.md only
CHECKS / EVIDENCE: Focused Vitest 7 files / 21 tests PASS; full Vitest 16 files / 57 tests PASS; lint, typecheck, changed-file Prettier, and build PASS; aggregate check:web blocked only by five baseline format failures; Playwright discovery lists 2 tests; Playwright execution blocked by occupied port and missing dedicated ATLAS_E2E_DATABASE_URL; Safari read-only checks completed with GET-only observed traffic.
FINDINGS / CONCERNS: Four blocking defects: responsive zero-width shell navigation; unwrapped DatasetSnapshot fingerprint overflow; smoke assertions sequenced on the wrong page; and missing visible focus replacement on new read-error retry controls. No backend/runtime/PAPER/Risk/OANDA/persistence/Strategy/migration changes; no mutation or capital-capable behavior was run.
```
