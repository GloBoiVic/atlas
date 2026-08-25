# Task 04 — V2 Native Acquisition + Immutable Snapshot

## Status
**DONE** (restored from validated stash, cleaned)

- `backend/market_data/historical_load.py` — bounded, policy-aware coordinator: initial `25h` estimate then `_warmup_plan` loop extending within `90d/40w` until `eligible >= warm_up_bars (200)` or `INSUFFICIENT_WARMUP`; counts `eligible` from actual native M15 membership (`_v2_warmup_count` via `dataset_snapshot_analytical_bars`), not open minutes. V2 path via `ingestion.load_v2` (native M15 + sparse M1), V1 fallback via `load_missing` intact.
- `backend/market_data/ingestion.py` — `load_v2` persistence, `create_snapshot` V2, `derive_m15` V1-only documented, deterministic `FINGERPRINT_SCHEMA_V2`
- `backend/persistence/historical_data_load_repository.py` + `historical_data_load_requests` durable `PENDING→RUNNING→COMPLETED/FAILED`, single-active index, sanitized failure codes
- `backend/api/historical_data.py` + `backend/persistence/historical_data_load_repository.py` — server-only `ATLAS_OANDA_API_TOKEN`, never in client/log, bounded OANDA windows (40×3 attempts)
- `backend/market_data/session_policy.py` + provenance md — NY 16:59-17:05 + weekly closure via ZoneInfo (investigation-proven sparse = real provider gaps)

V2 snapshot: `dataset_snapshot_analytical_bars` (native M15 MID), `dataset_snapshot_execution_observations` (sparse BID/ASK FK), `dataset_snapshot_gaps` (BLOCKING etc), `integrity_summary` with `policy_version=GAP_POLICY_V1`.

## Verification
- Focused `pytest backend/tests/test_historical_data_load.py` — 9 passed, 1 skipped (guarded PG)
- `pytest -q backend/tests/market_data/test_snapshot_v2_contract.py` — PASS, V2 fingerprint deterministic
- `pytest -q backend/tests -m "not external and not integration"` — 258 passed core

