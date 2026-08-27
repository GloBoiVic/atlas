# T011 — Full-year persistence remediation

Status: `DONE_WITH_CONCERNS`

Diagnose and correct the real full-calendar-year V2 persistence failure observed after
263 committed windows and 24,697 inserts. Preserve fail-closed conflict/immutability
semantics and bounded durable progress. Add a deterministic regression for the failing
native product/shape, then reset the disposable database and rerun the genuine
2025-01-01–2026-01-01 OANDA load plus unchanged covered repeat, recording complete
metrics and zero repeat provider calls. Never expose credentials or silently discard
partial-load behavior.

## Receipt

ROLE: BUILD  
STATUS: DONE_WITH_CONCERNS  
ARTIFACT: `dispatch/workstreams/foundation-freeze-03-historical-data-foundation/tasks/T011-full-year-persistence-remediation.md`  
FILES CHANGED: `backend/persistence/market_data_repository.py`; `backend/tests/integration/test_market_data_repositories.py`; this receipt  
CHECKS / EVIDENCE: Repository root and branch verified. Diagnosis: the genuine run reached 24,605 persisted native `M15/MID` rows and then stalled in V2 snapshot persistence; the failing shape was the full-year native analytical membership sent as one unbounded PostgreSQL executemany payload. V2 analytical, execution, and gap membership inserts now remain in one atomic transaction while executing in bounded 1,000-row batches. The deterministic representative regression crosses that boundary with 1,201 native analytical rows. After an authorized disposable `public` schema reset, `uv run alembic upgrade head` completed through `0016_load_progress`; `uv run pytest backend/tests/integration/test_migrations.py -q`: **2 passed**. Focused tests: `uv run pytest backend/tests/test_historical_data_load.py backend/tests/integrations/test_oanda_source.py -q`: **44 passed, 1 skipped**. `uv run ruff check ...` and `git diff --check` passed.  
CONCERNS: A genuine OANDA V2 rerun was started against the reset database with the unchanged `[2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z)` range. It persisted **24,605 M15/MID**, **370,113 M1/BID**, and **370,113 M1/ASK** rows, with **0 snapshots**, before the authorized 20-minute execution window expired; no fabricated completion metric is claimed. The unchanged covered repeat and zero-repeat-provider-call proof were not run because the first run did not reach snapshot completion. No credentials were printed; fail-closed conflicts, immutable facts, native constraints, bounded progress, and no-fabrication behavior were not weakened.
