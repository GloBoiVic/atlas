# T005 — Experiment delete API and confirmation UI

## Assignment

- Status: `DONE`
- Role: `BUILD`
- Workstream: `foundation-freeze-07-experiment-lifecycle-local-authority`
- Depends on: `T001`, `T002`, `T003`
- Owns: destructive API contract, structured client errors, and one detail-page workflow

## Frozen requirements

Implement `ARCHITECTURE.md` §§5–6 using the completed lifecycle service. Add only
`DELETE /api/v1/experiments/{experiment_id}` with strict confirmation payload:
exact case-sensitive `DELETE` plus exact human-fact projection including locked
status, strategy, instrument/provider, native analysis, and canonical UTC period.
Return the frozen 200 JSON success body with `snapshot.deleted`; preserve the
existing error envelope and all specified 404/409/422/403/500 codes and mutation
guarantees. Do not expose raw SQL/errors or tombstones, and do not retry unknown
delete outcomes.

Add one explicit detail/status-surface workflow only: status-aware delete control,
real confirmation dialog, human-readable facts, permanent/retention explanation,
exact DELETE field, pending disable/double-submit prevention, navigation/refetch on
success/not-found, persistent conflict/error handling, and structured `ApiError`
code handling. Hide or disable deletion for RUNNING. Do not add bulk delete,
generic resource deletion, UUID entry, or alter surviving completed-result polling
or rendering.

## Required proof

Test strict request/response/error contracts, locked-status mismatch and RUNNING
precedence, repeated delete, orphan/shared response flags, no-retry behavior,
dialog states, exact confirmation enablement, double-submit prevention,
navigation/refetch, and structured errors. Use the project's browser validation
when available for the affected workflow.

## Completion receipt

- Status: `DONE`
- Application paths:
  - `backend/api/app.py`
  - `backend/api/experiments.py`
  - `backend/api/schemas.py`
  - `frontend/components/experiments/experiment-status.tsx`
  - `frontend/lib/api-client.ts`
  - `frontend/lib/api.generated.ts`
- Test paths:
  - `backend/tests/integration/test_experiment_deletion.py`
  - `frontend/tests/experiment_delete.test.tsx`
- Migration/config paths: none.
- Implementation evidence:
  - Added the single `DELETE /api/v1/experiments/{experiment_id}` endpoint using
    the completed ExperimentDeletionService boundary and caller-owned transaction.
    It locks and projects persisted human facts, gives locked `RUNNING` precedence,
    enforces exact `DELETE` plus exact status/identity/period facts, returns the
    frozen 200 response with `snapshot.deleted`, and maps stable deletion errors
    without exposing database diagnostics or retrying.
  - Added strict request/response schemas and regenerated the typed OpenAPI client;
    the client preserves structured `ApiError` codes and sends exactly one DELETE.
  - Added one native detail-page confirmation dialog for PENDING, FAILED, and
    COMPLETED Experiments. It shows human-readable facts and retention semantics,
    disables confirmation until exact `DELETE`, prevents double submit, hides the
    control for RUNNING, navigates/refetches after success or not-found, refreshes
    stale conflict state, and keeps unknown failures in the dialog without retry.
  - Added API integration coverage for one-time deletion/repeat 404, RUNNING
    precedence, case-sensitive confirmation, and stale deletable status; added
    focused UI coverage for facts, exact confirmation, pending/double-submit,
    RUNNING visibility, conflict refetch, navigation, and unknown outcomes.
  - Normalized FastAPI-raised structured errors to the root Atlas envelope so
    delete responses are not nested under `detail`.
- Checks / evidence:
  - `ATLAS_TEST_DATABASE_URL=postgresql+psycopg://vike@localhost:5432/atlas_freeze07_test uv run pytest -q backend/tests/integration/test_experiment_deletion.py` — 7 passed.
  - `ATLAS_TEST_DATABASE_URL=postgresql+psycopg://vike@localhost:5432/atlas_freeze07_test uv run pytest -q backend/tests/integration/test_api_experiments.py` — 12 passed.
  - `bun node_modules/.bin/vitest run --config frontend/vitest.config.ts frontend/tests/experiment_delete.test.tsx frontend/tests/api_client.test.ts` — 5 passed.
  - `bun node_modules/.bin/tsc --project frontend/tsconfig.json --noEmit` — passed.
  - Targeted ESLint and Prettier checks — passed.
