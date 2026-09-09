# VALIDATION - R001 UI 01 Responsive, Safety, and Smoke Remediation

- **Status:** `PASS`
- **Role:** VALIDATE
- **Workstream:** `ui-01-trader-shell-read-only-overview`
- **Branch:** `solo/ui-01-trader-shell-read-only-overview`
- **Remediation:** `R001-ui-01-responsive-safety-smoke`
- **Owner:** fresh `solo-flow-worker`

## Scope

Independent validation of the four findings in the immutable root `VALIDATION.md`,
the frozen `PLAN.md`, the R001 `BUILD.md`, the R001 changed source, and the
read-only PAPER boundary. Validation changed only this artifact.

## Acceptance

- **PASS:** At 390px, Safari Technology Preview measured the primary navigation at
  `342px` usable width with `568px` to `570px` scroll content. Its five links all
  reported `tabIndex: 0`, and direct keyboard-target focus on `Overview` succeeded.
  On `/`, `/paper`, and `/data`, `document` and `body` widths were exactly `390px`
  with no document-level horizontal overflow. The `overflow-x-auto`, `min-w-0`,
  `flex-1`, and `contain-paint` classes are present at
  `frontend/components/app-shell.tsx:42-45`.
- **PASS:** The Data `Fact` constrains its value with `min-w-0` and `break-all` at
  `frontend/components/data-overview.tsx:32-37`; integrity values use a
  constrained parent and `break-all` at `:146-154`. The focused test uses long
  fingerprint and integrity values at
  `frontend/tests/data_overview.test.tsx:20-30` and asserts the wrapping classes at
  `:58-59`. Safari measured each live `/data` fingerprint at `300px` wide and
  `40px` high inside the `390px` viewport, with no document/body overflow.
- **PASS:** `foundation.spec.ts` performs PAPER assertions immediately after the
  `/paper` navigation at `tests/e2e/foundation.spec.ts:70-79`, including inactive
  status and evidence-boundary facts, and performs Data assertions after the
  `/data` navigation at `:81-85`. The route-level no-mutation guard is installed at
  `:6-17` and PAPER controls are checked at `:41-44`.
- **PASS:** `ReadError` Retry has an explicit visible focus replacement at
  `frontend/components/read-resource.tsx:106-110`:
  `focus-visible:ring-2 focus-visible:ring-atlas-focus-ring focus-visible:ring-offset-2`.
  The focused Data error test asserts those classes and focus at
  `frontend/tests/data_overview.test.tsx:118-124`.

## Boundary Evidence

- `git diff --name-only BASE --` for the frozen backend/trading paths returned no
  paths. The only backend worktree item is the pre-existing untracked
  `backend/.DS_Store`; no backend source, runtime, PAPER, Risk, OANDA, persistence,
  Strategy, or migration path changed.
- R001 changed source is limited to the shell, Data rendering, Retry rendering,
  focused frontend tests, and `tests/e2e/foundation.spec.ts`. Those R001 files add
  or change no POST, PUT, PATCH, DELETE, activation, stop, reconcile, broker, or
  capital-capable request. Existing mutation methods in the earlier workstream
  `frontend/lib/api-client.ts` were not part of R001 and were not invoked by the
  PAPER checks.
- Safari fetch recording during a 390px Data-to-PAPER transition observed only
  GETs: the Next route RSC request, `/atlas-api/health/ready`,
  `/atlas-api/api/v1/paper/capability`, and
  `/atlas-api/api/v1/paper/activations/active`. No non-GET request occurred.
- Safari `/paper` showed capability facts, the expected
  `PAPER_ACTIVATION_NOT_ACTIVE` empty state, and the evidence boundary. It exposed
  no buttons or mutation controls at desktop or 390px.
- No runtime command, credentialed operation, PAPER activation, broker mutation,
  reconciliation, migration, Dogfood 02, or Trade 11 action was run.

## Checks

- Focused Vitest: passed, 5 files and 15 tests (`home_page`, `app_shell`,
  `data_overview`, `overview`, `paper_status`).
- Full frontend Vitest: passed, 16 files and 57 tests.
- Changed-file Prettier: passed for all six R001 implementation/test files.
- Changed-file ESLint: passed with 0 errors and no output.
- Full frontend lint: passed with 0 errors and 242 warnings, all in pre-existing
  Experiment workflow files.
