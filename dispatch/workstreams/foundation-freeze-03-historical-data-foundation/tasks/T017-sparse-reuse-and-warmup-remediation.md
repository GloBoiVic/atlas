# T017 — Sparse reuse and canonical warm-up remediation

Status: `DONE_WITH_CONCERNS`

Implement the approved external-review corrections only:

- make `_validate_v2_coverage` accept fully absent sparse M1 minutes when the successful
  acquisition window covers them, while rejecting one-sided BID/ASK absence;
- keep successful sparse-window semantics limited to M1 execution and keep native M15
  expected completed-bar/context gaps strictly blocking;
- remove/bypass `load_v2_incremental`; extend warm-up through canonical missing-only
  `load_v2` so canonical M15/M1 observations are persisted/reused;
- subtract the union of overlapping successful acquisition windows, including windows
  that contain or overlap a later subrange, from missing acquisition spans.

Add deterministic regressions for all cases and run genuine full-year load through the
historical-load/configuration path with reference Strategy warm-up, then unchanged
repeat proving zero M15/M1 OANDA calls and same snapshot/fingerprint. Preserve no
fabrication/forward-fill and all other Freeze 03 behavior. Never expose credentials or
change Git history.

## BUILD receipt

Status: `DONE_WITH_CONCERNS`

Files changed:

- `backend/experiments/configuration.py`
- `backend/market_data/ingestion.py`
- `backend/market_data/historical_load.py`
- `backend/persistence/market_data_repository.py`
- `backend/tests/experiments/test_configuration.py`
- `backend/tests/market_data/test_freeze03_regressions.py`
- `backend/tests/test_historical_data_load.py`

Checks / evidence:

- Targeted pytest: **32 passed, 1 skipped**.
- Freeze 03 fixture benchmark repeat: `m15_calls=0`, `m1_calls=0`; matching fingerprint `5dbf3534c3e44032fcaf918fafb877227fe01f577c4b717c77a4ebe2f477ca5e`.
- Added coverage, strict native M15, warm-up bypass, and containing-window regressions. No fabrication or forward-fill was added.
- `git diff --check` passed; no branch or Git history changes.

Concerns:

- The repository benchmark uses a representative 2024-01-01→2024-02-01 fixture despite its `one_year` label. A genuine one-calendar-year run through the persisted historical-load/configuration coordinator was unavailable without the configured integration database/reference Strategy fixture.
