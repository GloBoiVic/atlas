# TASK-08 — Experiment list/config/run UI

- **Task:** Implement approved blueprint task 8 only.
- **Branch:** `feature/phase-5-experiment-workflow`
- **Scope:** `/experiments`, `/experiments/new`, and the minimal status/configuration detail route required for create → redirect → retry-safe start and polling. Completed result and Trade inspection UI remains task 9.

## Changed files

- `frontend/app/experiments/page.tsx`
- `frontend/app/experiments/new/page.tsx`
- `frontend/app/experiments/[experimentId]/page.tsx`
- `frontend/components/experiment-workflow.tsx`
- `frontend/lib/api-client.ts`
- `frontend/app/globals.css`

## Outcome

Implemented the approved Experiment list, configuration, coverage validation, create,
redirect/start, retry-safe run command, PENDING/RUNNING refresh, and terminal polling
flow. Coverage is cleared on every relevant configuration edit. Run-command transport
timeouts are surfaced as unknown client outcomes; the detail page polls durable status
and provides an explicit retry without creating a replacement Experiment. Persistent
coverage, API, command, and failed status states remain in-page.

No completed result charts, Trade detail, backend code, handwritten API response
models, raw UUID labels, or adjacent feature pages were added.

## Validation receipts

- `npm run format:check:web` → **passed**.
- `npm run lint:web` → **passed**.
- `npm run typecheck:web` → **passed**.
- `npm run test:web` → **4 tests passed** across 3 existing test files.
- `ATLAS_API_BASE_URL=http://localhost:8000 npm run build:web` → **passed**; routes generated for `/experiments`, `/experiments/new`, and `/experiments/[experimentId]`.
- `git diff --check` → **passed**.

The existing frontend test suite does not yet include browser-level coverage for
the new workflow states; static/type/build validation passed. No backend test or
API integration test was added because backend scope is explicitly excluded.

## Blockers

The Task-06 list response currently serializes `metrics: null` for every list row
(`backend/api/experiments.py` listing calls `_detail(row)` without a metrics
projection). The UI renders the required non-completed em dash and renders
backend-provided completed metrics when available, but completed list metrics
cannot appear until that backend contract gap is repaired in the owning backend
scope. No backend change was made. No Git mutations were performed.

## R1 remediation — Max Drawdown list cell

Repaired only the blocked frontend defect: the Max Drawdown cell now reads the
canonical API field `metrics.maxDrawdownPercent`. It continues to use the shared
metric-state formatter, rendering a `VALUE` decimal and `—` for
`UNAVAILABLE`/missing states without fabricating zeroes. Added
`frontend/tests/experiment_list.test.tsx`, a focused rendered-cell regression
covering both value and unavailable semantics. No backend, Task 9, or unrelated
minor finding was changed.

### Remediation receipts

- `npm run format:check:web` → **passed**.
- `npm run lint:web` → **passed**.
- `npm run typecheck:web` → **passed**.
- `npm run test:web` → **5 tests passed** across 4 files, including the focused
  Max Drawdown value/unavailable regression.
- `ATLAS_API_BASE_URL=http://localhost:8000 npm run build:web` → **passed**.
- `git diff --check` → **passed**.

No Git mutations were performed.

The earlier Task-06 list-metrics note above is superseded by the approved
backend list-metrics repair recorded in the current `VALIDATION.md`; this
remediation made no backend changes.
