# T022 — Live snapshot persistence remediation

Status: `DONE_WITH_CONCERNS`

Diagnose the sanitized `DATABASE_WRITE_FAILED` during fresh token-only full-year
Snapshot finalization after successful 767,673-bar acquisition. Reproduce with a
bounded deterministic large fixture, identify the exact database operation/constraint,
and fix only the V2 streaming snapshot path while preserving append-only immutable
facts, exact sparse/native membership, deterministic fingerprints, and bounded memory.
Then rerun fresh genuine full-year acquisition (no stopped-load resume), covered repeat,
and interrupted/resumed equivalence with all required performance telemetry.

## Receipt

ROLE: BUILD
STATUS: DONE_WITH_CONCERNS
ARTIFACT: `dispatch/workstreams/foundation-freeze-03-historical-data-foundation/tasks/T022-live-snapshot-persistence-remediation.md`

### Diagnosis and remediation

The V2 finalization path computed the snapshot identity over header, analytical, and
execution members with `gaps=()`, while `create_v2_validated(..., gaps=None)` generated
and persisted the canonical missing-native-candle gap members before recomputing the
identity. A sparse deterministic fixture therefore produced a fingerprint mismatch
after the membership inserts. This was surfaced by the API as the generic persistence
failure; the bounded reproduction did not identify a PostgreSQL constraint violation.

The fix keeps the append-only parent row born with its final fingerprint, but makes the
pre-insert streaming digest include the same bounded gap stream used by repository
finalization. No membership is materialized; execution and analytical streams remain
repeatable database reads, and the caller transaction still atomically rolls back on
any insert or validation failure.

### Files changed

- `backend/market_data/ingestion.py`
- `backend/tests/market_data/test_freeze03_regressions.py`
- this receipt

### Evidence

- Deterministic regression: `uv run pytest -q backend/tests/market_data/test_freeze03_regressions.py` — **9 passed**.
- Lint: `uv run ruff check backend/market_data/ingestion.py backend/tests/market_data/test_freeze03_regressions.py` — **clean**.
- Fixture benchmark: `uv run python -m backend.market_data.freeze03_benchmark` — all four scenarios completed; repeat made **0/0** provider calls, fingerprint remained `c830c458bdb309aeb34354fcf25adb41655e4bad335927b5e382da419f7a6320`, interrupted/resumed matched it, maximum batch **2,868**, maximum progress payload **417 B**, peak RSS **131,756,032 B**.
- PostgreSQL integration could not be rerun in this environment: `ATLAS_TEST_DATABASE_URL` is configured, but the disposable PostgreSQL service is unavailable (Docker daemon unavailable). No genuine fresh 2025-01-01 through 2026-01-01 OANDA rerun, covered repeat, or interrupted/resumed live equivalence is claimed.

CONCERN: Live PostgreSQL/OANDA evidence remains outstanding; do not mark the live
benchmark complete from this receipt alone. A fresh disposable database must be
migrated and a new genuine load run after this remediation.
