# T002 - Overview, PAPER, and Data Surfaces

- **Status:** `DONE_WITH_CONCERNS`
- **Role:** BUILD
- **Workstream:** `ui-01-trader-shell-read-only-overview`
- **Branch:** `solo/ui-01-trader-shell-read-only-overview`
- **Owner:** fresh `solo-flow-worker`

## Objective

After T001, compose independent read-only Overview, PAPER, and Data surfaces from
the existing GET contracts. Preserve truthful loading, empty, unavailable, and
error states, display-timezone formatting, and the explicit PAPER safety boundary.

## Constraints

- Depends on T001 client methods and shell foundations.
- Frontend-only changes. No backend projection, persistence, runtime, broker, or
  trading behavior changes.
- PAPER must expose no activation, stop, reconcile, Buy/Sell, close, protection,
  or broker mutation affordance and must not imply historical activation evidence.
- Do not fabricate totals, performance, account, Trade, P/L, RiskDecision, exit,
  realized-R, or broker-flatness claims.
- Data must use only existing historical capability, configuration-options
  DatasetSnapshot facts, and optional active-load facts.

## Required checks

- Focused Overview, PAPER, and Data component tests for loading, populated,
  empty, unavailable, error, and timezone states.
- Relevant frontend format, lint, typecheck, and test checks for changed files.

## Completion receipt

```text
ROLE: BUILD
STATUS: DONE_WITH_CONCERNS
ARTIFACT: dispatch/workstreams/ui-01-trader-shell-read-only-overview/tasks/T002-overview-paper-data-surfaces.md
FILES CHANGED: frontend/app/page.tsx; frontend/app/paper/page.tsx; frontend/app/data/page.tsx; frontend/components/overview.tsx; frontend/components/paper-status.tsx; frontend/components/data-overview.tsx; frontend/components/read-resource.tsx; frontend/tests/home_page.test.tsx; frontend/tests/overview.test.tsx; frontend/tests/paper_status.test.tsx; frontend/tests/data_overview.test.tsx; dispatch/workstreams/ui-01-trader-shell-read-only-overview/tasks/T002-overview-paper-data-surfaces.md
CHECKS / EVIDENCE: Focused Prettier check passed for all T002 files; focused ESLint passed; npm run typecheck:web passed; final focused Overview/PAPER/Data/Home suite passed 4 files / 14 tests; npm run test:web passed 16 files / 57 tests; npm run build:web passed and emitted /, /paper, and /data; git diff --check passed.
FINDINGS / CONCERNS: npm run format:check:web reports pre-existing formatting issues outside T002 (including T001/baseline files); npm run lint:web exits 0 with pre-existing warnings in existing Experiment components. No backend files changed; no PAPER mutation or broker calls were added.
```
