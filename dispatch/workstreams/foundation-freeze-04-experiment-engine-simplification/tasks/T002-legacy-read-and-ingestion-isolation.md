# T002 — Legacy Read and Ingestion Isolation

Status: `DONE`

State history: `READY → IN_PROGRESS → DONE_WITH_CONCERNS → DONE`

## Goal

Remove obsolete V1 acquisition/write and M1-derived public operator paths while
preserving explicitly read-only immutable V1 result/chart inspection and ensuring
V2 always reads native M15 membership.

## Read

- `PLAN.md`
- `ARCHITECTURE.md`, section 2.3 and the legacy-boundary invariants
- `backend/experiments/results.py`
- `backend/market_data/ingestion.py`, `aggregation.py`, and `cli.py`
- historical-load coordinator, snapshot repositories, and relevant tests

## Implement

- Put V1 M1→M15 derivation behind the named private result-reader boundary only;
  reject unknown schema rather than falling back to V1.
- Remove obsolete `MarketDataService` V1 acquisition/write methods, uncalled
  `current_m15`, `derive_m15`, and the public aggregation alias only as specified
  by architecture; remove their dead CLI commands/tests.
- Preserve V2 `load_v2`, native `create_snapshot_v2`, independent products,
  acquisition-window reuse, immutable membership, and historical coordinator flow.
- Preserve existing V1 rows as immutable; no migration, deletion, rewrite, or
  backfill.

## Do not implement

- Do not change native M15 MID, sparse M1 BID/ASK, gap, snapshot, fingerprint,
  warm-up, or provider semantics.
- Do not route V1 reads through mutable current bars or allow them to create/run a
  new Experiment.

## Acceptance/checks

- V2 result/chart tests prove direct native M15 membership and no legacy helper use.
- V1 immutable read fixture remains read-only and byte-stable.
- Old creation/write/CLI surfaces are absent; V2 historical-load and Freeze 03
  regression tests pass.

## Completion receipt

Status: `DONE`

### Files changed

- `README.md`
- `pyproject.toml`
- `backend/experiments/results.py`
- `backend/market_data/aggregation.py`
- `backend/market_data/coverage.py`
- `backend/market_data/ingestion.py`
- `backend/market_data/cli.py` (deleted)
- `backend/tests/experiments/test_price_analysis_results.py`
- `backend/tests/experiments/test_results.py`
- `backend/tests/integration/test_market_data_ingestion.py` (deleted)
- `backend/tests/market_data/test_cli.py` (deleted)
- `backend/tests/market_data/test_task3.py`
- `backend/tests/test_historical_data_load.py`

### Evidence

- V1 `price_analysis` and `_chart` reads now use the private
  `ExperimentResultReadService._legacy_v1_m15` membership-only boundary.
- V2 result/chart reads use persisted native M15 analytical membership; unknown
  schemas fail closed. The V2 load/snapshot/coordinator path remains intact.
- Removed V1 acquisition/write methods, `load_v2_incremental`, `current_m15`,
  `MarketDataService.derive_m15`, the public aggregation alias, and the obsolete
  CLI entry point/tests. Existing V1 rows are not migrated or rewritten.
- Source scan found no executable references to the removed method/command names;
  `aggregate_m1_to_m15` remains only in the isolated result-reader boundary and
  its primitive tests.
- Focused result/market-data/coordinator checks: `54 passed`.
- Freeze 03 and result regressions: `74 passed`.
- Full non-integration backend suite: `332 passed, 6 skipped` (one existing
  Starlette/httpx deprecation warning).
- Targeted Ruff, `git diff --check`, and `python -m compileall -q backend/market_data
  backend/experiments` passed.

### Concerns

- Strict Pyright remains non-clean (75 errors in the ingestion typing surface);
  unrelated typing cleanup was not expanded into T002.
- Database-backed integration tests were not run because
  `ATLAS_TEST_DATABASE_URL` was unavailable; available Freeze 03 and
  non-integration regressions passed.
