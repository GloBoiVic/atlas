# T002 — PAPER 05 Durable Execution Integration

- **Status:** `DONE_WITH_CONCERNS`
- **Role:** `BUILD`
- **Workstream:** `paper-05-persistence-reconciliation`
- **Branch:** `solo/paper-05-persistence-reconciliation`
- **Base:** `7a3204c41a394172752ab64b8aeab3f8fbcccf5e`
- **Owned artifact:** this file
- **Depends on:** T001 persistence foundation and R001 attribution remediation; frozen `PLAN.md` and `ARCHITECTURE.md`

## Objective

Integrate the durable PAPER ledger with the existing one-shot PAPER 04
execution composition without changing Strategy, Risk, Fill, target, precision,
or OANDA provider semantics.

## In scope

- Add the narrowest provider-neutral durable PAPER execution coordinator or
  explicit durable mode that accepts the exact verified Strategy evaluation
  receipt, one fresh Risk authority snapshot, and the existing immutable PAPER
  04 instruction.
- Persist the attempt and exact immutable instruction/Strategy/Risk/provenance
  evidence, then commit the permanent `ENTRY` claim before invoking the existing
  non-retrying OANDA entry POST.
- Persist normalized mutation/readback observations before applying the existing
  `PaperExecutionResult` outcome projection. Preserve proven Fill facts even
  when protection is incomplete or later reads are uncertain.
- After a proven Fill and confirmed Stop prerequisite, derive the actual target
  from the actual Fill plus frozen Strategy target geometry without rounding;
  commit the permanent `TAKE_PROFIT` claim before the dependent non-retrying
  PUT, then persist response/readback facts and final protected/incomplete
  conclusion.
- Ensure process restart, duplicate invocation, claim conflict, and database
  commit failure cannot acquire a second POST/PUT permit. A committed claim is a
  possible mutation, not proof of HTTP dispatch.
- Keep provider-specific normalization in the existing OANDA integration seam;
  the repository remains provider-neutral. Extend only the minimal callback or
  result plumbing needed to persist normalized facts around the two mutation
  points.
- Add deterministic public-seam tests using fakes/MockTransport for ordering,
  exactly-once fresh Risk evaluation, pre-mutation commits, uncertain transport,
  Fill retention, target derivation, claim conflicts, and no-resubmit behavior.

## Explicit non-goals

- No reconciliation coordinator or transaction-ID-range polling; that is a
  later task.
- No runtime loop, scheduler, activation, background worker, recovery mutation,
  retry, protection repair, cancel/close/reduce, LIVE, real credentials, or
  capital-capable broker action.
- No Strategy methodology, Risk policy, historical Experiment persistence, or
  frozen PAPER 04 outcome semantics changes.

## Completion requirements

1. The durable path performs exactly one `evaluate_paper_risk(...)` for the
   fresh mutation decision and persists that same authority/evidence.
2. The attempt row and `ENTRY` claim are committed before entry POST; target
   claim is committed before dependent PUT.
3. The durable result and normalized provider facts are distinguishable, and
   all proven Fill facts remain immutable and visible.
4. No uncertain path resubmits entry or Take Profit, and no claim expires,
   transfers, or reacquires.
5. Existing PAPER 04 tests remain green and no real provider call is made.
6. Focused tests, relevant static checks, and the complete task receipt below
   pass before advancing to validation.

## Worker Evidence

Populate on completion with:

```text
ROLE: BUILD
STATUS: DONE | BLOCKED | DONE_WITH_CONCERNS
ARTIFACT: this file
FILES CHANGED: <paths>
CHECKS / EVIDENCE: <brief result>
FINDINGS / CONCERNS: <brief result>
```

## Completion Receipt

ROLE: BUILD
STATUS: DONE_WITH_CONCERNS
ARTIFACT: `dispatch/workstreams/paper-05-persistence-reconciliation/tasks/T002-paper-05-durable-execution.md`
FILES CHANGED: `backend/paper/durable_execution.py`, `backend/paper/execution_application.py`, `backend/paper/__init__.py`, `backend/integrations/oanda/execution.py`, `backend/tests/paper/test_durable_execution.py`
CHECKS / EVIDENCE:

- Focused durable/PAPER/OANDA tests: `45 passed`.
- Full safe backend suite: `931 passed, 4 skipped, 97 deselected`.
- Changed-slice Ruff check/format: passed.
- Changed-slice Pyright: `0 errors`.
- PostgreSQL repository test: `9 skipped` because no dedicated `ATLAS_TEST_DATABASE_URL` was configured.
- `git diff --check`: passed.

FINDINGS / CONCERNS: Durable execution now consumes the verified Strategy receipt, evaluates fresh Risk once, commits ENTRY and TAKE_PROFIT barriers before the existing non-retrying mutations, and persists normalized facts before projections. Restart, duplicate, uncertain, and pre-mutation commit-failure paths do not resubmit. No reconciliation, transaction-range polling, runtime, activation, credentials, or real broker mutation was added. PostgreSQL integration evidence remains the T001 dedicated-database evidence; T002's repository integration test was skipped in this environment.
