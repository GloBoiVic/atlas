# TASK-09 — Completed Experiment results and Trade detail UI

- **Task:** Implement approved Phase 5 blueprint task 9 only.
- **Agent:** frontend builder
- **Branch:** `feature/phase-5-experiment-workflow`
- **Scope:** Completed, failed, zero-Trade, and focused Trade inspection views.

## Changed files

- `frontend/components/experiment-workflow.tsx`
- `frontend/lib/api-client.ts`
- `frontend/app/experiments/[experimentId]/trades/[sequenceNumber]/page.tsx`

## Outcome

Completed Experiment detail now renders backend-authoritative metric states,
including accurate unavailable and infinite values, zero-Trade messaging,
equity and drawdown Lightweight Charts, Trade table/detail links, ambiguity
disclosure, and assumptions/provenance disclosures. Failed Experiments retain
the existing persistent fail-closed result hierarchy; PENDING/RUNNING remain
status-only and do not expose partial facts.

Trade detail adds focused immutable M15 candle context with EMA 100, entry,
stop, target, exit levels, omitted-range disclosure, captured rationale, and
human-readable Risk/order/fill lineage. No Strategy, P&L, metric, coverage, or
chart-context calculations were added to the browser.

## Exact validation receipts

- `npm run format:check:web` → **passed**.
- `npm run lint:web` → **passed** (no errors; one prior hook warning was removed).
- `npm run typecheck:web` → **passed**.
- `npm run test:web` → **5 tests passed** across 4 files.
- `ATLAS_API_BASE_URL=http://localhost:8000 npm run build:web` → **passed**;
  generated `/experiments/[experimentId]/trades/[sequenceNumber]` alongside
  existing Experiment routes.

## Acceptance coverage

- Completed hierarchy: metrics → equity → drawdown → Trades → assumptions /
  provenance.
- Failed hierarchy: persistent failure explanation and next action; no result
  cards, charts, or partial Trades.
- Zero-Trade: explicit valid zero-Trade state with unavailable Trade metrics
  and empty table, never fabricated zeroes.
- Metric states: `VALUE`, `INFINITE`, and unavailable reasons remain visible;
  no frontend metric calculations.
- Safety/status: persistent status and API/request failure surfaces remain in
  page; narrow tables scroll horizontally; chart and status layouts stack.
- Disclosures: ambiguity/Stop-first, financing excluded, embedded spread,
  immutable DatasetSnapshot provenance, and bounded chart omitted range.

## Blockers

None. No backend files or Task 10 work were changed. No Git mutations were
performed. Existing pre-task worktree changes and dispatch artifacts remain
untouched except this report.

## R1 remediation — focused Task-9 test adequacy

Added only focused frontend test coverage for the Important R1 validation gap.
`frontend/tests/experiment_results.test.tsx` now covers completed `VALUE`,
`INFINITE`, and unavailable metric states/reasons; zero-Trade messaging and
empty Trade state; failed no-result hierarchy; persistent RUNNING status with
partial result suppression; chart setup/series and cleanup through a safe
Lightweight Charts test double; and focused Trade detail chart setup,
immutable candle context, rationale, execution lineage, ambiguity/Stop-first,
financing, and omitted-range disclosures. It also asserts the Trade-oriented
responsive heading/table surface without changing functional UI code.

`frontend/vitest.config.ts` only inlines `lightweight-charts` for the existing
jsdom test environment so the approved chart dependency can be safely mocked;
no production behavior was changed.

### Exact remediation receipts

- `npm run format:check:web` → **passed**.
- `npm run lint:web` → **passed** (no errors or warnings after cleanup).
- `npm run typecheck:web` → **passed**.
- `npm run test:web` → **5 test files, 9 tests passed**.
- `git diff --check -- frontend/tests/experiment_results.test.tsx frontend/vitest.config.ts` → **passed**.

No backend, functional frontend, Task 10, or other dispatch artifact was
modified. No Git mutations were performed.
