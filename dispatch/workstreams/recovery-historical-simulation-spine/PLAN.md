# Recovery — Historical Simulation Spine

- **Classification:** Architecture + Implementation (recovery)
- **Branch:** `recovery/historical-simulation-spine` @ `1a1474d2c57241ea63bca190076af90640203ea4` (Document Phase 6 startup)
- **Status:** Planning → awaiting build
- **Scope:** Clean spine from known-good Phase 6 → StrategyMarketDataRequirement → ProviderCapability → V2 native M15 + sparse M1 → immutable V2 snapshot → runner → results/chart → UI load/run — one real one-month OANDA flow
- **Reference stash:** `stash@{0}` = pre-recovery dirty `feature/experiment-usability-historical-data-timezone` (do not merge wholesale; cherry-pick proven pieces)
- **Approved decisions:** StrategyMarketDataRequirement (M15 MID, 100/200 context), ProviderCapability (native M15 MID + sparse M1 BID/ASK), V2 `ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2` preserved, `aggregate_m1_to_m15` V1-only, 200 conservative context, execution M1 BID/ASK sparse valid, America/Chicago display only, 90d/40w bounds

## CodeGraph Summary (recovery base)
- `backend/strategies/contract.py` + `ema_sweep_engulfing_v2.py` own current `primary_timeframe=M15` and `warm_up_bars=200` but without `RequiredHistoricalContext` value object — to be introduced.
- `backend/persistence/models.py` (`StrategyVersionModel.warm_up_bars`, `DatasetSnapshotModel` V1 conditional, `MarketBarModel m1_only`) is V1-only provenance; V2 not present on base.
- `backend/market_data/{aggregation,coverage,ingestion,session_calendar}.py` assumes M1→M15 derived path and 25h wall-clock completeness — must be split to V1-only vs V2-native.
- `backend/integrations/oanda/source.py` already has `fetch_ohlc` primitive but dirty stash adds `fetch_native_m15` + `fetch_sparse_m1` correctly — to be cleanly reintroduced via ProviderCapability.
- `backend/experiments/{clock,runner,configuration,results}.py` currently assumes derived M15 input and M1 triple completeness — must dispatch V1 derived vs V2 native.

Risks: V1 compatibility must stay readable; migration triggers must be table-name-aware (see stash `0011` fix); fingerprint determinism must survive gap/policy metadata.

## Architecture Decision (1 paragraph)
Start from `1a1474d` (Phase-6 green). Introduce `StrategyMarketDataRequirement` (`AnalyticalRequirement` M15 MID UTC_HALF_OPEN_V1 + `RequiredHistoricalContext` 100/200 eligible M15) owned by StrategyVersion; introduce small `ProviderCapability` (OANDA native M15 MID + sparse M1 BID/ASK) and resolve loader through it; re-apply V2 migrations `ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2` (analytical M15, execution BID/ASK, gaps, result_quality/gap_decisions) with V1 backfill; make `aggregate_m1_to_m15` explicitly V1-only and wire V2 to provider-native M15 (never reconstructed); keep execution M1 sparse valid, 90d/40w, America/Chicago display-only, deterministic V2 fingerprint. Each stage adds focused regression and keeps V1 green.

## Ordered Tasks

| Order | Status | Task | Artifact | Depends |
|---|---|---|---|---|
| 1 | pending | Clean recovery branch verified (done) + V2 migration skeleton | dispatch/workstreams/recovery-historical-simulation-spine/TASK-01.md | — |
| 2 | pending | StrategyMarketDataRequirement (analytical + context, 100/200, zero/PA-ready) | TASK-02.md | 1 |
| 3 | pending | ProviderCapability (OANDA native M15 MID + sparse M1 BID/ASK value object) | TASK-03.md | 2 |
| 4 | pending | V2 native acquisition + immutable snapshot (analytical/execution/gaps, V2 fingerprint, result_quality) | TASK-04.md | 3 |
| 5 | pending | Experiment runner V2 dispatch (native M15 to Strategy, sparse BID/ASK to execution, gap decisions) | TASK-05.md | 4 |
| 6 | pending | Results/chart + durable historical load API/UI | TASK-06.md | 5 |
| 7 | pending | Validation: fixtures + live one-month OANDA (server-only) + deterministic rerun | VALIDATION.md | 6 |
| 8 | pending | Review + closure | REVIEW.md | 7 |

## Approval Record

- 2026-08-25 UTC — Recovery audit approved; branch `recovery/historical-simulation-spine` @ `1a1474d` approved; decisions 1-8 (Requirement, ProviderCapability, V2, M15 native, 200 context, execution M1 sparse, America/Chicago, 90d/40w) explicitly approved. Proceed sequential, no dirty wholesale copy.

## Implementation Receipts

| Task | Status | Receipt |
|---|---|---|
| — | — | — |

## Validation Section

| Check | Result | Evidence |
|---|---|---|
| — | — | — |


## Latest Validation (2026-08-25 recovery branch)

- Alembic 0011 head PASS, 258 core passed, typecheck/lint PASS, web 22/23 (1 pre-existing deferred), migrations integration 2 passed.
- Spine rebuilt sequentially 1-6 on `recovery/historical-simulation-spine` @ `1a1474d`; reference stash untouched.
- Deferred: live OANDA month requires server token + manual UI run — not a code failure.

