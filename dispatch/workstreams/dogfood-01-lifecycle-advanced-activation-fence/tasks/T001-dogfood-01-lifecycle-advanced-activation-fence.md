# Task T001 — Dogfood 01 Lifecycle-Advanced Activation Fence

- **Workstream:** `dogfood-01-lifecycle-advanced-activation-fence`
- **Role:** `BUILD`
- **Status:** `DONE_WITH_CONCERNS`
- **Branch:** `solo/dogfood-01-lifecycle-advanced-activation-fence`
- **Base SHA:** `bc53f70d0afdcbbc728d54d48df5370da0f2238e`
- **Owned artifact:** `dispatch/workstreams/dogfood-01-lifecycle-advanced-activation-fence/tasks/T001-dogfood-01-lifecycle-advanced-activation-fence.md`

## Approved outcome

Implement only the frozen PLAN.md and ARCHITECTURE.md narrow semantic new-session history
recovery seam. Keep historical Dogfood 01 truth unchanged and preserve all existing
fail-closed, owner/generation, frontier, STOP, claim, no-retry, startup, P05, and mutation
barriers.

## Required implementation

- Add a separate semantic new-session history classifier; do not hardcode any incident UUID.
- Keep `is_unsafe_paper_attempt()` and strict interrupted-claim/same-attempt recovery unchanged.
- Permit a new explicitly approved `FRESH_BOOTSTRAP` activation past local history only for
  coherent lifecycle-ended incomplete Fill evidence with applied `LIFECYCLE_ADVANCED`
  reconciliation, while preserving existing safe terminal cases.
- Require complete, coherent durable Fill identity and linked applied reconciliation evidence;
  malformed, missing, unsupported, unresolved, conflicted, or contradictory history blocks.
- Ensure any blocker in the configured account blocks the new session.
- Keep activation POST provider-free and create only a new `REQUESTED` activation. Never revive
  a prior `BLOCKED` activation or donate prior Strategy state.
- Keep fresh startup capability, exact account identity, coherent FLAT, zero open Trades,
  zero Positions, and zero pending Orders authoritative before `RUNNING`.
- Keep fresh P05 account/instrument/pricing reads and one fresh Risk evaluation independent
  before any ENTRY claim or mutation.
- Make no schema/migration or provider-neutral reconciliation semantic change. STOP and report
  if the frozen architecture cannot be implemented without one.

## Required evidence

Add deterministic focused tests covering the complete truth table, strict predicate unchanged,
synthetic future UUID equivalence/no hardcoded incident behavior, coherent durable qualifiers,
malformed/missing evidence, multi-attempt blocking, provider-free POST, blocked non-revival,
fresh startup/current-account gates, independent P05/Risk, owner/claim/restart/no-retry
regressions, and mutation spies proving zero provider mutations during this remediation.

Run focused tests first, then report the appropriate safe Critical backend checks and
`git diff --check`. Do not start atlas-runtime, create/retry Dogfood 02, use credentials, or
perform credentialed OANDA validation or mutation.

## Completion receipt

On completion, update this task only with the BUILD receipt below. Do not edit completed
planning, validation, or review artifacts.

### Worker Evidence

ROLE: BUILD
STATUS: DONE_WITH_CONCERNS
ARTIFACT: `dispatch/workstreams/dogfood-01-lifecycle-advanced-activation-fence/tasks/T001-dogfood-01-lifecycle-advanced-activation-fence.md`

FILES CHANGED:

- `backend/persistence/runtime_repository.py`
- `backend/runtime/activation.py`
- `backend/runtime/orchestration.py`
- `backend/tests/runtime/test_runtime_activation.py`
- `backend/tests/runtime/test_runtime_orchestration.py`

IMPLEMENTATION:

- Added the semantic `is_new_session_safe_attempt()` classifier and repository
  `has_new_session_blocker()` account-wide query.
- Lifecycle-ended `FILLED_PROTECTION_INCOMPLETE + LIFECYCLE_ADVANCED` is accepted
  only with complete Fill facts, a linked applied coherent reconciliation run, and
  no reconciliation block code; all other unknown, malformed, unsupported, or
  contradictory states remain blockers.
- Activation creation and fresh account observation use the new classifier.
  `is_unsafe_paper_attempt()` and interrupted-claim recovery remain unchanged.
- No schema/migration, provider-neutral reconciliation, historical row, activation
  revival, provider mutation, credential, runtime-start, or Dogfood 02 change was made.

CHECKS / EVIDENCE:

- Focused runtime/reconciliation suite: `157 passed`.
- Safe backend suite: `1154 passed, 4 skipped, 115 deselected`.
- Changed-slice Ruff check and format check: passed.
- Changed implementation Pyright: `0 errors, 0 warnings, 0 informations`.
- `uv run alembic check`: no new upgrade operations detected.
- `git diff --check`: passed.
- Regression tests cover the new-session matrix, strict predicate, coherent durable
  qualifier, synthetic/non-incident UUID equivalence, account-wide blockers, and the
  fresh observation seam without strict recovery fallback.

FINDINGS / CONCERNS:

- Repository-wide Ruff format/lint and Pyright remain non-clean due to pre-existing
  unrelated findings outside this task; the changed implementation slice is clean.
- No PostgreSQL integration or credentialed/provider validation was run. No provider
  mutation, runtime start, activation, Dogfood 02 action, or historical data change was
  performed.
