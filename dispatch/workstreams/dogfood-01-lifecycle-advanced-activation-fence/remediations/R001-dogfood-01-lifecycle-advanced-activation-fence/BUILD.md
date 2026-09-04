# Remediation R001 — Dogfood 01 Lifecycle-Advanced Activation Fence

- **Remediation ID:** `R001`
- **Status:** `DONE_WITH_CONCERNS`
- **Origin finding:** IMPORTANT finding 1 in `dispatch/workstreams/dogfood-01-lifecycle-advanced-activation-fence/REVIEW.md`
- **Finding severity:** `IMPORTANT`
- **Finding class:** approved-scope `DEFECT` (PRODUCT)
- **Related original task:** `T001-dogfood-01-lifecycle-advanced-activation-fence`
- **Branch:** `solo/dogfood-01-lifecycle-advanced-activation-fence`
- **Owned artifact:** `dispatch/workstreams/dogfood-01-lifecycle-advanced-activation-fence/remediations/R001-dogfood-01-lifecycle-advanced-activation-fence/BUILD.md`

## Approved requirement or invariant violated

`FILLED_PROTECTION_INCOMPLETE + LIFECYCLE_ADVANCED` may stop fencing a new session only
when the durable Fill and applied reconciliation evidence are complete, coherent, and
non-conflicted. Malformed, contradictory, or conflicted durable evidence must block.

## Finding

The new-session classifier currently accepts a linked applied `LIFECYCLE_ADVANCED` run while
ignoring durable `read_count`, `finding_codes`, and `diagnostic_summary`. A malformed shape
with zero reads and a conflict finding/diagnostic can therefore be classified safe.

## Exact remediation outcome

Make the existing semantic classifier fail closed unless the applied lifecycle-advanced run's
read evidence is structurally complete and contradiction-free. Validate only existing durable
fields; do not weaken strict same-attempt recovery or add a schema/policy bypass.

## Affected implementation seams

- `backend/persistence/runtime_repository.py` lifecycle-ended Fill qualifier.
- Focused runtime classifier tests for zero/invalid reads, conflict findings, and diagnostics.

## Explicit out-of-scope items

- No change to `is_unsafe_paper_attempt()`.
- No change to provider-neutral reconciliation semantics, schema, migrations, historical rows,
  activation lifecycle, startup gates, P05, Risk, claims, retries, or mutation paths.
- No credentials, runtime start, Dogfood 02 action, provider validation, or broker mutation.

## Regression evidence required

- Normal applied `LIFECYCLE_ADVANCED` lifecycle-ended incomplete Fill remains eligible.
- Zero/invalid read evidence, conflict/unresolved finding codes, non-empty diagnostic/block
  evidence, and contradictory applied runs block.
- Existing focused suite and relevant safe backend checks remain passing; strict predicate and
  diff checks remain unchanged.

## Worker Evidence

ROLE: BUILD  
STATUS: DONE_WITH_CONCERNS  
ARTIFACT: `dispatch/workstreams/dogfood-01-lifecycle-advanced-activation-fence/remediations/R001-dogfood-01-lifecycle-advanced-activation-fence/BUILD.md`

### Files changed

- `backend/persistence/runtime_repository.py`
- `backend/tests/runtime/test_runtime_activation.py`
- This artifact only for the remediation receipt.

### Implementation

- The existing semantic classifier now requires positive, bounded applied-run read evidence,
  structurally valid lifecycle findings containing `TRADE_LIFECYCLE_ADVANCED`, no contradictory
  findings, and an empty diagnostic summary.
- Malformed/contradictory read, finding, diagnostic, or durable block evidence fails closed.
- Normal applied lifecycle advancement remains eligible; strict
  `is_unsafe_paper_attempt()` and all out-of-scope paths remain unchanged.

### Checks / evidence

- Focused runtime/reconciliation suite: **174 passed**.
- Safe backend suite: **1171 passed, 4 skipped, 115 deselected** (4 existing warnings).
- Changed-slice Ruff format/check: passed.
- Changed implementation Pyright: **0 errors, 0 warnings, 0 informations**.
- `uv run alembic check`: no new upgrade operations detected.
- `git diff --check`: passed.
- Regression coverage includes zero/invalid reads, conflict/unresolved/unknown findings,
  diagnostic and block evidence, contradictory applied runs, and preservation of normal
  lifecycle-advanced evidence.

### Findings / concerns

- No dedicated PostgreSQL integration or credentialed/provider validation was run; no schema or
  migration change was made.
- No credentials, runtime start, activation, Dogfood 02 action, provider mutation, or historical
  data change was performed.
