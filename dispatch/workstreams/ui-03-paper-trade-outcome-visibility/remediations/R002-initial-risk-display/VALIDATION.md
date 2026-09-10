# VALIDATION - R002 Initial Risk Display

## Result

- **Status:** `PASS`
- **Workstream:** `ui-03-paper-trade-outcome-visibility`
- **Remediation:** `R002`
- **Role:** `VALIDATE`
- **Branch:** `solo/ui-03-paper-trade-outcome-visibility`
- **Base:** `main` at `664b19c902656b37271158c55faf7f7d19cfa840`
- **Finding disposition:** F-002 is resolved within the approved R002 scope.
- **R002 findings:** None.

## Scope Review

- Reviewed the R002 BUILD packet, origin finding F-002 in the immutable workstream VALIDATION, the approved PLAN, the original T002 task receipt, R001 validation evidence, current source/tests, and the complete visible working-tree diff.
- R002-owned implementation and regression seams are `frontend/components/paper-trade-history.tsx` and `frontend/tests/paper_status.test.tsx`, as approved by BUILD. The visible worktree also contains the separate T001/T002/R001 implementation and dispatch artifacts; no R002-specific scope drift was identified.
- The R002 change is presentation-only. It does not change `initialRisk` calculations, the typed API contract, durable Fill sourcing, the history read service, execution, reconciliation, persistence, migrations, runtime, Risk, or provider integrations.
- The current history read service still projects initial risk from durable Fill evidence: `backend/paper/trade_history.py:126`, `:216-228`, and `:386`. R002 does not alter that path.

## Acceptance Coverage

### F-002 initial-risk presentation

- F-002 identified `frontend/components/paper-trade-history.tsx:194-197` as passing account-risk data through the price formatter, producing five-decimal output without currency.
- The current fuller-history card uses `formatMoney(trade.initialRisk)` at `frontend/components/paper-trade-history.tsx:194-197`.
- The existing `formatMoney` implementation uses currency and two decimal places (`frontend/lib/experiment-formatters.ts:27-31`), while `priceLabel` continues to use `formatPrice` for market prices (`frontend/components/paper-trade-history.tsx:63-65`).
- The focused regression fixture supplies `initialRisk: '0.00500'` and asserts eight `+$0.01` monetary displays and no `0.00500` price-formatted display (`frontend/tests/paper_status.test.tsx:311-372`). This proves the risk amount is formatted as money and is not rendered with price precision.

### Adjacent T002 behavior

- Entry and exit remain price-formatted through `priceLabel`; Stop and Target remain price-formatted through the same helper (`frontend/components/paper-trade-history.tsx:170-192`). The focused regression continues to assert the five-decimal price values.
- Realized P/L, financing, and non-zero dividend adjustment remain separate `formatMoney` values. The focused regression covers positive and negative P/L, financing, and dividend output and does not introduce a Net P/L calculation.
- Exact `TAKE_PROFIT`, `STOP_LOSS`, `MARKET_CLOSE`, `MARGIN_CLOSEOUT`, and `OTHER` causes retain their trader-facing labels. Null, `UNRESOLVED`, and `MULTIPLE` remain `Exit cause unavailable`; raw cause values are not presented.
- Current PAPER capability, broker exposure, and runtime sections remain present and independent. Existing active, inactive, loading, empty, error, refresh, and no-mutation assertions remain in `frontend/tests/paper_status.test.tsx`.
- Overview recent-history behavior, PAPER full-history behavior, bounded limits, loading/empty/error handling, timezone display, and read-only client GET behavior remain covered by the focused frontend tests.

## Checks

```text
npx vitest run --config frontend/vitest.config.ts frontend/tests/api_client.test.ts frontend/tests/overview.test.tsx frontend/tests/paper_status.test.tsx
3 test files passed; 29 tests passed

npm run check:web
Prettier passed; ESLint passed with 242 existing warnings and 0 errors;
TypeScript passed; 18 test files passed with 94 tests passed; production build passed.

git diff --check HEAD
Passed with no output.

git diff --no-index --check /dev/null frontend/components/paper-trade-history.tsx || test $? -eq 1
git diff --no-index --check /dev/null dispatch/workstreams/ui-03-paper-trade-outcome-visibility/remediations/R002-initial-risk-display/VALIDATION.md || test $? -eq 1
Passed with no whitespace diagnostics; expected no-index difference exits were accepted.

git status --short && git diff --stat HEAD && git diff --name-only HEAD && git ls-files --others --exclude-standard
Showed the expected mixed UI-03 worktree: T001 backend/API/generated files, T002 frontend files,
R001/R002 and workstream dispatch artifacts, and no migration/runtime/Risk/provider file added by R002.
The R002-specific source/test review was limited to the approved history component formatter seam and
its focused regression assertions.
```

No OANDA call, credentialed external check, `atlas-runtime` startup, PAPER activation, or broker mutation was performed.

## Browser Evidence

- An existing local browser tab at `http://127.0.0.1:3000/` rendered the current Overview structure, including `Recent PAPER trades`, and preserved the current broker/runtime sections. Its history read returned the non-destructive `Completed PAPER trades are unavailable.` state, so it did not provide a populated card for visual inspection of the formatted initial-risk value.
- No new web server or runtime was started for this validation. Populated initial-risk evidence therefore comes from current source review and the passing jsdom regression, not a fresh browser fixture run. The available tab was not treated as branch-specific browser evidence.

## Findings

- None for R002. F-002 is resolved by the approved presentation-only change. No `PRODUCT / REGRESSION / TOOLING` plus `DEFECT / NEW SCOPE` finding was identified.
- The 242 ESLint warnings are existing repository warnings with zero errors and are outside the R002 seam; they are recorded as a residual tooling baseline, not an R002 finding.

## Limitations

- No PostgreSQL integration test was run because R002 changes no backend/database seam; T001/R001 focused backend evidence remains the applicable evidence for durable sourcing.
- No populated branch-specific browser fixture was available without starting another server. Browser evidence is consequently limited as stated above.
- No credentialed external checks were run. No `atlas-runtime` process was started, PAPER was not activated, and no broker mutation was performed.
