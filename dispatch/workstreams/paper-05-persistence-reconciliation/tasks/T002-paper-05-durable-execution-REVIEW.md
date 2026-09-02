# T002 Review — PAPER 05 Durable Execution Integration

- **Task:** `T002`
- **Workstream:** `paper-05-persistence-reconciliation`
- **Branch:** `solo/paper-05-persistence-reconciliation`
- **Role:** `REVIEW`
- **Status:** `FAIL`
- **Base:** `7a3204c41a394172752ab64b8aeab3f8fbcccf5e`

## Review mandate

Independently review T002's implementation, task receipt, validation artifact,
and actual diff against the frozen PLAN and ARCHITECTURE. Confirm the durable
execution integration is narrow, preserves PAPER 04/Strategy/Risk/provider
semantics, places both permanent claims before mutation, retains normalized
facts and Fill truth, and does not introduce reconciliation/runtime/repair/LIVE
scope. Pass requires zero unresolved CRITICAL or IMPORTANT findings.

No implementation, test, migration, or prior evidence artifact may be modified
from the REVIEW role. No broker calls or credentials are permitted.

## Worker Evidence

Populate this artifact once with the independent review receipt, judgment,
findings, and evidence.

## Independent judgment

T002 does not pass. The normal successful path has the intended durable ordering,
but a protection path that stops before the Take Profit mutation records a false
provider observation.

### Positive review conclusions

- The durable coordinator accepts only `PaperStrategyEvaluationReceipt` and uses
  `receipt.evaluation.decision`. The receipt-producing boundary verifies the
  persisted StrategyVersion and validated parameters, and the repository verifies
  those facts again before the ENTRY claim.
- `PaperExecutionApplication.prepare()` calls fresh Risk exactly once;
  `PaperRiskAuthoritySnapshot.from_evaluation()` serializes that same evaluation
  without a second Risk call.
- The attempt plus permanent ENTRY claim is committed before the entry POST. The
  pre-PUT callback commits Fill/confirmed Stop/actual target plus the permanent
  TAKE_PROFIT claim before the PUT.
- The normal OANDA path preserves PAPER 04 entry, Fill, actual-fill target,
  precision, protection, and non-retrying semantics. R001's repository identity
  and protection attribution checks remain in force. Existing focused PAPER/OANDA
  regressions are green.
- Existing-attempt loading and permanent claims prevent duplicate, restart, and
  uncertain paths from obtaining another POST/PUT permit. The repository remains
  separate from historical Experiment persistence and no forbidden runtime,
  reconciliation coordinator, polling, repair, close/reduce, LIVE, credential, or
  activation scope was added by T002.

## Findings

### IMPORTANT — PRODUCT — protection-only read is persisted as a Take Profit mutation response

`PaperDurableExecutionApplication.execute()` unconditionally persists the final
`completed` result with `_final_read_kind(completed)`. Any non-`FILLED_PROTECTED`
result is classified as `TAKE_PROFIT_MUTATION_RESPONSE`, and when no Take Profit
claim exists it is linked to the ENTRY claim. However,
`OandaPracticeProtectionCompletion.complete()` returns before the
`before_take_profit` callback for a missing/unprovable Trade, Stop mismatch,
invalid target geometry, or unrepresentable target; no PUT has occurred and no
TAKE_PROFIT claim exists.

An independent deterministic probe with the entry Fill followed by a missing
Trade produced `FILLED_PROTECTION_INCOMPLETE` and no PUT, but the durable
observations were:

```text
ENTRY_MUTATION_RESPONSE             claim=ENTRY
TAKE_PROFIT_MUTATION_RESPONSE       claim=ENTRY, provider_type=TAKE_PROFIT_ORDER,
                                    provider_order_id=<entry order id>
```

This is a false provider fact and incorrect claim attribution. It violates the
frozen append-only normalized-observation/read-kind boundary and omits the
actual pre-PUT `TRADE_DETAIL` evidence. It can mislead later reconciliation and
means the durable ledger is not an auditable record of what broker read or
mutation occurred. The coordinator must retain a correctly typed Trade-detail
observation for the protection read, and must not create a Take Profit mutation
observation unless the dependent PUT was actually reached (with uncertainty
represented without inventing provider facts).

No implementation changes were made from REVIEW.

## Review Evidence

- Actual working-tree source/diff review covered the T002 coordinator,
  preparation/callback seams, OANDA mutation/protection normalization, receipt
  producer, provider-neutral repository, models/migration, and focused tests.
- Focused deterministic suite: **66 passed**.
- Broad safe backend suite: **931 passed, 4 skipped, 97 deselected**; four
  existing warnings.
- Scoped Ruff: passed. Scoped Pyright: **0 errors**. `git diff --check`:
  passed.
- T002 validation evidence records **9 passed** dedicated PostgreSQL repository
  tests and Alembic head/check success in the owned validation schema; the
  public-schema reset limitation remains an environment/tooling concern from
  T001/R001.
- No broker call, credential, activation, runtime, or capital-capable action was
  used. The finding probe used only deterministic in-process fakes.

## Worker Evidence Receipt

ROLE: REVIEW
STATUS: FAIL
ARTIFACT: `dispatch/workstreams/paper-05-persistence-reconciliation/tasks/T002-paper-05-durable-execution-REVIEW.md`
FILES CHANGED: this artifact only
CHECKS / EVIDENCE: Independent source/diff review; focused 66 passed; broad safe backend 931 passed, 4 skipped, 97 deselected; scoped Ruff/Pyright and diff checks passed; deterministic no-Trade probe reproduced the misclassified observation; T002/T001/R001 PostgreSQL and migration evidence reviewed.
FINDINGS / CONCERNS: One unresolved IMPORTANT PRODUCT finding: a no-PUT protection-only path is persisted as `TAKE_PROFIT_MUTATION_RESPONSE` against the ENTRY claim and lacks the actual `TRADE_DETAIL` observation. No forbidden scope or external/capital action occurred.