- Frontend typecheck: passed.
- Production build: passed with
  `ATLAS_API_BASE_URL=http://127.0.0.1:8000`; emitted `/`, `/paper`, and `/data`.
- `git diff --check`: passed for the tracked worktree diff and the R001 changed
  files.
- `npm run check:web`: blocked at `format:check:web` by five baseline files only:
  `frontend/app/providers.tsx`, `frontend/components/ui/select.tsx`,
  `frontend/lib/time.ts`, `frontend/tests/time.test.ts`, and
  `tests/e2e/.fixtures.json`. Individual lint, typecheck, test, build, and
  changed-file format gates passed.
- Playwright discovery: passed; `npx playwright test tests/e2e/foundation.spec.ts
--list` listed 2 tests.
- Playwright execution: blocked before a safe execution attempt because
  `ATLAS_E2E_DATABASE_URL` is unset and `127.0.0.1:8000` is already occupied by
  PID `2922`. No shared or non-dedicated database was substituted. The standard
  isolated E2E execution therefore remains an environmental limitation, not a
  remediation result.

## Safari Evidence

- Desktop `1440px`: `/`, `/paper`, and `/data` loaded their expected headings and
  facts. `/paper` and `/data` had document/body width `1440px`; the primary nav
  measured `1016px` wide without overflow.
- `390px`: `/`, `/paper`, and `/data` loaded readable route content. `/` measured
  nav `342px`/`570px` (client/scroll width), `/paper` measured `342px`/`568px`,
  and `/data` measured `342px`/`568px`; all document/body widths were `390px`.
- Direct focus proved the nav links are focusable. Safari's local keyboard
  navigation setting sent a literal Tab from the wordmark to the timezone select
  instead of traversing links; this is a browser-environment limitation. The
  Playwright keyboard assertions remain present but could not execute without the
  dedicated E2E environment.
- An induced read-error state rendered a `Retry` button on `/data`; its production
  class includes the explicit focus ring. Safari's programmatic focus does not
  enter `:focus-visible`, so runtime pseudo-class rendering was supplemented by
  the source assertion and focused regression test above.
- Safari console output contained only local development HMR suspension and
  expected local resource/empty-status 404 noise; no remediation-specific runtime
  exception was observed.

## Findings

No unresolved `CRITICAL` or `IMPORTANT` approved-scope finding remains. No
remaining approved-scope defect requires classification as `PRODUCT`,
`REGRESSION`, or `TOOLING`, and nothing is `NEW SCOPE`. The baseline formatter
failures, existing lint warnings, unavailable dedicated E2E database, occupied
API port, and Safari keyboard-mode limitation are recorded as environmental or
pre-existing concerns only.

## Completion Receipt

```text
ROLE: VALIDATE
STATUS: PASS
ARTIFACT: dispatch/workstreams/ui-01-trader-shell-read-only-overview/remediations/R001-ui-01-responsive-safety-smoke/VALIDATION.md
FILES CHANGED BY VALIDATION: dispatch/workstreams/ui-01-trader-shell-read-only-overview/remediations/R001-ui-01-responsive-safety-smoke/VALIDATION.md only
CHECKS / EVIDENCE: Focused Vitest 5 files / 15 tests PASS; full frontend Vitest 16 files / 57 tests PASS; changed-file format, lint, typecheck, build, and git diff --check PASS; full lint PASS with 242 pre-existing warnings; aggregate check:web blocked only by five baseline format failures; Playwright discovery lists 2 foundation tests; Playwright execution blocked by unset dedicated ATLAS_E2E_DATABASE_URL and occupied 127.0.0.1:8000 without database substitution; Safari desktop and 390px checks PASS with no document overflow, wrapped snapshot values, no PAPER controls, and GET-only PAPER reads.
FINDINGS / CONCERNS: No unresolved approved-scope defect. Baseline formatting/lint warnings, unavailable dedicated E2E environment, occupied API port, and Safari keyboard-mode limitation are environmental or pre-existing concerns; no frozen backend/trading path or mutation behavior changed.
```
