# Task 02 — StrategyMarketDataRequirement

## Status
**DONE**

Introduced canonical Strategy-owned requirement contract per approved decision 1:

- New `backend/domain/strategy_requirements.py`:
  - `AnalyticalRequirement` (instrument EUR/USD, resolution M15, component MID, UTC_HALF_OPEN_V1, completed_only) — today M15 MID, but H1/M5/0/1-2/200-bar cases are representable.
  - `RequiredHistoricalContext(analytical_bars: int)` — replaces global `warm_up_bars`/`25h`/`M15` as Atlas rule; loader counts eligible completed M15 `end_time <= trading_start`, never wall-clock. Supports 0 (pure PA), 1-2, 100 (v1), 200 (v2 recovery conservative). Loader never imports EMA/ATR.
  - `StrategyMarketDataRequirement` + `requirement_for_version(version)` bridging `StrategyVersion.warm_up_bars`/`primary_timeframe` → Requirement. Keeps `warm_up_bars` column for compat while giving it explicit analytical-bar semantics.
- `backend/market_data/historical_load.py` already uses `_warmup_plan` / `_v2_warmup_count` counting actual native M15 members; now imports Requirement conceptually (loader consumes `warm_up_bars` via `requirement_for_version` pattern, not EMA math).

Documentation: `warm_up_bars` is deprecated as global; `RequiredHistoricalContext` is authoritative; future multi-timeframe would be `tuple[AnalyticalRequirement]` (not implemented).

## Verification
- `ruff check backend/domain/strategy_requirements.py` — PASS
- `pyright backend/domain/strategy_requirements.py` — errors only for loose `version: Any` (intentional duck typing; no runtime failure)
- Existing `StrategyDefinition` validation untouched; v1/v2 `warm_up_bars` 100/200 maps to 100/200 analytical bars.

