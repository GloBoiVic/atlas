# T035 — Complete terminal snapshot metrics

Status: `COMPLETE WITH CONCERNS`

## Assignment

Fix REVIEW finding 6 only. Ensure terminal snapshot/fingerprint metrics accurately
count all hashed records, including gaps, or explicitly report analytical, execution,
and gap counts separately without presenting an incomplete count as the total. Preserve
snapshot bytes, membership ordering, determinism, and bounded-memory behavior. Add
focused metric regression coverage.

Do not change ingestion semantics, provider chunking, progress phases, Experiment
validation, completion handling, or unrelated architecture.

## Required checks

- focused gap-inclusive terminal metric regression;
- affected snapshot/repository tests;
- Ruff/compile checks and `git diff --check`.

## Receipt

ROLE: BUILD
STATUS: COMPLETE WITH CONCERNS
FILES CHANGED:
- `backend/persistence/market_data_repository.py`
- `backend/market_data/ingestion.py`
- `backend/market_data/freeze03_benchmark.py`
- `backend/tests/integration/test_market_data_repositories.py`
- `backend/tests/market_data/test_freeze03_regressions.py`
- this receipt
CHECKS / EVIDENCE:
- Focused terminal gap-inclusive metric regression: 1 passed.
- Snapshot contract, Freeze 03 regression, and repository tests: 29 passed, 6 skipped
  (database-gated).
- Affected historical-load and ingestion tests: 23 passed, 6 skipped
  (database-gated).
- Ruff passed for changed application/test files.
- `python -m compileall -q backend` passed.
- `git diff --check` passed for changed application/test files.
IMPLEMENTATION:
- Gap finalization now counts every gap row while streaming and exposes the count in
  repository finalization telemetry.
- Terminal snapshot-membership `rows` and fingerprinting `records_hashed` now include
  analytical, execution, and gap rows, with each component count reported separately.
- Fingerprint input bytes, membership ordering, deterministic hashing, and bounded
  streaming/batch behavior are unchanged.
CONCERNS:
- PostgreSQL-backed repository checks were skipped because `ATLAS_TEST_DATABASE_URL`
  is not configured; no genuine OANDA run or database reset was performed.
