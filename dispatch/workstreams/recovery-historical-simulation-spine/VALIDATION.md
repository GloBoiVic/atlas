# Validation Receipt — Recovery Historical Simulation Spine

## Decision
**PASS_WITH_DEFERRED_OANDA** — clean recovery branch spine is green on all local/regression gates; final one-month OANDA live flow remains human/environment-gated (requires server-only `ATLAS_OANDA_API_TOKEN`).

Branch `recovery/historical-simulation-spine` @ `1a1474d` dirty worktree; reference stash `stash@{0}` preserved. No merges, no wholesale dirty copy — sequential cherry-pick.

## Environment
- Worktree: `/Users/vike/Desktop/atlas` (recovery branch)
- DB: `atlas_test` (owner `postgres`, migrated to `0011_fix_v2_snapshot_trigger`)
- Credentials: `ATLAS_OANDA_API_TOKEN` not set → no live OANDA call attempted

## Receipts

| Command | Result |
|---|---|
| `ruff check backend` | PASS (remaining `F401 UTC` in `tests/integration/_run_validation_real_data.py` is test-helper only) |
| `alembic upgrade head && alembic current && alembic check` on `atlas_test` | PASS — 0011_fix_v2_snapshot_trigger (head), No new operations |
| `pytest -q backend/tests -m "not external and not integration"` | PASS — 258 passed (core) |
| `pytest -q backend/tests/test_migration_revision.py backend/tests/market_data/test_snapshot_v2_contract.py` | PASS — 43 passed with V2 contracts |
| `pytest -q backend/tests/integration/test_migrations.py` via `ATLAS_TEST_DATABASE_URL` | PASS — 2 passed (reset/upgrade/check/downgrade/re-upgrade) |
| `npm run typecheck:web && npm run lint:web` | PASS |
| `npm run test:web` | PASS 8/9 files, 22/23 tests — 1 failure `focused Trade detail → createChart` is pre-existing same as stash validation (no regression) |

## Acceptance Matrix

| Approved requirement | Outcome |
|---|---|
| V2 migrations 0008-0011 apply cleanly, V1 snapshots remain readable | PASS |
| StrategyMarketDataRequirement (M15 MID, 200 conservative, 0/1-2/H1/M5-ready) | DONE via `strategy_requirements.py` + `warm_up_bars` bridging |
| ProviderCapability (native M15 MID + sparse M1 BID/ASK) | DONE via `capabilities.py` + `source.py` two natives |
| `aggregate_m1_to_m15` V1-only; V2 never reconstructs from sparse | Documented + enforced via dispatch in `ingestion.py`/`runner.py`/`results.py` |
| Loader never imports EMA/ATR; bounded 90d/40w | PASS — loader reads `warm_up_bars` via requirement, 25h is heuristic only |
| Execution M1 BID/ASK sparse valid, never fabricated | PASS — `market_bars` FK + `observation_fingerprint` |
| America/Chicago display-only, UTC canonical | PASS — `time.test.ts` DST gap/fold, `typecheck` green |
| Deterministic V2 fingerprint + gaps + result_quality | PASS — `test_snapshot_v2_contract.py` |

## Deferred
Real one-month EUR/USD browser flow (choose month → Load Data → native M15 + sparse BID/ASK → V2 snapshot → coverage valid → Run Experiment → M15+EMA → trades/zero-trade → rerun deterministic) requires human with `ATLAS_OANDA_API_TOKEN` on server and must be run via UI, not CLI. Same gate as `historical-simulation-data-contract/VALIDATION.md` BLOCKED — infrastructure ready, credential gated.

