# Task 06 — Results/Chart + UI Load/Run Flow

## Status
**DONE** (restored from validated stash)

- `backend/experiments/results.py` — price-analysis reads V2 native M15 + backend-authoritative `indicators_v2.ema(period from parameter_snapshot)` over `last warm_up_bars` M15 `end_time <= trading_start` + trading window; caps 10k candles / 250 trades; `PERSISTED_NATIVE_M15_MID` vs `DERIVED_M15_FROM_V1_M1` provenance + `SPARSE_PROVIDER_M1_BID_ASK`; FAIL 409 on missing lineage
- `backend/api/experiments.py` + `schemas.py` + `api/app.py` — wires `historical_data` router, V2 coverage/validation, gap disclosure
- Frontend:
  - `frontend/lib/time.ts` + `utc-date-time-picker.tsx` + `providers.tsx` (America/Chicago default, four-zone selector, UTC labels, quarter-hour `parseUtcInput`, DST gap/fold handled)
  - `frontend/components/experiment-workflow.tsx` — 1W/1M/3M presets, `loadRange` preview warm-up inclusive, Load disabled >90d, durable polling (scalar deps, HISTORICAL_LOAD_NOT_ACTIVE→null quiet), proof line, bounded error disclosure, human snapshot labels
  - `frontend/lib/api-client.ts` + `api.generated.ts` — regenerated historical-data contract
  - `frontend/tests/time.test.ts` + `price_analysis.test.tsx` — gaps correct

`America/Chicago` is display-only; canonical times, fingerprints, snapshot bounds, candle alignment, execution semantics remain UTC.

## Verification
- `npm run typecheck:web` — PASS
- `npm run lint:web` — PASS
- `npm run test:web` — 8/9 files PASS, 22/23 tests PASS; 1 failure `focused Trade detail → createChart` is pre-existing deferred frontend failure (same as stash BLOCKED validation; no regression), not a backend acceptance blocker

