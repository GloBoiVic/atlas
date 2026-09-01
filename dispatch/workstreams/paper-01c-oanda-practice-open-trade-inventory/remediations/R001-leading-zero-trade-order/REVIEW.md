# REVIEW — R001 Leading-Zero Trade Order

- **Status:** `PASS`
- **Workstream:** `paper-01c-oanda-practice-open-trade-inventory`
- **Branch:** `solo/paper-01c-oanda-practice-open-trade-inventory`
- **Role:** `REVIEW`
- **Remediation:** `R001`
- **Origin finding:** `IMPORTANT V-001` in the original `VALIDATION.md`

## Review assignment

Independently review the originating validation finding, the approved PAPER 01C
contract and scope, the R001 BUILD and VALIDATION receipts, the remediation diff,
and the relevant implementation/test seams. Confirm that:

- R001 fully resolves the permutation-invariance defect for accepted leading-zero
  provider Trade IDs;
- raw provider IDs and exact duplicate semantics remain correct;
- the regression evidence and focused quality gates are credible;
- no unresolved CRITICAL or IMPORTANT finding remains and no out-of-scope
  behavior was introduced.

This is the initial broad review because root validation failed before root review
began.

## Worker Evidence

### Independent review

- The originating IMPORTANT V-001 is resolved by retaining accepted leading-zero
  IDs and extending `_trade_id_sort_key(...)` with the raw provider ID as a final
  tie-breaker after numeric magnitude. This makes ordering total and independent
  of provider array order, including numerically equal IDs such as `"01"` and
  `"1"`.
- The regression test compares both input permutations, asserts normalized
  inventory equality, and verifies that raw IDs remain preserved as `("01", "1")`.
- Exact duplicate raw IDs are still rejected before sorting. No ID acceptance,
  rewriting, deduplication, or merge behavior changed.
- The remediation changes only the OANDA provider inventory ordering seam and
  its focused regression test. No forbidden financial-domain, persistence,
  API/UI, runtime, Risk, execution, reconciliation, activation, broker-mutation,
  or later-PAPER behavior was introduced.

### Checks / evidence

- Focused OANDA suite: **117 passed**.
- Targeted Ruff format and lint checks: **passed**.
- Targeted Pyright: **0 errors, 0 warnings, 0 informations**.
- Tracked and new-file whitespace checks: **passed**.
- CWD/repository root and branch match the dispatch header and remediation
  receipts.

## Findings

No unresolved `CRITICAL` or `IMPORTANT` findings.

## Conclusion

R001 **PASS**. The remediation fully resolves IMPORTANT V-001 while preserving
the approved provider-specific contract and scope. The remediation chain is
merge-ready subject to the parent SoloFlow merge-approval gate.
