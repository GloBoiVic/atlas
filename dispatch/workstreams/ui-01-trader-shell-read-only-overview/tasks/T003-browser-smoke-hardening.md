# T003 - Browser Smoke and Hardening

- **Status:** `DONE_WITH_CONCERNS`
- **Role:** BUILD
- **Workstream:** `ui-01-trader-shell-read-only-overview`
- **Branch:** `solo/ui-01-trader-shell-read-only-overview`
- **Owner:** fresh `solo-flow-worker`

## Objective

After T002, add or update focused Playwright smoke coverage for `/`, `/paper`,
and `/data`, verify lifecycle navigation and the absence of PAPER mutation
controls or requests, and make only the directly required frontend test or
selector hardening changes.

## Constraints

- Depends on T002's completed surfaces.
- Frontend and frontend-test/e2e changes only; no backend or trading-path edits.
- Do not weaken existing Experiment or Strategy workflow assertions.
- Do not create activation, reconcile, runtime, broker, or other mutation traffic.

## Required checks

- Focused Playwright smoke flow against the standard local API/frontend setup when
  available, with truthful reporting if the environment is unavailable.
- Relevant frontend format, lint, typecheck, unit-test, and build checks.

## Completion receipt

```text
ROLE: BUILD
STATUS: DONE_WITH_CONCERNS
ARTIFACT: dispatch/workstreams/ui-01-trader-shell-read-only-overview/tasks/T003-browser-smoke-hardening.md
FILES CHANGED:
- tests/e2e/foundation.spec.ts
- dispatch/workstreams/ui-01-trader-shell-read-only-overview/tasks/T003-browser-smoke-hardening.md
CHECKS / EVIDENCE:
- Focused Playwright discovery passed: 2 tests listed in foundation.spec.ts.
- Focused Playwright execution was attempted on the standard setup. The first attempt was blocked because port 8000 was already occupied by a pre-existing process. An alternate-port retry was blocked before browser launch because ATLAS_E2E_DATABASE_URL is unset; the configured API exited after receiving an empty database URL. No browser workflow or mutation request ran.
- Focused smoke spec Prettier check passed.
- Focused smoke spec ESLint check passed.
- Frontend ESLint passed with 0 errors; 242 pre-existing warnings remain in untouched Experiment workflow files.
- Frontend typecheck passed after the production build completed.
- Focused frontend Vitest passed: 4 files, 10 tests.
- Full frontend Vitest passed on rerun: 16 files, 57 tests.
- Production build passed with ATLAS_API_BASE_URL=http://127.0.0.1:8000 and emitted /, /paper, and /data.
- git diff --check passed.
FINDINGS / CONCERNS:
- Browser smoke could not execute because the isolated PostgreSQL E2E database variable is unavailable; no database was inferred or substituted.
- Repository-wide format check remains blocked by five pre-existing files: frontend/app/providers.tsx, frontend/components/ui/select.tsx, frontend/lib/time.ts, frontend/tests/time.test.ts, and tests/e2e/.fixtures.json. The changed smoke spec is formatted.
- The first parallel full Vitest invocation reported one unrelated experiment_results assertion failure; the affected file passed in isolation and the subsequent full rerun passed.
- No backend, runtime, PAPER, Risk, OANDA, persistence, migration, broker, or Dogfood 02/Trade 11 paths were changed; no browser request reached the API, and atlas-runtime was not run.
```
