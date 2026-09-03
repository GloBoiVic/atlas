# T004 — Frontier, cycles, and Strategy-state authority

- **Status:** `DONE`
- **Role:** `BUILD`
- **Workstream:** `paper-06-runtime-activation`
- **Branch:** `solo/paper-06-runtime-activation`
- **Depends on:** T001, T003
- **Owned artifact:** this file

## Objective

Implement immutable completed-frontier consumption, cycle reservation/evidence, fresh bootstrap, same-activation exact state resume, and strict separation of Strategy evaluation eligibility from entry eligibility.

## Required boundaries

- Consume the existing provider-native completed EUR/USD M15 frontier exactly once per evaluation key/frontier; no forming/future bars, aggregation, interpolation, or automatic catch-up.
- Bind exact Strategy identity, parameter fingerprint, state_before/after, FinancialPositionState, bounded account evidence, and receipt identity to each cycle.
- Allow known attributable LONG/SHORT open exposure to advance read-only Strategy state without Risk or entry authority; require fresh FLAT/zero-pending P05 authority for openings.
- Fresh activation bootstraps null state; same non-terminal activation resumes only exact durable state; terminal sessions never donate state.
- Retry only transient pre-claim reads; block on semantic contradictions, missed frontier, unsafe durable state, or unsupported methodology action.

## Evidence required

- Deterministic matrix coverage for FLAT, known LONG/SHORT, duplicate/future/forming/missed frontiers, retryable reads, unsupported actions, fresh bootstrap, restart resume, and no cross-session import.

## Completion receipt

Implemented the immutable frontier handoff and runtime cycle/Strategy-state
authority.  The runtime now consumes one validated completed native M15
frontier without rereading the provider, enforces exact next-frontier
continuity, binds bounded account evidence and exact activation state to cycle
identity, and prevents unattributed exposure or non-flat capital actions from
reaching an execution path.  New sessions remain fresh-bootstrap sessions;
same-activation state resumes only from its exact durable frontier/state
projection.

### Files changed

- `backend/paper/current_analytical_frontier.py`
- `backend/paper/strategy_evaluation.py`
- `backend/paper/__init__.py`
- `backend/runtime/cycles.py`
- `backend/runtime/__init__.py`
- `backend/runtime/persistence_contracts.py`
- `backend/persistence/runtime_repository.py`
- `backend/tests/paper/test_strategy_evaluation.py`
- `backend/tests/runtime/test_runtime_cycles.py`

### Checks and evidence

- Focused frontier/Strategy/runtime tests after the final repository guard patch:
  `43 passed, 2 skipped`.
- Full non-integration/non-external backend suite: `994 passed, 4 skipped, 103 deselected`.
- Changed-slice Ruff check and format check: passed.
- Changed-slice Pyright: `0 errors, 0 warnings, 0 informations`.
- `git diff --check`: passed.
- PostgreSQL runtime integration tests were discovered but skipped because
  `ATLAS_TEST_DATABASE_URL` is not configured in this environment.
- No OANDA calls, credentials, PAPER activation, or broker mutation were used.

### Concerns / handoff

- T005 must use `PaperRuntimeCycleAuthority.persist_evaluation` or the
  equivalent caller-owned repository boundary so cycle/state/attempt/claim
  atomicity remains intact.
- T006 must treat `PaperRuntimeFrontierGap` and semantic state/account errors as
  fail-closed runtime outcomes, while handling transient provider reads before
  cycle reservation as retryable waits.
