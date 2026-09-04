# R001 — Reject Explicit Null Trade Account Identity

- **Remediation ID:** `R001`
- **Status:** `DONE`
- **Role:** `BUILD`
- **Origin finding:** `I-001` in `dispatch/workstreams/dogfood-01-protection-trade-identity/REVIEW.md`
- **Finding severity:** `IMPORTANT`
- **Classification:** `REGRESSION`; approved-scope `DEFECT`
- **Related original task(s):** `T001`

## Approved requirement or invariant violated

The frozen execution and reconciliation contracts permit an omitted raw Trade `accountID`
because account authority is proven by the account-scoped reader, but require any supplied
Trade `accountID` to equal the already-proven configured/context account. An explicit
`{"accountID": null}` is supplied malformed identity and must fail closed. The T001
implementation incorrectly treats explicit null as omission using `in (None, account_id)`.

## Exact remediation outcome

Distinguish a missing `accountID` key from an explicitly supplied value in all affected
execution and reconciliation Trade predicates. Accept only key absence or an exact matching
account; reject explicit null and every other mismatch. Add public-seam regression coverage
for explicit null in uncertain-entry, protection/target authorization, and reconciliation
attribution while retaining accountless real-shape success and matching-account success.

## Affected implementation seams

- `backend/integrations/oanda/execution.py` uncertain-entry Trade matching and protection
  Trade matching.
- `backend/integrations/oanda/reconciliation.py` account-scoped Trade attribution.
- Directly affected public-seam deterministic tests only.

## Explicit out-of-scope items

- No changes to the frozen PLAN or ARCHITECTURE, provider-neutral reconciliation coordinator,
  persistence/schema, Strategy, Risk, runtime authority, mutation barriers, retry semantics,
  provider payload mapping, or historical Dogfood 01 evidence.
- No new recovery, mutation, Stop repair, Target retry, credentialed OANDA request, runtime
  start, activation, or Git operation.

## Regression evidence required

- Accountless real-shape Trade remains valid through execution/protection and reconciliation.
- Explicit matching Trade account remains valid.
- Explicit null Trade account fails closed in uncertain-entry, protection (no Target PUT),
  and reconciliation (unattributable/conflict).
- Existing focused and relevant durable/runtime/barrier checks remain green.
- Format, lint, type, and diff checks pass for the changed slice.

## Worker Evidence

Implemented the approved I-001 remediation without changing the frozen architecture or
provider-neutral behavior.

- Execution uncertain-entry and protection Trade predicates now accept an omitted raw
  `accountID` or an exact configured-account value, while explicit `null` and every other
  supplied mismatch fail closed.
- OANDA reconciliation Trade attribution uses the same omission-versus-supplied identity
  distinction; accountless and explicitly matching account-scoped Trades remain attributable,
  while explicit `null` and mismatches remain unattributable/conflict.
- Added public-seam regressions for uncertain-entry, protection/target authorization, and
  reconciliation, including accountless, matching-account, explicit-null, and mismatch cases.
- No provider payload mapping, mutation, retry, persistence/schema, Strategy, Risk, runtime
  authority, coordinator, or historical evidence changes were made.

### Checks

- TDD red phase: the three new explicit-null regressions failed before the predicate fix.
- Focused execution/protection, uncertain-entry, reconciliation, durable/composition, and
  runtime checks: **189 passed**.
- Changed-slice Ruff format: **passed**; Ruff lint: **passed**; Pyright: **0 errors / 0
  warnings / 0 informations**.
- `git diff --check`: **passed**.
- No credentialed OANDA mutation, runtime start, activation, retry, historical repair, or
  Git history operation was performed.

### R001 files changed

- `backend/integrations/oanda/execution.py`
- `backend/integrations/oanda/reconciliation.py`
- `backend/tests/integrations/test_oanda_entry_mutation.py`
- `backend/tests/integrations/test_oanda_protection_completion.py`
- `backend/tests/integrations/test_oanda_reconciliation.py`

Concerns: none requiring architecture escalation. Frozen PLAN, ARCHITECTURE, T001 receipt,
root VALIDATION/REVIEW, ACTIVE state, and completed evidence artifacts were not modified.
