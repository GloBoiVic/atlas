# REVIEW - R002 Initial Risk Display

## Status

- **Status:** `PASS`
- **Workstream:** `ui-03-paper-trade-outcome-visibility`
- **Remediation:** `R002`
- **Role:** `REVIEW`
- **Branch:** `solo/ui-03-paper-trade-outcome-visibility`
- **Base:** `main` at `664b19c902656b37271158c55faf7f7d19cfa840`
- **Origin:** `F-002 - Initial risk is presented as a price`

## Review Mandate

Independently judge R002 against the approved `PLAN.md`, origin finding
F-002, the R002 BUILD and VALIDATION packets, the original T002 contract and
receipt, R001 evidence, current source/tests, and the complete base-to-working-
tree diff. Confirm that the smallest approved fix presents durable initial-risk
amounts as money, preserves market-price formatting and all adjacent trader
behavior, leaves calculation/API/durable sourcing unchanged, and does not
change a capital-capable boundary. F-001 must remain resolved by R001.

## Inputs Reviewed

- Approved `PLAN.md` and its R002 scope, acceptance criteria, and out-of-scope
  boundaries.
- Origin F-002 in the immutable workstream `VALIDATION.md`.
- R002 `BUILD.md` and `VALIDATION.md`.
- Original T002 task contract and BUILD receipt.
- R001 `REVIEW.md` and `VALIDATION.md`, including the F-001 disposition.
- Current `frontend/components/paper-trade-history.tsx` and
  `frontend/tests/paper_status.test.tsx`.
- Existing `formatMoney` and `formatPrice` implementations.
- Current API client, API schemas, history read service, and related frontend
  tests to verify unchanged boundaries and adjacent behavior.
- Complete visible base-to-working-tree diff, including the separate T001,
  T002, R001, and dispatch artifacts.
- Fresh Web Interface Guidelines fetched for the UI review.

## Acceptance Judgment

**PASS.** R002 resolves F-002 within the approved narrow presentation scope.

- The fuller history card now renders `trade.initialRisk` with the existing
  `formatMoney` formatter at `frontend/components/paper-trade-history.tsx:194-197`.
  That formatter uses the established signed currency format with two decimal
  places (`frontend/lib/experiment-formatters.ts:27-31`), so the account-risk
  amount is no longer presented as a five-decimal market price.
- Market prices remain routed through `priceLabel` and `formatPrice` at
  `frontend/components/paper-trade-history.tsx:63-65`; Entry, Exit, Stop, and
  Target continue to use that path at lines 170-192.
- R002 changes no initial-risk calculation, API schema, generated contract,
  history read service, durable Fill sourcing, execution, reconciliation,
  persistence, Risk, Strategy, provider, or broker behavior. The current
  history service still sources initial risk from durable Fill facts at
  `backend/paper/trade_history.py:208-228` and `:373-392`.
- The focused regression uses `initialRisk: '0.00500'`, asserts the monetary
  `+$0.01` output, rejects the old `0.00500` display, and continues to assert
  five-decimal Entry/Stop/Target price output. The same test retains coverage
  for realized P/L, financing, dividend adjustment, direction, Strategy facts,
  timezone display, exact exit labels, unavailable causes, and raw identifier
  suppression.
- Existing current PAPER broker/runtime sections, read-only behavior, loading,
  empty, error, retry, Overview, and PAPER-page behavior remain covered and
  unchanged by the R002 delta.
- F-001 remains resolved and is not reopened. R001's post-composition limit
  and deterministic chronology remain present in
  `backend/paper/trade_history.py:96-205`; R002 changes no backend history
  code.
- The R002-owned implementation/test delta is limited to the approved
  presentation formatter and regression coverage. No activation, reconciliation
  control, runtime startup, provider call, or broker mutation path was added.

## Evidence

- Focused frontend command:
  `npx vitest run --config frontend/vitest.config.ts frontend/tests/api_client.test.ts frontend/tests/overview.test.tsx frontend/tests/paper_status.test.tsx`
  -> 3 files passed, 29 tests passed.
- Full web gate: `npm run check:web` passed Prettier, TypeScript, 94 frontend
  tests, and production build. ESLint passed with 242 existing warnings and 0
  errors; no R002 warning or error was identified.
- `git diff --check HEAD` passed with no whitespace diagnostics.
- Source and diff review found no R002-specific accessibility or interaction
  issue under the fetched Web Interface Guidelines. The change is a semantic
  labeled fact value and introduces no new interactive control.
- No OANDA call, credentialed external check, `atlas-runtime` startup, PAPER
  activation, broker mutation, or other capital-capable action was performed.

## Findings

### CRITICAL

None.

### IMPORTANT

None.

### PRODUCT / REGRESSION / TOOLING

None. No `DEFECT` or `NEW SCOPE` finding was identified for R002. F-001
remains a resolved R001 finding; it is not a regression or R002 concern.

## Residual Limitations

- No PostgreSQL integration test was run because R002 changes no backend or
  database seam; R001/T001 backend evidence remains the applicable evidence for
  durable sourcing and F-001.
- No populated branch-specific browser fixture was run. R002's populated-value
  behavior is covered by current source review and the passing jsdom regression;
  starting another server was unnecessary and prohibited runtime activity was
  not performed.
- The repository's existing 242 ESLint warnings remain outside the R002 seam;
  they are a tooling baseline, not an R002 finding.

## Merge Recommendation

**MERGE APPROVED** for R002 after the normal explicit workstream merge
approval. F-002 is resolved, F-001 remains resolved, and no further R002
remediation is warranted.

## Completion Receipt

```text
ROLE: REVIEW
STATUS: PASS
ARTIFACT: dispatch/workstreams/ui-03-paper-trade-outcome-visibility/remediations/R002-initial-risk-display/REVIEW.md
FILES CHANGED BY REVIEW: dispatch/workstreams/ui-03-paper-trade-outcome-visibility/remediations/R002-initial-risk-display/REVIEW.md only
CHECKS / EVIDENCE: Independent source, current-test, specialist-guideline, and complete-diff review; focused frontend tests 29 passed; npm run check:web passed with 94 frontend tests, TypeScript, Prettier, production build, and ESLint with 242 existing warnings and 0 errors; git diff --check passed; F-001 remains resolved by R001; no provider, runtime, activation, broker mutation, or capital-capable action occurred.
FINDINGS / CONCERNS: PASS - no unresolved CRITICAL or IMPORTANT PRODUCT/REGRESSION finding; no R002 DEFECT or NEW SCOPE finding. F-002 is resolved by the approved presentation-only change. PostgreSQL integration and populated branch-specific browser evidence were not run and are recorded as non-blocking limitations.
```
