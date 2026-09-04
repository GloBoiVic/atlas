# Remediation R002 — Dogfood 01 Lifecycle-Advanced Activation Fence

- **Remediation ID:** `R002`
- **Status:** `DONE_WITH_CONCERNS`
- **Origin finding:** IMPORTANT findings 1 and 2 in `dispatch/workstreams/dogfood-01-lifecycle-advanced-activation-fence/remediations/R001-dogfood-01-lifecycle-advanced-activation-fence/REVIEW.md`
- **Finding severity:** `IMPORTANT`
- **Finding class:** approved-scope `DEFECT` (PRODUCT)
- **Related original task:** `T001-dogfood-01-lifecycle-advanced-activation-fence`
- **Related remediation:** `R001-dogfood-01-lifecycle-advanced-activation-fence`
- **Branch:** `solo/dogfood-01-lifecycle-advanced-activation-fence`
- **Owned artifact:** `dispatch/workstreams/dogfood-01-lifecycle-advanced-activation-fence/remediations/R002-dogfood-01-lifecycle-advanced-activation-fence/BUILD.md`

## Approved requirement or invariant violated

`FILLED_PROTECTION_INCOMPLETE + LIFECYCLE_ADVANCED` may stop fencing a new session only
when existing durable Fill and applied reconciliation evidence are complete, coherent, and
non-conflicted. Provider-neutral reconciliation metadata must remain bounded and internally
consistent; contradictory or unsupported durable evidence blocks.

## Findings

R001 still permits `ENTRY_REJECTED`/`ENTRY_CANCELLED` alongside
`TRADE_LIFECYCLE_ADVANCED`, and does not constrain the applied run's read budget to the
provider-neutral maximum or enforce `non_atomic_read_set == (read_count > 1)`. Those malformed
shapes remain eligible.

## Exact remediation outcome

Tighten only the existing classifier qualifier so it rejects incompatible entry-terminal
findings and applied-run metadata outside the existing provider-neutral reconciliation contract:
the configured maximum read budget and the exact non-atomic read-set relation. Preserve valid
normal lifecycle-advanced evidence and all existing strict/recovery behavior.

## Affected implementation seams

- `backend/persistence/runtime_repository.py` lifecycle-ended Fill qualifier.
- Focused runtime classifier tests for known contradictory findings and run metadata bounds.

## Explicit out-of-scope items

- No change to `is_unsafe_paper_attempt()`.
- No provider-neutral reconciliation implementation change, schema/migration, historical data,
  activation lifecycle, startup, P05, Risk, claims, retries, mutation paths, or architecture
  contract.
- No credentials, runtime start, Dogfood 02 action, provider validation, or broker mutation.

## Regression evidence required

- Normal applied lifecycle advancement remains eligible with current reconciliation output.
- `ENTRY_REJECTED`/`ENTRY_CANCELLED`, read budget above the existing maximum, and inconsistent
  `non_atomic_read_set` fail closed.
- T001/R001 focused and safe checks remain passing; strict predicate and diff checks remain
  unchanged.

## Worker Evidence

ROLE: BUILD  
STATUS: DONE_WITH_CONCERNS  
ARTIFACT: `dispatch/workstreams/dogfood-01-lifecycle-advanced-activation-fence/remediations/R002-dogfood-01-lifecycle-advanced-activation-fence/BUILD.md`

### Files changed

- `backend/persistence/runtime_repository.py`
- `backend/tests/runtime/test_runtime_activation.py`
- This artifact only for the R002 receipt.

### Implementation

- Lifecycle-ended incomplete-Fill history now rejects applied runs containing
  `ENTRY_REJECTED` or `ENTRY_CANCELLED` with `TRADE_LIFECYCLE_ADVANCED`.
- The classifier now enforces the existing provider-neutral
  `MAX_RECONCILIATION_READS` ceiling and requires strictly typed
  `non_atomic_read_set == (read_count > 1)` metadata.
- Valid current reconciliation output remains eligible, including one-read atomic
  and multi-read non-atomic evidence; `is_unsafe_paper_attempt()` and all R001/T001
  authority boundaries remain unchanged.
- No schema/migration, provider-neutral reconciliation, activation/startup/P05/Risk,
  owner/claim/no-retry, mutation, historical, credential, runtime-start, or Dogfood 02
  change was made.

### Checks / evidence

- Red-before-fix focused regressions: **5 failed** for the newly covered fail-open shapes.
- Focused runtime/orchestration/completion-cross-seam/reconciliation suite: **185 passed**.
- Safe backend suite: **1182 passed, 4 skipped, 115 deselected, 4 warnings**.
- Changed-slice Ruff format/check: **passed**.
- Changed implementation Pyright: **0 errors, 0 warnings, 0 informations**.
- `uv run alembic check`: **no new upgrade operations detected**.
- `git diff --check`: **passed**.
- Regressions cover both incompatible entry-terminal finding codes, the read-budget
  ceiling, invalid/mismatched read-set metadata, and preservation of valid one- and
  multi-read provider output.

### Findings / concerns

- No dedicated PostgreSQL integration run was available (`ATLAS_TEST_DATABASE_URL` was
  unset); no schema change was made.
- No credentials, runtime start, activation, provider request, broker mutation, Dogfood 02
  action, or historical-data change was performed.
