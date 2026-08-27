# T006 — Review remediation

Status: `DONE_WITH_CONCERNS`

Resolve the IMPORTANT findings in REVIEW.md without broad cleanup:

- remove effective 40-window/90-day warm-up ceilings while retaining only valid
  malformed/invariant planning failures;
- remove the legacy shared M1 planner from new V2 preparation;
- correct public historical-data product metadata to describe independent native M15
  MID analytical and native M1 BID/ASK execution products.

Add regressions proving the three corrections, run relevant checks, and append a
complete receipt. Preserve the frozen architecture and all safety semantics.

## Receipt

Implemented the three scoped review remediations without broad historical-data
cleanup.

### Files changed

- `backend/market_data/historical_load.py` — removed the 40-window and 90-day
  warm-up ceilings. `_warmup_plan` now validates malformed/invariant inputs only,
  extends deterministically by bounded increments, and reports readiness from the
  observed native M15 count. Removed the legacy `plan_missing` call from V2
  preparation.
- `backend/api/historical_data.py` — public source metadata now exposes separate
  analytical native M15/MID and execution native M1/BID+ASK products.
- `backend/api/schemas.py` — capability response models the independent product
  metadata.
- `backend/tests/test_historical_data_load.py` — regressions for uncapped warm-up,
  native-M15-count readiness, planner quarantine, and public product metadata.

### Checks and evidence

- Focused historical-load and Freeze 03 regression suite: **25 passed, 1 skipped**.
- Non-integration backend suite: **306 passed, 7 skipped**.
- Ruff for changed Python files, compileall, and `git diff --check`: **passed**.

### Concerns

- PostgreSQL-backed checks and credentialed OANDA evidence remain environment-gated
  as documented by the workstream validation receipt (`ATLAS_TEST_DATABASE_URL` and
  OANDA credentials are unavailable). No unrelated files or artifacts were edited.
