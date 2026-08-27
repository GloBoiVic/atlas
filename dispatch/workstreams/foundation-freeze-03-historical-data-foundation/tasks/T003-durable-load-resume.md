# T003 — Durable load and resume

Status: `DONE_WITH_CONCERNS`

After T001 and T002, implement the V2 load coordinator lifecycle: persist and validate
each bounded window before recording progress, keep earlier work reusable, recompute
coverage on explicit resume, fetch only remaining windows, process arbitrarily large
plans in bounded batches without a window-count ceiling, prevent duplicate active
requests, and represent unknown/terminal failures safely. Add interruption/recovery
tests. Do not make provider calls from database transactions.

## Receipt

Implemented the durable V2 acquisition/resume slice only.

### Files changed

- `backend/market_data/ingestion.py` — independently plans native M15/MID and
  M1/BID+ASK missing coverage, performs bounded provider calls outside DB
  transactions, atomically commits each validated window, reports product/window
  progress only after commit, and rebuilds analytical membership from durable
  canonical rows on resume.
- `backend/market_data/historical_load.py` — removes request-range and
  request-window ceilings and persists product/window progress through the
  coordinator callback.
- `backend/persistence/historical_data_load_repository.py` — additive product
  progress and explicit terminal-failure resume retaining prior coverage facts.
- `backend/api/historical_data.py` — explicit `POST .../{request_id}/resume`.
- `backend/persistence/models.py` and
  `backend/persistence/migrations/versions/0016_unbounded_historical_load_progress.py`
  — remove obsolete 90-day/40-range ceilings while retaining range validation.
- `backend/tests/test_historical_data_load.py` — deterministic resume and
  committed product-window progress tests.

### Checks and evidence

- `pytest -q backend/tests/test_historical_data_load.py backend/tests/market_data backend/tests/integrations/test_oanda_source.py`
  — **78 passed, 2 skipped** (credential/database-dependent cases).
- `ruff check` on T003-changed modules — passed.
- `git diff --check` — passed.

### Concerns / boundaries

- PostgreSQL migration execution and transaction-interruption integration tests
  were unavailable; these remain for VALIDATE.
- DatasetSnapshot authority, Experiment validation, and stale-path quarantine are
  intentionally deferred to T004. Existing legacy incremental code remains outside
  this task and is not used by the new missing-only V2 load path.
