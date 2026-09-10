# R002 - Initial Risk Display

## Remediation ID

`R002`

## Status

`DONE`

## Origin finding and source artifact

- Finding: `F-002 — Initial risk is presented as a price`
- Source: `dispatch/workstreams/ui-03-paper-trade-outcome-visibility/VALIDATION.md`
- Location: `frontend/components/paper-trade-history.tsx:194-197`

## Finding severity

`PRODUCT / DEFECT`

## Related original tasks

- `T002`

## Approved requirement or invariant violated

Initial risk is an account-risk amount derived from filled trade facts and must be presented as a monetary amount, not as a market price.

## Exact remediation outcome

Present the fuller PAPER Trade history `Initial risk` value with the existing money formatter used for account P/L and financing. Add focused regression coverage proving the risk amount is not rendered with price precision/formatting.

## Affected implementation seams

- `frontend/components/paper-trade-history.tsx`
- `frontend/tests/paper_status.test.tsx`

## Explicit out-of-scope items

- No backend or API changes.
- No generated client changes.
- No changes to initial-risk calculation or durable evidence sourcing.
- No changes to execution, reconciliation, Risk, persistence, or migrations.
- No OANDA/provider calls, runtime startup, PAPER activation, or broker mutation.
- Do not reopen or modify F-001; it is resolved by R001.

## Regression evidence required

- Fuller history renders initial risk with existing money formatting.
- Entry, Stop, Target, realized P/L, financing, and other history presentation remain unchanged.
- Existing focused frontend tests and web checks continue to pass.
- `git diff --check` passes.

## Worker Evidence

- R002 is implemented in the fuller PAPER Trade history presentation. Initial
  risk now uses the existing account-money formatter, with focused regression
  coverage proving a non-price amount renders with currency and two decimal
  places while entry, exit, protection, realized P/L, financing, dividend
  adjustment, close time, direction, Strategy facts, and exit-cause behavior
  remain covered.

## Completion Receipt

```text
ROLE: BUILD
STATUS: DONE
ARTIFACT: dispatch/workstreams/ui-03-paper-trade-outcome-visibility/remediations/R002-initial-risk-display/BUILD.md
FILES CHANGED:
- frontend/components/paper-trade-history.tsx
- frontend/tests/paper_status.test.tsx
- dispatch/workstreams/ui-03-paper-trade-outcome-visibility/remediations/R002-initial-risk-display/BUILD.md
CHECKS / EVIDENCE:
- Focused T002 frontend tests: `29 passed` across `api_client.test.ts`, `overview.test.tsx`, and `paper_status.test.tsx`.
- `npm run check:web`: passed Prettier, ESLint with the existing 242 warnings and 0 errors, TypeScript, 94 frontend tests, and production build.
- `git diff --check`: passed.
- R002 changed only initial-risk frontend presentation, its focused regression coverage, and this receipt; no provider call, runtime start, PAPER activation, or broker mutation occurred.
FINDINGS / CONCERNS:
- None for R002. F-001 was not addressed.
```