- Targeted Ruff and Python compilation — passed.
- OpenAPI regeneration from `create_app().openapi()` with openapi-typescript
  7.13.0/Prettier and exact diff — passed.
- `git diff --check` — passed.
- Remediation: added `name="delete-confirmation"` and replaced the non-modal
  `<dialog open>` with an accessible modal surface using `aria-modal`, an inert
  and hidden background, focus-on-open, focus containment, and Escape/cancel
  behavior. Added focused assertions for the name, modal semantics, background
  inertness, focus trap, Escape/cancel, exact phrase enablement, and one-submit
  behavior.
- Remediation checks: `bun node_modules/.bin/vitest run --config
  frontend/vitest.config.ts frontend/tests/experiment_delete.test.tsx` — 5
  passed; targeted TypeScript and ESLint — passed; `git diff --check` — passed.
- Remediation Local Host workflow on `http://localhost:3200/experiments/6293aa22-dc45-4e9e-b5d0-b3662c537cf8` — opened the detail dialog, verified the
  labelled input had `name="delete-confirmation"` and received focus, verified
  the accessibility snapshot exposed only the modal, typed exact `DELETE`, and
  cancelled with focus restored to the trigger; console errors — none.
- Approved R-003/R-004 remediation: moved unknown/failed deletion `ErrorPanel`
  rendering into the active confirmation dialog, outside the inert and
  `aria-hidden` detail page content. The typed `DELETE` value remains intact,
  the dialog stays open, and no retry control or automatic second request is
  introduced. Added visible/accessible focused assertions for
  `EXPERIMENT_DELETE_FAILED`, `LOCAL_PEER_REQUIRED`, unavailable, and transport
  timeout failures. Added one PostgreSQL API read-equivalence proof covering a
  surviving completed Experiment's detail/metrics, equity, trades/trade,
  price-analysis, and comparison responses before and after another completed
  Experiment is deleted.
- Remediation checks: focused Vitest deletion suite (`9 passed`), targeted
  frontend TypeScript/ESLint/Prettier, and the dedicated PostgreSQL deletion
  integration suite (`37 passed`, including the surviving-read test) — all
  passed; `git diff --check` passed.
- Final remediation status: `DONE`.
- Final Local Host evidence on `http://localhost:3200/experiments/6293aa22-dc45-4e9e-b5d0-b3662c537cf8`:
  stopped the local API after opening the real dialog and typing exact `DELETE`,
  submitted once, and observed the persistent failure inside the active dialog
  (`Request needs attention`, `Atlas API returned 500`, `Code: HTTP_500`) with
  no navigation; the page readback retained `DELETE`, and console diagnostics
  reported no errors. The API was restarted afterward.
- Concerns:
  - The full frontend Vitest run reports 19 failures from pre-existing
    decomposed-component test mocks that omit `next/navigation.usePathname`; the
    focused T005 tests pass, and those unrelated test files were not changed.
  - Browser tooling does not provide a keyboard-key action, so Escape remains
    covered by the focused unit test; no PAPER or pre-PAPER work was started.

Do not edit `PLAN.md`, `ARCHITECTURE.md`, `ACTIVE.md`, or another task artifact.

## Approved review remediation — R-003 and R-004

- R-003: render unknown/failed deletion errors inside the active confirmation
  dialog, not inert/aria-hidden page content; preserve typed `DELETE` and no
  auto-retry. Add visible/accessible assertions for `EXPERIMENT_DELETE_FAILED`,
  `LOCAL_PEER_REQUIRED`, and transport/unavailable failures.
- R-004 portion owned here: add minimum proof for surviving completed-Experiment
  read equivalence and API/UI failure-path behavior, without redesigning the
  validation harness or broadening product scope.

Preserve all frozen API/UI semantics, use the dedicated local checks, and do not
edit role artifacts or other task artifacts. Update this receipt with paths,
checks, and final status.
