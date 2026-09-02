# PAPER 05 Validation

- **Workstream:** `paper-05-persistence-reconciliation`
- **Branch:** `solo/paper-05-persistence-reconciliation`
- **Base:** `7a3204c41a394172752ab64b8aeab3f8fbcccf5e`
- **Scope:** independent validation of T001 PAPER persistence foundation
- **Status:** `FAIL`
- **Role:** `VALIDATE`

## Validation evidence

- `uv run pytest backend/tests/paper/test_persistence_contracts.py backend/tests/paper/test_strategy_evaluation.py backend/tests/test_migration_revision.py -q`: **27 passed**.
- Dedicated PostgreSQL database `atlas_freeze07_test` (local `vike` role): focused repository tests **6 passed**; migration tests **3 passed** including upgrade/downgrade/upgrade, schema shape, and `alembic check`.
- Supplemental dedicated-DB checks: concurrent ENTRY claim, Fill non-erasure, stale reconciliation, append-only guards, and rollback all passed. Rollback left `attempts=0 claims=0`.
- `uv run pytest -m 'not integration and not external' -q`: **931 passed, 94 deselected**; four existing warnings only.
- Changed-slice Ruff format/lint: passed. Changed-slice Pyright: **0 errors**. `git diff --check`: passed. Alembic current: `0022_paper_persistence (head)`; no new upgrade operations.
- No OANDA calls, credentials, activation, runtime, or capital-capable action were used. VALIDATE changed only this artifact.

## Findings

### IMPORTANT — PRODUCT — same-ID result identity is not checked (FAIL)

`PaperExecutionRepository.apply_result()` forwards only the result attempt ID,
outcome, Fill, and protection to `apply_execution_outcome()`; it does not compare
`result.instruction` with the durable immutable instruction. A valid result built
with the same `attempt_id` but a changed quantity was accepted and wrote
`UNKNOWN` (`stored_quantity=20000`, `result_quantity=20001`) instead of raising
`PaperIdentityConflict`.

This violates the frozen same-ID immutable-facts conflict rule and permits a
result for different execution evidence to alter the attempt projection.

### IMPORTANT — PRODUCT — protection facts are not bound to the attempt (FAIL)

`apply_protection()` accepts any structurally valid `ProtectionConfirmation` and
does not verify the durable attempt's expected Stop/Take Profit client IDs,
prices, or actual-fill-derived target. Supplemental validation applied unrelated
protection (`unrelated-stop-client`, `unrelated-tp-client`, price `9.98`) and then
accepted `FILLED_PROTECTED`.

This violates strict protection attribution and the frozen requirement that
`FILLED_PROTECTED` represent exact confirmed protections for the attempt.

Both findings are unresolved Critical-slice persistence defects; SoloFlow
therefore requires remediation before validation can pass.

## Worker Evidence

ROLE: VALIDATE
STATUS: FAIL
ARTIFACT: `dispatch/workstreams/paper-05-persistence-reconciliation/VALIDATION.md`
FILES CHANGED: `dispatch/workstreams/paper-05-persistence-reconciliation/VALIDATION.md` only
CHECKS / EVIDENCE: Focused unit 27 passed; dedicated PostgreSQL repository 6 passed; migration 3 passed; broad safe backend 931 passed; Ruff/Pyright/Alembic/diff checks passed. Two supplemental identity/protection probes reproduced the findings above.
FINDINGS / CONCERNS: IMPORTANT PRODUCT findings require a remediation chain; no capital-capable or external broker action occurred.
