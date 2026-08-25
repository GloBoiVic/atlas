# Task 01 — V2 Migration Skeleton

## Status
**DONE**

Cleanly re-applied approved V2 schema delta on `recovery/historical-simulation-spine` @ `1a1474d`:

- `backend/domain/market_data.py` — added `SNAPSHOT_SCHEMA_V2`, `FINGERPRINT_SCHEMA_V2`, `NATIVE_M15_CONTRACT_V1`, `GAP_POLICY_V1`, V2-aware `DatasetSnapshot` (conditional resolution/components/fingerprint/policy_version)
- `backend/market_data/fingerprint.py` — deterministic V2 fingerprint over ordered analytical + execution + gaps + metadata (UTC-second canonical)
- `backend/persistence/models.py` — conditional V1/V2 constraints (`snapshot_resolution_by_schema`, `components_by_schema`, `fingerprint_schema_by_snapshot`, `valid_integrity_summary`), new tables `dataset_snapshot_analytical_bars` (M15 MID), `dataset_snapshot_execution_observations` (M1 BID/ASK FK), `dataset_snapshot_gaps` (M1/M15, policy_version), `historical_data_load_requests` moved to 0008, `experiment_results.result_quality` + `experiment_gap_decisions`
- Migrations `0008_historical_load` (durable LOAD_MISSING PENDING→RUNNING→COMPLETED/FAILED, 90d/40w, atlas_historical_ranges_valid), `0009_historical_snapshot_v2`, `0010_experiment_gap_decisions`, `0011_fix_v2_snapshot_trigger` (TG_TABLE_NAME dispatch fix)

Existing V1 snapshots remain readable (backfilled `snapshot_schema=ATLAS_HISTORICAL_SNAPSHOT_V1`, old constraints conditional).

## Verification
- `ruff check backend/domain/market_data.py backend/market_data/fingerprint.py backend/persistence/models.py backend/persistence/migrations/versions/0009*.py` — PASS
- `pytest -q backend/tests/test_migration_revision.py backend/tests/market_data/test_snapshot_v2_contract.py backend/tests/domain/test_primitives.py` — 43 passed
- `ATLAS_DATABASE_URL=.../atlas_test alembic upgrade head && alembic current && alembic check` — 0011_fix_v2_snapshot_trigger (head), No new operations
- `pytest -q backend/tests/integration/test_migrations.py` with `ATLAS_TEST_DATABASE_URL` — 2 passed (full reset/upgrade/check/downgrade/re-upgrade cycle)

No Git mutation beyond this workspace; V1 readers unchanged.

