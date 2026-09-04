# R001 REVIEW — Reject Explicit Null Trade Account Identity

- **Remediation ID:** `R001`
- **Workstream:** `dogfood-01-protection-trade-identity`
- **Role:** `REVIEW`
- **Branch:** `solo/dogfood-01-protection-trade-identity`
- **CWD:** `/Users/vike/Desktop/atlas`
- **Origin finding:** `I-001` in the immutable originating `REVIEW.md`
- **Status:** `PASS`

## Independent verdict

**PASS.** R001 resolves I-001 with no unresolved CRITICAL or IMPORTANT finding. The
remediation is narrowly limited to distinguishing an absent raw Trade `accountID` key from
an explicitly supplied value in the execution uncertain-entry/protection predicates and the
OANDA reconciliation attribution predicate.

Accountless and explicitly matching-account Trades remain accepted. An explicit `null` or
other supplied mismatch fails closed. In the protection public seam, an explicit-null Trade
cannot pass Trade identity or Stop confirmation, so the result remains
`FILLED_PROTECTION_INCOMPLETE`, the Target remains `NOT_ATTEMPTED`, and no Target PUT follows.
In reconciliation, the same explicit-null Trade is not attributable and remains
unattributable/conflict behavior.

## Review scope and evidence

- Verified repository root/CWD and branch: `/Users/vike/Desktop/atlas`,
  `solo/dogfood-01-protection-trade-identity`; the worktree remains uncommitted with the
  expected workstream changes.
- Independently read the immutable originating `REVIEW.md` I-001 finding, frozen `PLAN.md`
  and `ARCHITECTURE.md`, completed T001 task receipt, root `VALIDATION.md`, root review,
  R001 `BUILD.md`, R001 `VALIDATION.md`, and the complete tracked branch diff plus the
  workstream evidence files.
- The implementation predicates now use key absence versus exact supplied-account equality
  in `backend/integrations/oanda/execution.py` and
  `backend/integrations/oanda/reconciliation.py`. Public-seam regressions cover accountless,
  matching-account, mismatching-account, and explicit-null cases.
- The full branch diff is confined to the approved OANDA execution/protection,
  uncertain-entry, reconciliation, directly affected deterministic tests/fixtures, and
  expected dispatch state. No provider-neutral coordinator, persistence/schema, Strategy,
  Risk, runtime authority, mutation barrier, retry, provider payload, activation, credential,
  or historical evidence changes are present.

## Findings

| Severity | Classification | Type | Finding |
| --- | --- | --- | --- |
| CRITICAL | PRODUCT | DEFECT | None observed. |
| IMPORTANT | REGRESSION | DEFECT | I-001 — **Resolved.** Explicit-null Trade account identity is rejected in all three affected predicates. |
| MINOR | TOOLING | NEW SCOPE | Inherited `ARCHITECTURE.md` metadata still says “Implementation authorization: None” although PLAN/T001 record approval and completion; not an R001 defect and not changed by REVIEW. |
| MINOR | TOOLING | NEW SCOPE | Safe-suite output retains four pre-existing dependency/mark warnings; changed-slice gates are clean. |

No further approved-scope remediation is required.

## Checks and capital-safety boundary

- Explicit-null regressions: **3 passed, 44 deselected**.
- Independently reran the focused execution/protection, uncertain-entry, reconciliation,
  durable/composition, and runtime suites: **196 passed**.
- Independently reran the safe backend suite: **1121 passed, 4 skipped, 115 deselected**;
  four pre-existing warnings were emitted.
- Changed-slice Ruff format: **passed**; Ruff lint: **passed**; Pyright: **0 errors, 0
  warnings, 0 informations**; `git diff --check`: **passed**.
- No broker mutation, credentialed OANDA request, runtime start, activation, historical
  repair, retry, or Git history operation occurred.

## Merge recommendation

Merge approval may proceed for R001. Do not perform broker/runtime/activation activity as a
consequence of this review; the frozen workstream still does not authorize those operations.
