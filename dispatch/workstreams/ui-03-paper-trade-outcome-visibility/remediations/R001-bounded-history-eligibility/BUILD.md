# R001 - Bounded History Eligibility

## Remediation ID

`R001`

## Status

`DONE`

## Origin finding and source artifact

- Finding: `F-001 — Bounded query can omit completed Trades`
- Source: `dispatch/workstreams/ui-03-paper-trade-outcome-visibility/VALIDATION.md`
- Location: `backend/paper/trade_history.py:96-137`

## Finding severity

`PRODUCT / DEFECT`

## Related original tasks

- `T001`

## Approved requirement or invariant violated

The bounded history read must return eligible completed PAPER Trades newest-close-first. The SQL limit must not discard rows before durable CLOSED eligibility and chronological composition are established.

## Exact remediation outcome

Ensure the history projection cannot omit eligible completed Trades because non-CLOSED, malformed, mismatched, or otherwise ineligible observations consume the SQL limit. Preserve the approved bounded `limit` contract and deterministic newest-close-first ordering.

## Affected implementation seams

- `backend/paper/trade_history.py`
- `backend/tests/paper/test_trade_history.py`

## Explicit out-of-scope items

- No frontend changes.
- No API shape or limit-bound changes.
- No persistence schema or migration changes.
- No PAPER execution/reconciliation changes.
- No OANDA/provider calls, runtime startup, PAPER activation, or broker mutation.
- Do not address F-002; it is a separate R002 remediation.

## Regression evidence required

- A valid completed Trade is returned when ineligible observations would otherwise fill the SQL limit.
- Results remain newest-close-first by parsed close time with deterministic tie-breaking.
- Existing focused T001 history/API tests continue to pass.
- Changed-slice static checks and `git diff --check` pass.

## Worker Evidence

R001 is implemented in the PAPER Trade history read service. Raw schema-V2
observations are composed for durable eligibility and parsed chronological ordering
before the approved API limit is applied. Focused regression coverage verifies that an
ineligible observation cannot consume the requested limit and that timezone-normalized
close times use deterministic attempt-ID tie-breaking.

## Completion Receipt

```text
ROLE: BUILD
STATUS: DONE
ARTIFACT: dispatch/workstreams/ui-03-paper-trade-outcome-visibility/remediations/R001-bounded-history-eligibility/BUILD.md
FILES CHANGED:
- backend/paper/trade_history.py
- backend/tests/paper/test_trade_history.py
- dispatch/workstreams/ui-03-paper-trade-outcome-visibility/remediations/R001-bounded-history-eligibility/BUILD.md
CHECKS / EVIDENCE:
- Focused history/API tests: 30 passed; one existing Starlette/httpx deprecation warning.
- Regression coverage retains an eligible CLOSED Trade behind an ineligible observation and verifies parsed close-time ordering with deterministic tie-breaking.
- Changed-slice Ruff format/check passed; Pyright reported 0 errors.
- `uv run alembic check`: No new upgrade operations detected.
- `git diff --check`: passed.
- R001 changed only the history service, its focused tests, and this receipt; no provider call, runtime start, PAPER activation, or broker mutation occurred.
FINDINGS / CONCERNS:
- None for R001. F-002 was not addressed.
```
