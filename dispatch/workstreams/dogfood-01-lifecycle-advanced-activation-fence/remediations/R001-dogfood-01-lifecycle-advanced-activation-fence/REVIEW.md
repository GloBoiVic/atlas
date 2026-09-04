# REVIEW — Remediation R001 — Dogfood 01 Lifecycle-Advanced Activation Fence

ROLE: REVIEW  
WORKSTREAM: dogfood-01-lifecycle-advanced-activation-fence  
BRANCH: solo/dogfood-01-lifecycle-advanced-activation-fence  
CWD: /Users/vike/Desktop/atlas  
TASK: R001  
OWNED_ARTIFACT: dispatch/workstreams/dogfood-01-lifecycle-advanced-activation-fence/remediations/R001-dogfood-01-lifecycle-advanced-activation-fence/REVIEW.md  
SPECIALIST_SKILLS: tdd

## Verdict

**FAIL — the originating IMPORTANT fail-open is not fully closed.** Two IMPORTANT
product findings remain in the approved R001 classifier scope.

## Findings

1. **IMPORTANT — contradictory known terminal findings remain allowed.**
   `_is_complete_lifecycle_fill()` rejects the contradiction set, but that set omits
   `ENTRY_REJECTED` and `ENTRY_CANCELLED`. With otherwise complete Fill and applied-run
   evidence, `TRADE_LIFECYCLE_ADVANCED` combined with either code returns `True` from
   `is_new_session_safe_attempt()`. These are incompatible entry-terminal conclusions
   under the durable PAPER rule that Fill plus reject/cancel evidence is conflicted and
   must fail closed. `ENTRY_FILLED` and `ENTRY_READBACK_NOT_FOUND` can be legitimate
   discovery/fallback findings; the issue is accepting reject/cancel (and combinations
   containing them) merely because they are known codes. The new-session classifier can
   therefore still grant a new activation from contradictory durable evidence.

2. **IMPORTANT — applied-run read metadata is not checked narrowly against the
   provider-neutral reconciliation contract.** The coordinator accepts a read budget only
   through `MAX_RECONCILIATION_READS` (8), and emits
   `non_atomic_read_set == (read_count > 1)`. The classifier checks only positive
   `read_budget` plus `read_count <= read_budget`, and never checks `non_atomic_read_set`.
   Independent probes show complete evidence with `read_budget=9`, with
   `read_count=1/non_atomic_read_set=True`, and with
   `read_count=2/non_atomic_read_set=False` all classify safe. The existing ORM/model
   shape permits these contradictory or unsupported durable values. This remains a
   malformed applied reconciliation run able to pass the activation fence.

## What is closed and preserved

- Normal complete Fill plus applied `LIFECYCLE_ADVANCED` evidence remains eligible.
- Zero/invalid reads, missing/unknown/duplicate/conflicting findings, non-empty or
  malformed diagnostics, durable block codes, mismatched IDs/versions/timestamps/outcomes,
  and incomplete Fill facts fail closed in the added tests.
- The Dogfood UUID is not a production exception; synthetic UUID equivalence remains true.
- `is_unsafe_paper_attempt()` and `_recover_interrupted()` remain on the strict
  same-attempt predicate. The incomplete lifecycle-ended outcome remains unsafe there.
- The R001 delta is confined to `runtime_repository.py` and its classifier tests. No
  schema/migration, provider-neutral reconciliation, historical-data, activation-lifecycle,
  startup, P05/Risk, owner/claim, restart/no-retry, or mutation implementation was added;
  the inherited T001 paths and their focused regressions remain unchanged by R001.

## Test quality and scope

The 17 added malformed-evidence cases do not cover the two omitted known terminal findings,
the read-budget ceiling, or the `non_atomic_read_set` relation. The classifier tests use
`SimpleNamespace` rows, so they also do not exercise the ORM-loaded run shape. The lack of
dedicated PostgreSQL integration and an end-to-end accepted POST/startup test is LOW, not
the reason for failure.

## Checks / evidence

- Focused runtime/orchestration/completion-cross-seam/reconciliation suite: **174 passed**.
- Changed-slice Ruff format/check: **passed**; changed implementation Pyright:
  **0 errors, 0 warnings, 0 informations**.
- `uv run alembic check`: **no new upgrade operations detected**; `git diff --check`:
  **passed**.
- Independent classifier probes reproduced safe results for the contradictory finding
  combinations and unsupported/inconsistent read metadata described above.
- No credentials, runtime start, activation, Dogfood 02 action, provider request, historical
  data change, or broker mutation was performed.

## SoloFlow receipt

ROLE: REVIEW  
STATUS: FAIL  
ARTIFACT: `dispatch/workstreams/dogfood-01-lifecycle-advanced-activation-fence/remediations/R001-dogfood-01-lifecycle-advanced-activation-fence/REVIEW.md`  
FILES CHANGED: this artifact only  
CHECKS / EVIDENCE: 174 focused tests passed; changed-slice Ruff/Pyright, Alembic, and diff checks passed; independent probes reproduced two remaining fail-open classes.  
FINDINGS / CONCERNS: **IMPORTANT** contradictory `ENTRY_REJECTED`/`ENTRY_CANCELLED` combinations remain accepted; **IMPORTANT** read-budget and `non_atomic_read_set` fields are not constrained to provider-neutral output; LOW PostgreSQL/end-to-end coverage limitations.
