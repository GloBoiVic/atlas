# T015 — Sparse snapshot performance

Status: `DONE_WITH_CONCERNS`

Resolve the T014 live snapshot-materialization timeout without changing sparse-data
semantics. Audit snapshot membership reads/inserts and fingerprinting for the
full-year sparse M1 dataset; use bounded/chunked operations and appropriate existing
indexes where necessary. Preserve exact sparse observations, immutable membership,
determinism, and zero-call reuse. Add a representative performance regression, then
complete the genuine full-year snapshot and unchanged covered repeat evidence.

## Receipt

ROLE: BUILD  
STATUS: DONE_WITH_CONCERNS  
ARTIFACT: `dispatch/workstreams/foundation-freeze-03-historical-data-foundation/tasks/T015-sparse-snapshot-performance.md`  
FILES CHANGED: `backend/persistence/market_data_repository.py`, `backend/tests/integration/test_market_data_repositories.py`  
CHECKS / EVIDENCE: CodeGraph-first audit and repository/branch verification completed. The indexed current-bar range query already uses the existing partial current-row index; the timeout bottleneck was the 740,226-row sparse execution membership's 1,000-row executemany cadence (approximately 740 insert round trips) inside the single immutable transaction. Increased the bounded payload to 10,000 rows (still bounded; transaction atomicity and schema constraints unchanged). Deterministic fixture benchmark passed all four scenarios: fresh month 11.021s, fresh representative year 10.172s, covered repeat 8.010s with 0 provider calls and identical fingerprint, interrupted/resumed 9.855s. `pytest -q backend/tests/market_data/test_freeze03_regressions.py`: 6 passed. PostgreSQL repository snapshot regression was skipped because `ATLAS_TEST_DATABASE_URL` is not configured. `python -m backend.market_data.freeze03_benchmark` completed successfully and emitted full metrics. `compileall`/live full-year rerun could not be performed because no authorized database/OANDA environment variables are present (`ATLAS_TEST_DATABASE_URL`, `ATLAS_OANDA_API_TOKEN`, `ATLAS_OANDA_ACCOUNT_ID`, and `ATLAS_EXTERNAL_OANDA_TOKEN` all absent).  
FINDINGS / CONCERNS: Implementation preserves sparse membership, immutable single-transaction creation, deterministic fingerprint inputs, and existing indexed reads. Genuine full-year snapshot completion and unchanged repeat zero-provider-call proof remain blocked by unavailable authorized disposable PostgreSQL/OANDA configuration; no secrets were exposed and no reset was attempted.
