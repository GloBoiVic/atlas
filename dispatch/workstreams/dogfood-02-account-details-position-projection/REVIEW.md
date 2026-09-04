# REVIEW — Dogfood 02 Account Details Position Projection

- **Workstream:** `dogfood-02-account-details-position-projection`
- **Role:** `REVIEW`
- **Branch:** `solo/dogfood-02-account-details-position-projection`
- **Source task:** `tasks/T001-dogfood-02-account-details-position-projection.md`
- **Validation:** `VALIDATION.md` (`PASS`)
- **Status:** `PASS`

## Independent review assignment

Review the completed T001 implementation, frozen PLAN/ARCHITECTURE contract, immutable task
receipt, and independent validation artifact. Inspect the complete branch diff and judge
scope, correctness, safety, provider-read topology, endpoint distinction, derived-count and
frontier authority, dual-sided exposure handling, runtime/P05/reconciliation behavior, test
evidence, and all dogfood restrictions. Confirm no schema/migration, Strategy, Risk policy,
runtime cadence, execution semantics, activation, credential, provider mutation, or manual
repair was introduced.

Pass requires zero unresolved CRITICAL or IMPORTANT findings. Classify any finding as an
approved-scope DEFECT or NEW SCOPE according to SoloFlow; do not edit application, tests,
fixtures, harnesses, or other implementation code. Write only this canonical review artifact
once with the independent judgment and evidence.

## Independent conclusion

**PASS** — T001 satisfies the frozen `PLAN.md`/`ARCHITECTURE.md` contract with no
unresolved CRITICAL or IMPORTANT findings.

## Review evidence

- Inspected the complete branch diff from base `b75930f2276f93938e250ea8498ad8affb4f97c5`.
  The implementation change is limited to the exported Account Details-only projection
  seam and its call site; remaining changes are directly affected deterministic tests and
  operational `dispatch/ACTIVE.md` state.
- `positions.py` keeps the strict `/openPositions` normalizer and its zero/zero rejection
  intact. The new pure helper validates the full raw collection, instrument and side shape,
  both finite signed units, raw duplicates (including excluded records), excludes only
  zero/zero records, and preserves both sides plus existing open-position invariants for
  nonzero records. It does not mutate input or retain provider extras.
- `execution_account.py` uses only the derived inventory; existing exact count coherence,
  common `lastTransactionID` frontier propagation, Trade/Order semantics, exposure
  projection, `require_flat_entry_state`, runtime, P05, and reconciliation behavior remain
  unchanged. The reader still performs one full Account Details GET and no position-endpoint
  workaround was added.
- No schema/migration, Strategy, Risk policy, runtime implementation, execution policy,
  reconciliation policy, activation, credential, provider mutation, or manual repair was
  introduced.
- Independent focused run: `213 passed` across the affected OANDA, exposure, runtime,
  P05, and reconciliation tests. The PASS validation receipt additionally records the safe
  suite (`1221 passed, 4 skipped, 115 deselected`), changed-slice Ruff/Pyright success, and
  `git diff --check` success.

## Findings

- **CRITICAL:** none.
- **IMPORTANT:** none.
- **CONCERN:** none within the approved T001 scope.
