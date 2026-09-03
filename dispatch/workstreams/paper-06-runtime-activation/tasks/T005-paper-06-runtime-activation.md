# T005 — PAPER 05 caller-owned transaction seam

- **Status:** `DONE`
- **Role:** `BUILD`
- **Workstream:** `paper-06-runtime-activation`
- **Branch:** `solo/paper-06-runtime-activation`
- **Depends on:** T001, T004
- **Owned artifact:** this file

## Objective

Refactor only the narrow PAPER 05 transaction ownership required for the runtime atomic boundary: cycle evidence, state_after, immutable P05 attempt, and permanent ENTRY claim before broker mutation.

## Required boundaries

- Preserve PAPER 05 Risk evaluation, attempt semantics, claim semantics, OANDA translation, broker mutation, Fill/protection, observations, and reconciliation as the sole existing authority.
- Add a caller-owned transaction seam; do not duplicate P05 logic in runtime.
- Preserve existing P04/P05 one-shot public behavior and cover any compatibility change with regression tests.
- Ensure rollback leaves no partial runtime/P05 authority and no broker mutation can occur before the atomic commit.

## Evidence required

- Focused P05 regression tests plus transaction rollback/commit evidence, fresh Risk exactly once, and no real provider mutation.

## Completion receipt

Implemented the narrow caller-owned PAPER 05 transaction seam required by the
runtime atomic opening boundary.  Runtime callers can now prepare fresh P05
Risk/attempt evidence, stage the immutable attempt and permanent ENTRY claim in
their own transaction, commit alongside cycle/state evidence, and only then
dispatch the existing one-shot P05 mutation/protection chain.

### Files changed

- `backend/persistence/paper_execution_repository.py`
- `backend/paper/durable_execution.py`
- `backend/paper/__init__.py`
- `backend/tests/paper/test_durable_execution.py`
- `backend/tests/integration/test_paper_execution_repository.py`
- `dispatch/workstreams/paper-06-runtime-activation/tasks/T005-paper-06-runtime-activation.md`

### Checks and evidence

- Focused PAPER execution tests: `20 passed`.
- Full non-integration/non-external backend suite: `996 passed, 4 skipped, 104 deselected`.
- Changed-slice Ruff check/format check: passed.
- Changed-slice Pyright: `0 errors, 0 warnings, 0 informations`.
- `git diff --check`: passed.
- Dedicated PostgreSQL integration file was collected but skipped because
  `ATLAS_TEST_DATABASE_URL` is not configured in this environment; the added
  integration test covers rollback of both attempt and ENTRY claim when run.
- Deterministic fakes verified Risk is evaluated once, no provider mutation is
  reached before the caller-owned claim transaction, and existing one-shot
  P05 entry/protection behavior remains covered.
- No OANDA calls, credentials, PAPER activation, or broker mutation were used.

### Concerns / handoff

- T006 must commit `persist_entry_claim(...)` in the same caller-owned
  transaction as cycle/state evidence and must invoke `submit_claimed_entry(...)`
  only after that commit and a current owner guard.
