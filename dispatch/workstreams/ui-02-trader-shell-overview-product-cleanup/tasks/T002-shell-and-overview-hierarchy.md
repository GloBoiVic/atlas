# T002 - Shell and Overview Hierarchy

- **Workstream:** `ui-02-trader-shell-overview-product-cleanup`
- **Status:** `DONE_WITH_CONCERNS`
- **Role:** `BUILD`
- **Branch:** `solo/ui-02-trader-shell-overview-product-cleanup`
- **Base:** `9c31774f499c2e21a34b7f80fbfa190bf3be1fdb`
- **Dependency:** T001 DONE

## Outcome

Implement the approved trader-facing shell and Overview hierarchy using the existing read contracts and compact components from T001.

## Scope

Primary files:

- `frontend/components/app-shell.tsx`
- `frontend/components/overview.tsx`
- `frontend/tests/app_shell.test.tsx`
- `frontend/tests/overview.test.tsx`

Required behavior:

- Remove the lifecycle explainer strip and standalone timezone body sentence while retaining navigation, API status, timezone selector, responsive behavior, and disabled LIVE affordance.
- Make current broker exposure the first substantive Overview section.
- Add trader-facing Strategies, Experiments, and compact System summaries using existing reads/helpers.
- Remove Overview capability, historical-data, DatasetSnapshot, raw status-count, and global Next Steps sections.
- Preserve independent loading, empty, and error states and contextual Strategy/Experiment links.
- Keep Overview free of UUIDs, provider Trade IDs, raw error codes, mutation controls, and unsupported claims.

## Constraints

- Frontend-only; no backend files, API contracts, generated clients, or broker behavior.
- Do not modify shared helpers unless a real reuse gap is demonstrated.
- No global navigation redesign, automatic polling, or trading controls.

## Checks

Run the focused shell/Overview tests from the PLAN and record the exact result in this task file. Do not mark this task done without implementation, tests, and a concise completion receipt.

## Worker Evidence

- BUILD execution completed after T001 completion.

## Immutable BUILD Receipt

- **Status:** `DONE_WITH_CONCERNS`
- **Files changed:**
  - `frontend/components/app-shell.tsx`
  - `frontend/components/overview.tsx`
  - `frontend/tests/app_shell.test.tsx`
  - `frontend/tests/overview.test.tsx`
  - `frontend/tests/home_page.test.tsx` (directly required stale route assertion)
  - `dispatch/workstreams/ui-02-trader-shell-overview-product-cleanup/tasks/T002-shell-and-overview-hierarchy.md`
- **Checks/evidence:**
  - `npm run test:web -- tests/app_shell.test.tsx tests/overview.test.tsx tests/paper_broker_state.test.tsx tests/paper_status.test.tsx` - passed, 34 tests.
  - `npm run check:web` - passed formatting, typecheck, 91 tests, and production build.
  - `npm run lint:web` - passed with 242 existing warnings and no errors.
  - `git diff --check` - passed.
  - Shell evidence covers retained navigation, API status, disabled LIVE affordance, visible focus class, timezone selection, and removal of lifecycle/timezone body copy.
  - Overview evidence covers exposure-first hierarchy, compact active/no-active runtime, Strategy and Experiment summaries/actions, compact healthy/degraded System facts, independent loading/empty/error states, no capability/historical/snapshot/Next Steps sections, no raw runtime code or provider Trade ID, and no mutation controls.
  - Overview continues to use read-only existing reads only: `ready()`, `listStrategies()`, `listExperiments()`, `paperBrokerState()`, and `activePaperStatus()`.
- **Findings/concerns:**
  - The frontend lint gate retains 242 pre-existing unused-variable warnings; this task introduced no lint errors.
  - `frontend/tests/home_page.test.tsx` was updated narrowly because the approved removal of the recurring Overview explanation invalidated its old copy assertion.
  - No backend files, generated clients, shared helpers, API request semantics, automatic polling, or mutation controls were changed.
