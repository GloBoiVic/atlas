# T006 — Runtime orchestration

- **Status:** `DONE`
- **Role:** `BUILD`
- **Workstream:** `paper-06-runtime-activation`
- **Branch:** `solo/paper-06-runtime-activation`
- **Depends on:** T002, T003, T004, T005
- **Owned artifact:** this file

## Objective

Implement startup recovery, fixed 15-second one-frontier-per-tick orchestration, evaluation/refusal/opening branches, same-process dependent protection, STOP fencing, and read-only restart recovery.

## Required boundaries

- No activation or broker call merely from process liveness; idle with no activation.
- Reconcile committed claims on restart through bounded GET-only P05 recovery; never POST/PUT or create missing claims after restart.
- STOP before claim prevents entry; a claim linearized before STOP may complete only its already-authorized same-process entry/protection chain while ownership remains valid; no later cycles.
- Owner loss fences all new authority; UNKNOWN, UNRESOLVED, CONFLICT, protection-incomplete, unattributed exposure, and persistence uncertainty fail closed.
- Preserve FILLED_PROTECTED as historical truth and never infer current flatness from it or LIFECYCLE_ADVANCED.

## Evidence required

- Full deterministic state-transition matrix, fault injection at every capital boundary, restart and STOP/claim races, no automatic catch-up, and no real mutation.

## Current implementation

- Added the fixed-cadence `PaperRuntimeOrchestrator` with explicit owner acquisition, startup lifecycle handling, one-frontier-per-tick evaluation, distinct entry gating, STOP fencing, and bounded fatal/error outcomes.
- Added restart handling for committed P05 claims using the existing reconciliation seam only; restart does not submit or recreate mutation claims.
- Added the caller-owned P05 mutation guard so owner loss fences ENTRY and dependent Take Profit mutation boundaries.
- Added focused tests for idle startup, fixed cadence/no catch-up, bounded result serialization, and owner-loss entry fencing.

The deterministic orchestration slice and its matching BUILD evidence are complete. Cross-seam PostgreSQL concurrency/migration completion remains assigned to T008.

## Checks so far

- `uv run pytest -m "not integration and not external"` — 1019 passed, 4 skipped, 104 deselected.
- Focused Ruff format/check and Pyright checks for the changed runtime/orchestration/test slice — passed.

## Completion receipt

Implemented and verified the runtime orchestration boundary:

- startup acquires the single owner, remains idle without an activation, validates the exact local Strategy registry identity, performs fresh/bootstrap and same-activation recovery checks, and requires a flat/no-pending bootstrap account;
- ticks process at most one completed frontier, wait and retry transient pre-cycle observations, reject duplicate frontiers, and fail closed on semantic frontier/account state errors;
- Strategy evaluation remains read-only for known attributable open exposure, while opening requires a fresh flat/no-pending gate and the caller-owned PAPER 05 attempt/ENTRY claim transaction;
- STOP fences account/cycle/ENTRY work, owner loss fences dispatch, unsupported decisions retain their receipt evidence before blocking, uncertain execution blocks without resolution, and terminal cycle resolution failures fail closed;
- restart recovery performs bounded reconciliation only after committed claims, requires definite reconciliation evidence, and never replays ENTRY or Take Profit mutation.

### Files changed

- `backend/runtime/orchestration.py`
- `backend/runtime/cycles.py`
- `backend/tests/runtime/test_runtime_orchestration.py`
- `dispatch/workstreams/paper-06-runtime-activation/tasks/T006-paper-06-runtime-activation.md`

### Checks and evidence

- Focused runtime/PAPER tests passed, including deterministic FLAT/LONG evaluation, duplicate/frontier waits, STOP/claim ordering, owner loss before claim/dispatch, unsupported actions, execution uncertainty, persistence fencing, and read-only restart recovery.
- Full non-integration/non-external backend suite: `1019 passed, 4 skipped, 104 deselected`.
- Changed-slice Ruff format/check: passed.
- Changed-slice Pyright: `0 errors, 0 warnings, 0 informations`.
- `git diff --check`: passed.
- No real OANDA calls, PAPER activation, credentials, or broker mutation were used. PostgreSQL migration/concurrency evidence remains T008 scope.
