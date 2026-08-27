# T010 — Fix migration naming

Status: `DONE_WITH_CONCERNS`

Fix revision 0015 constraint-drop naming so a fresh PostgreSQL schema migrates through
head under the actual SQLAlchemy naming convention. Preserve migration semantics and
immutable-facts protections. Add/adjust migration regressions, then rerun the approved
clean reset, full-year OANDA durable load, and unchanged covered repeat with zero
provider calls. Do not expose credentials or fabricate evidence.

## Receipt

ROLE: BUILD  
STATUS: DONE_WITH_CONCERNS  
ARTIFACT: `dispatch/workstreams/foundation-freeze-03-historical-data-foundation/tasks/T010-fix-migration-naming.md`  
FILES CHANGED: `backend/persistence/migrations/versions/0015_native_market_bar_resolutions.py`; `backend/tests/test_migration_revision.py`; this receipt  
CHECKS / EVIDENCE: Repository root and branch verified. `uv run pytest backend/tests/integration/test_migrations.py -q` with the disposable `*_test` PostgreSQL URL: **2 passed** (fresh reset, upgrade through `0016_load_progress`, downgrade/re-upgrade, native constraints, immutable-facts checks). Focused `uv run pytest backend/tests/test_migration_revision.py backend/tests/test_historical_data_load.py backend/tests/integrations/test_oanda_source.py -q`: **46 passed, 1 skipped**. `git diff --check` passed.  
CONCERNS: The authorized genuine OANDA V2 request for `[2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z)` was started after the clean migration reset (request `9141377e-cfc0-414c-ad0a-aaf54d55dc96`) but failed with sanitized `PERSISTENCE / DATABASE_WRITE_FAILED` at `2026-08-27T15:29:43.993406Z`; progress at failure was 263 fetched/committed ranges and 24,697 inserted observations. The unchanged covered repeat was not run because the first load did not complete; zero repeat provider calls is therefore unestablished. No credentials were printed, and immutable-facts protections or migration semantics were not weakened.
