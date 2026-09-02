# R002 Review — PAPER 05 Observation Attribution

- **Remediation ID:** `R002`
- **Workstream:** `paper-05-persistence-reconciliation`
- **Branch:** `solo/paper-05-persistence-reconciliation`
- **Role:** `REVIEW`
- **Status:** `PASS`
- **Origin:** T002 review, false pre-PUT mutation observation finding

## Review mandate

Independently reviewed R002 against the frozen `PLAN.md` and
`ARCHITECTURE.md`, the failed T002 review, R002 BUILD/VALIDATION packets, the
actual working-tree diff, and current source. No implementation, test,
migration, fixture, or prior artifact was modified. No broker call or
credential was used.

## Independent judgment

R002 passes. The original IMPORTANT PRODUCT defect is resolved.

- For missing/unprovable Trade and Stop-mismatch paths, the OANDA protection
  seam invokes `after_trade_detail` before returning
  `FILLED_PROTECTION_INCOMPLETE`. The durable coordinator appends
  `TRADE_DETAIL` / `TRADE` with `mutation_claim_id=None`; it does not append a
  fabricated `TAKE_PROFIT_MUTATION_RESPONSE`.
- The final durable projection deliberately supplies no observation kind when
  no TAKE_PROFIT claim exists. Thus the normalized provider observation remains
  separate from the Atlas outcome projection.
- On the valid protected path, the pre-PUT callback commits the permanent
  `TAKE_PROFIT` claim, then the single PUT is reached, then the post-mutation
  callback appends `TAKE_PROFIT_MUTATION_RESPONSE` linked to that claim. The
  final Trade detail remains separately typed and claim-associated.
- On uncertain PUT transport, the claim remains permanent, no response fact is
  synthesized, the result remains protection-incomplete, and an existing
  attempt cannot reacquire a claim or resubmit. Entry claim ordering and
  restart/no-resubmit behavior remain intact.
- Existing PAPER 04 entry/Fill/protection, actual-fill target, precision,
  non-retrying, Strategy receipt, single fresh Risk evaluation, and R001
  attribution semantics remain unchanged. The R002 diff is limited to the
  callback/result plumbing and its deterministic regression coverage; no
  reconciliation, runtime, repair, activation, LIVE, schema, or broker scope
  was added.

## Findings

No unresolved CRITICAL, IMPORTANT, or MINOR PRODUCT/REGRESSION findings remain.

### MINOR — TOOLING / environment limitation

The dedicated PostgreSQL repository rerun was unavailable without
`ATLAS_TEST_DATABASE_URL` and skipped all 9 tests. R002 VALIDATION reviewed the
prior dedicated PostgreSQL evidence; this is an environment limitation, not an
R002 defect.

## Review Evidence

- Independent focused suite: **53 passed** across durable execution,
  protection completion, PAPER 04 composition/contracts, persistence
  contracts, and Strategy evaluation.
- Independent broad safe backend suite:
  **933 passed, 4 skipped, 97 deselected**; four pre-existing warnings.
- Changed-slice Ruff check/format: passed; Pyright: **0 errors**;
  `git diff --check`: passed.
- Migration head/check evidence and R002 VALIDATION evidence reviewed;
  deterministic missing-Trade/Stop-mismatch probes prove zero PUT calls,
  nullable claim attribution, and correct observation kind/object. Protected
  and uncertain PUT probes prove claim ordering, one-call behavior, and no
  fabricated response.

## Worker Evidence Receipt

ROLE: REVIEW
STATUS: PASS
ARTIFACT: `dispatch/workstreams/paper-05-persistence-reconciliation/remediations/R002-paper-05-observation-attribution/REVIEW.md`
FILES CHANGED: this artifact only
CHECKS / EVIDENCE: Independent source/diff review; focused 53 passed; broad safe backend 933 passed, 4 skipped, 97 deselected; scoped Ruff/Pyright and diff checks passed; migration head and revision tests passed; R002 deterministic no-PUT/protected/uncertain evidence reviewed.
FINDINGS / CONCERNS: No unresolved CRITICAL or IMPORTANT findings. One MINOR tooling limitation: dedicated PostgreSQL rerun skipped for missing `ATLAS_TEST_DATABASE_URL`; no real OANDA mutation, credential, activation, runtime, or capital-capable action occurred.
