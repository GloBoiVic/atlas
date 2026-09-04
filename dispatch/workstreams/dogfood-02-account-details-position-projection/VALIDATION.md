# VALIDATION — Dogfood 02 Account Details Position Projection

- **Workstream:** `dogfood-02-account-details-position-projection`
- **Role:** `VALIDATE`
- **Branch:** `solo/dogfood-02-account-details-position-projection`
- **Source task:** `tasks/T001-dogfood-02-account-details-position-projection.md`
- **Status:** `PASS`

## Independent conclusion

**PASS** — T001 satisfies the frozen `PLAN.md`/`ARCHITECTURE.md` contract. The new pure
Account Details projection is separate from the strict `/openPositions` normalizer, retains
only derived open inventory, and preserves fail-closed count, exposure, frontier, runtime,
P05, reconciliation, and mutation boundaries.

## Checks and exact evidence

Run in the required order, with sanitized local fixtures only:

1. `uv run pytest backend/tests/integrations/test_oanda_positions.py -q` — **75 passed**.
2. `uv run pytest backend/tests/integrations/test_oanda_execution_capability.py backend/tests/integrations/test_oanda_exposure_projection.py backend/tests/runtime/test_runtime_orchestration.py backend/tests/runtime/test_runtime_cycles.py backend/tests/paper/test_execution_composition.py backend/tests/integrations/test_oanda_reconciliation.py -q` — **138 passed**.
3. `uv run pytest -m "not integration and not external"` — **1221 passed, 4 skipped, 115 deselected**; only existing warnings were reported.
4. Changed-slice `uv run ruff format --check ...` — **9 files already formatted**; changed-slice `uv run ruff check ...` — **All checks passed**.
5. Changed-slice `uv run pyright ...` — **0 errors, 0 warnings, 0 informations**.
6. `git diff --check` — **passed**.

The safe-suite first attempt exceeded the tool's 120-second limit while progressing; the
same command was rerun with a 300-second limit and completed with the result above. This is
not a test failure.

## Requirement and A–O evidence

- **A–C:** `test_account_details_derives_open_position_count_from_nonzero_sides` covers an
  empty collection and multiple minimal zero/zero lifetime records; the full flat test
  projects `FLAT`. `positions.py:265-342` excludes only validated zero/zero records.
- **D–E:** the same execution-account parameterization covers genuine long and short
  positions; `test_account_details_open_position_preserves_projection_counterpart_semantics`
  proves `LONG`/`SHORT`; `test_account_details_retains_nonzero_positions_and_both_sides`
  proves both sides are retained without netting.
- **F–G:** `test_account_details_position_count_contradictions_fail_closed` covers both
  `count=0` with derived exposure and positive count with only historical records. The
  snapshot constructor's exact derived-count check remains at `execution_account.py:139-146`.
- **H–I:** `test_account_details_units_are_validated_before_closed_classification` covers
  missing/invalid/non-finite/non-string unit values on either side; the helper parses both
  units before classification at `positions.py:313-327`. Invalid long/short signs are
  covered by `test_account_details_invalid_position_signs_fail_closed` and remain rejected.
- **J:** raw duplicate detection, including excluded zero/zero records, is covered by
  `test_account_details_duplicate_detection_includes_excluded_positions`; the helper tracks
  duplicates before exclusion at `positions.py:288-297`.
- **K:** existing `test_zero_sides_are_explicit_but_both_zero_is_contradictory` still proves
  the separate strict `/openPositions` normalizer rejects zero/zero. Its implementation at
  `positions.py:229-262` is not replaced or called by the Account Details helper.
- **L:** `test_account_details_zero_historical_position_is_flat_and_projects_flat` calls
  `require_flat_entry_state()` on the corrected full snapshot and proves `FLAT`; the
  reconciliation historical-position test proves no derived open position and
  `unexpected_exposure=False`.
- **M:** parameterized `test_startup_uses_derived_account_position_projection_for_flat_gate`
  uses a normalized Account Details snapshot: historical zero/zero starts, while genuine
  exposure returns `BOOTSTRAP_REQUIRES_FLAT` and does not run.
- **N:** the four new public-composition tests cover derived exposure, dual-sided exposure,
  pending Orders, and normalization/count refusal. Each proves account read ordering and
  zero entry/protection mutation calls (`events == ["properties", "account"]`).
- **O:** reader tests use `httpx.MockTransport`, assert GET-only paths and the single full
  Account Details request, and do not use credentials or external calls. Reconciliation
  serializes only normalized derived fields at `reconciliation.py:251-283`; existing
  dataclass-field coverage proves raw provider extras are not retained.

Boundary validation is present for `-0`, omitted zero-side prices, required exposed-side
prices, invalid supplied prices, malformed zero/zero non-unit fields being irrelevant, and
malformed units remaining fatal. The helper is read-only over caller mappings; it constructs
immutable typed output and performs no HTTP.

## Diff and safety audit

The implementation diff is limited to the OANDA export, Account Details normalization, the
new Account Details position seam, and directly affected deterministic tests plus the
operational `dispatch/ACTIVE.md` update. No schema/migration, Strategy, Risk, runtime
implementation, execution policy, reconciliation policy, API/UI, or provider-read topology
change was found. `OandaPracticeExecutionAccountReader.read` still performs one full
Account Details GET (`execution_account.py:301-315`); no `/openPositions` or `/positions`
workaround was added. The validated common `lastTransactionID` is passed to every child
inventory and retained by the snapshot.

No credentials were read or changed; atlas-runtime was not started; no activation was
created, reused, or restarted; no OANDA/provider call or broker mutation was performed; and
no application, test fixture, harness, or implementation file was edited during validation.

## Findings

- **CRITICAL:** none.
- **IMPORTANT:** none.
- **CONCERN:** none within the approved T001 scope.
