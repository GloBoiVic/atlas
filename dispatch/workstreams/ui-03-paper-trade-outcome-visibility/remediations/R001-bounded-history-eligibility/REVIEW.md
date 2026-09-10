# REVIEW - R001 Bounded History Eligibility

- **Status:** `PASS`
- **Workstream:** `ui-03-paper-trade-outcome-visibility`
- **Remediation:** `R001`
- **Role:** `REVIEW`
- **Branch:** `solo/ui-03-paper-trade-outcome-visibility`
- **Base:** `main` at `664b19c902656b37271158c55faf7f7d19cfa840`
- **Origin:** `F-001 — Bounded query can omit completed Trades`

## Review Mandate

Independently judge R001 against the approved `PLAN.md`, F-001, the R001
BUILD/VALIDATION packets, the T001 contract, current source/tests, and the
complete branch/worktree diff. Confirm that the smallest complete fix removes
pre-composition loss of eligible completed Trades, makes chronology deterministic,
and leaves API, financial, execution, provider, and broker boundaries unchanged.
F-002 is explicitly outside R001 and remains reserved for R002.

## Inputs Reviewed

- Approved `PLAN.md` and T001 task contract/receipt.
- Immutable workstream `VALIDATION.md`, including F-001 and F-002.
- R001 `BUILD.md` and `VALIDATION.md`.
- Current `backend/paper/trade_history.py` and
  `backend/tests/paper/test_trade_history.py`.
- Complete recorded-base-to-worktree diff, including the separate T001/T002
  backend, frontend, generated-contract, and dispatch artifacts.
- Relevant PAPER persistence models/contracts for durable Fill, schema-V2
  observations, closure economics, and reconciliation status.

## Acceptance Judgment

**PASS.** R001 resolves F-001 within the approved narrow remediation scope.

- `PaperTradeHistoryReadService.list()` no longer applies SQL `LIMIT` or SQL
  chronology to candidate Trade observations. It loads all schema-V2
  `TRADE_DETAIL` candidates for filled `LIFECYCLE_ADVANCED` attempts, groups
  observations, validates Fill and CLOSED Trade evidence, rejects malformed or
  contradictory closure evidence, composes eligible items, and only then
  applies `composed[:limit]` (`backend/paper/trade_history.py:96-205`). An
  ineligible observation therefore cannot consume the requested result limit.
- Close timestamps are parsed as timezone-aware values and normalized to UTC
  before composition. The final sort is descending parsed close time with
  descending canonical attempt-UUID text as a deterministic tie-breaker
  (`backend/paper/trade_history.py:185-205,430-446`).
- The regression test places an OPEN observation ahead of an eligible CLOSED
  observation and uses a SQL-limit-aware fake; the eligible Trade is retained.
  The chronology test covers offset-normalized timestamps and deterministic
  equal-instant tie-breaking (`backend/tests/paper/test_trade_history.py:207-221,
  265-311`).
- The R001-owned seams are limited to the history service and its focused
  regression tests. No R001 change alters the API schema/route, generated
  contract, frontend, persistence schema or migrations, PAPER
  execution/reconciliation behavior, runtime, Risk, Strategy, provider, or
  broker mutation boundary. Existing T001/T002 changes in the complete branch
  diff remain separate from this remediation.
- F-002 is not addressed: the fuller history UI still presents `initialRisk`
  through the price formatter (`frontend/components/paper-trade-history.tsx:194-197`).
  This is the approved R002 boundary, not an R001 defect or regression.

## Evidence

- `uv run pytest backend/tests/paper/test_trade_history.py backend/tests/test_api_paper.py`:
  **30 passed**, one existing Starlette/httpx deprecation warning.
- `uv run pytest -m "not integration and not external"`: **1296 passed, 4
  skipped, 115 deselected, 4 warnings**.
- Scoped R001 Ruff format/check passed; scoped Pyright reported **0 errors, 0
  warnings, 0 informations**.
- `uv run alembic check`: **No new upgrade operations detected**.
- `git diff --check`: passed.
- T001 validation evidence confirms the unchanged bounded API contract,
  read-only route behavior, and byte-current generated OpenAPI client.
- No OANDA/provider request, credentialed external check, `atlas-runtime`
  startup, PAPER activation, broker mutation, or capital-capable action was
  performed.

## Findings

### CRITICAL

None.

### IMPORTANT

None.

### PRODUCT / REGRESSION / TOOLING

None. No defect or new-scope finding was identified in R001.

## Residual Limitations

- Dedicated PostgreSQL integration was not run because
  `ATLAS_TEST_DATABASE_URL` was unavailable. This is a non-blocking tooling
  limitation; the focused fake-session regression and static evidence pass.
- The existing Starlette/httpx deprecation warning remains unrelated to R001.

## Merge Recommendation

**MERGE APPROVED** for R001 after the normal explicit workstream merge approval.
R001 is complete and no further F-001 remediation is warranted. Proceed with
F-002 only through the separately approved R002 scope.

## Completion Receipt

```text
ROLE: REVIEW
STATUS: PASS
ARTIFACT: dispatch/workstreams/ui-03-paper-trade-outcome-visibility/remediations/R001-bounded-history-eligibility/REVIEW.md
FILES CHANGED BY REVIEW: dispatch/workstreams/ui-03-paper-trade-outcome-visibility/remediations/R001-bounded-history-eligibility/REVIEW.md only
CHECKS / EVIDENCE: Independent source and complete-diff review; focused history/API tests 30 passed; broad safe backend 1296 passed, 4 skipped, 115 deselected; scoped Ruff/Pyright passed; Alembic check reported no new operations; git diff --check passed; no provider, runtime, activation, broker mutation, or capital-capable action occurred.
FINDINGS / CONCERNS: PASS — no unresolved CRITICAL or IMPORTANT PRODUCT/REGRESSION finding; no R001 DEFECT or NEW SCOPE finding. PostgreSQL integration was unavailable without ATLAS_TEST_DATABASE_URL and is recorded as a non-blocking tooling limitation. F-002 remains intentionally reserved for R002.
```
