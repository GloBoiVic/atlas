# R001 - UI 01 Responsive, Safety, and Smoke Remediation

- **Remediation ID:** `R001`
- **Status:** `DONE_WITH_CONCERNS`
- **Role:** BUILD
- **Workstream:** `ui-01-trader-shell-read-only-overview`
- **Branch:** `solo/ui-01-trader-shell-read-only-overview`
- **Origin finding:** Four blocking findings in `dispatch/workstreams/ui-01-trader-shell-read-only-overview/VALIDATION.md`, findings 1-4
- **Finding severity:** `PRODUCT` / `TOOLING`, all blocking approved-scope defects
- **Related original task(s):** T001, T002, T003

## Approved requirement or invariant violated

The approved UI 01 plan requires a responsive shell with usable mobile horizontal
navigation and preserved keyboard focus behavior; responsive Data rendering with
returned DatasetSnapshot facts; a passing focused smoke flow covering `/`,
`/paper`, and `/data` plus the PAPER no-mutation boundary; and visible focus
behavior for interactive read-only error/retry states. The current implementation
does not satisfy those requirements at narrow viewport or in the smoke spec.

## Exact remediation outcome

- Constrain the primary navigation to the available header width so it remains
  horizontally usable at 390px without document-level horizontal overflow, while
  preserving its existing horizontal-scroll behavior and keyboard reachability.
- Wrap or otherwise constrain long DatasetSnapshot fingerprint and integrity
  values so `/data` does not overflow a 390px viewport.
- Correct `tests/e2e/foundation.spec.ts` sequencing so PAPER assertions execute on
  `/paper`, Data assertions execute on `/data`, and the no-mutation assertion is
  made against the actual PAPER surface.
- Restore a visible keyboard focus indicator for read-resource Retry controls.
- Add or adjust focused regression coverage for the responsive/focus behavior and
  keep the existing read-only safety assertions.

## Affected implementation seams

- `frontend/components/app-shell.tsx`
- `frontend/components/data-overview.tsx`
- `frontend/components/read-resource.tsx`
- `frontend/tests/*` focused UI tests as directly needed
- `tests/e2e/foundation.spec.ts`

## Explicitly out of scope

- Any PLAN or architecture reopening or broader visual redesign.
- Backend, API contract, runtime, PAPER, Risk, OANDA, persistence, Strategy,
  migration, broker, activation, stop, reconcile, or capital-capable changes.
- New status facts, projections, controls, mutation requests, or historical PAPER
  session behavior.
- Cleanup of pre-existing repository-wide formatting failures or lint warnings
  outside the directly affected files.
- Substitution of a shared/non-dedicated database for E2E validation.

## Regression evidence required

- Focused unit/component tests for mobile-safe shell layout, long snapshot value
  wrapping, and visible Retry focus behavior pass.
- Focused Playwright discovery passes and, when the dedicated E2E environment is
  available, the smoke flow passes with no non-GET traffic.
- Existing full frontend tests, typecheck, lint, changed-file formatting, build,
  and `git diff --check` pass; baseline failures remain separately identified.
- Safari Technology Preview rechecks `/`, `/paper`, and `/data` at 390px,
  keyboard focus, document overflow, and PAPER no-control/read-only behavior.

## Worker Evidence

R001 implementation and validation are complete within the approved frontend and
E2E-test scope.

## Completion Receipt

```text
ROLE: BUILD
STATUS: DONE_WITH_CONCERNS
ARTIFACT: dispatch/workstreams/ui-01-trader-shell-read-only-overview/remediations/R001-ui-01-responsive-safety-smoke/BUILD.md
FILES CHANGED:
- frontend/components/app-shell.tsx
- frontend/components/data-overview.tsx
- frontend/components/read-resource.tsx
- frontend/tests/app_shell.test.tsx
- frontend/tests/data_overview.test.tsx
- tests/e2e/foundation.spec.ts
- dispatch/workstreams/ui-01-trader-shell-read-only-overview/remediations/R001-ui-01-responsive-safety-smoke/BUILD.md
CHECKS / EVIDENCE:
- Focused Vitest passed: 5 files, 15 tests (`home_page`, `app_shell`, `data_overview`, `overview`, `paper_status`).
- Full frontend Vitest passed: 16 files, 57 tests.
- Changed-file Prettier check passed for all six implementation/test files.
- Changed-file ESLint passed with 0 errors; full frontend lint passed with 0 errors and 242 pre-existing warnings in untouched Experiment workflow files.
- Frontend typecheck passed sequentially after the production build.
- Production build passed with `ATLAS_API_BASE_URL=http://127.0.0.1:8000`; emitted `/`, `/paper`, and `/data` routes.
- `git diff --check` passed.
- Playwright discovery passed: 2 tests listed in `foundation.spec.ts`.
- Safari Technology Preview at 390x844 independently checked `/`, `/paper`, and `/data`: document and body width remained 390px; primary navigation had a 342px viewport with 568-570px internal scroll content; returned 64-character DatasetSnapshot fingerprints fit within 300px facts; `/paper` exposed no mutation controls and observed only GET requests, including the expected inactive-status 404.
CONCERNS:
- Playwright execution was unavailable: standard execution stopped before browser launch because `http://127.0.0.1:8000/health/ready` was already occupied; an isolated-port retry stopped before browser launch because `ATLAS_E2E_DATABASE_URL` is unset/empty and the API rejected it (`database_url must use postgresql+psycopg`). No non-dedicated database was substituted.
- Repository-wide format check remains blocked by five pre-existing files: `frontend/app/providers.tsx`, `frontend/components/ui/select.tsx`, `frontend/lib/time.ts`, `frontend/tests/time.test.ts`, and `tests/e2e/.fixtures.json`.
- Safari's local keyboard-navigation setting sent a Tab from the wordmark to the timezone select rather than the first nav link; the focused Playwright keyboard assertions are present but could not execute without the dedicated E2E environment.
- No backend/runtime/PAPER/Risk/OANDA/persistence/Strategy/migration files changed; no mutation or capital-capable behavior was run.
```
