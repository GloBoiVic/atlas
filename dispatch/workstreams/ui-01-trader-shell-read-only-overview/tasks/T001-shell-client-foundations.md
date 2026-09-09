# T001 - Shell and Client Foundations

- **Status:** `DONE_WITH_CONCERNS`
- **Role:** BUILD
- **Workstream:** `ui-01-trader-shell-read-only-overview`
- **Branch:** `solo/ui-01-trader-shell-read-only-overview`
- **Owner:** fresh `solo-flow-worker`

## Objective

Implement the shared frontend foundations for the approved UI 01 lifecycle shell.
Make the Atlas wordmark and current-level navigation truthful, replace the home
redirect with a renderable route, correct API readiness language, and add the
smallest type-safe frontend client support for the existing safe PAPER and
historical-data GET contracts.

## Constraints

- Frontend-only changes. Do not modify backend, runtime, PAPER, Risk, OANDA,
  persistence, Strategy, or migration paths.
- Do not add code-generation infrastructure or hand-edit generated API output.
- Add only safe GET client methods; no activation, stop, reconcile, broker, or
  other mutation method may be introduced or called.
- Preserve the existing shell tokens, timezone selector, loading/error patterns,
  keyboard focus behavior, and mobile horizontal navigation behavior.
- Do not redesign existing Strategy or Experiment workflows.

## Dependencies

- None. T002 depends on this task's client and shell contracts.

## Required checks

- Focused home, shell, API-status, and API-client tests.
- Relevant frontend format, lint, typecheck, and test checks for changed files.

## Completion receipt

```text
ROLE: BUILD
STATUS: DONE_WITH_CONCERNS
ARTIFACT: dispatch/workstreams/ui-01-trader-shell-read-only-overview/tasks/T001-shell-client-foundations.md
FILES CHANGED:
- frontend/app/data/page.tsx
- frontend/app/layout.tsx
- frontend/app/page.tsx
- frontend/app/paper/page.tsx
- frontend/components/api-status.tsx
- frontend/components/app-shell.tsx
- frontend/lib/api-client.ts
- frontend/lib/api.generated.ts
- frontend/tests/api_client.test.ts
- frontend/tests/api_status.test.tsx
- frontend/tests/app_shell.test.tsx
- frontend/tests/home_page.test.tsx
- dispatch/workstreams/ui-01-trader-shell-read-only-overview/tasks/T001-shell-client-foundations.md
CHECKS / EVIDENCE:
- Focused Vitest: 4 files passed, 8 tests passed.
- Full frontend Vitest: 13 files passed, 44 tests passed.
- Full frontend lint: passed with 0 errors; 242 pre-existing warnings remain in untouched workflow files.
- Changed-file ESLint: passed.
- Frontend typecheck: `npm run typecheck:web` passed.
- Changed-file Prettier check and `git diff --check`: passed.
- Production build: `ATLAS_API_BASE_URL=http://127.0.0.1:8000 npm run build:web` passed; routes `/`, `/data`, and `/paper` generated.
- OpenAPI freshness: regenerated current `create_app().openapi()` output with `openapi-typescript` and Prettier; `cmp -s` passed.
- No backend or frozen trading-path diff; handwritten client adds only safe GET wrappers and exact inactive-state null handling.
FINDINGS / CONCERNS:
- `tests/e2e/foundation.spec.ts` still asserts the previous `/` Experiments redirect/title and was intentionally left for T003, which owns browser smoke updates after T002.
- No Playwright/browser smoke was run because T003 is blocked on T002 and the standard API/frontend smoke setup was not part of this task.
- `npm ci` reported 6 dependency audit findings (2 moderate, 3 high, 1 critical); no dependency files were changed.
```
