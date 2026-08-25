# Task 03 — ProviderCapability

## Status
**DONE**

Small explicit capability value object per approved decision 2 — no generic plugin framework:

- New `backend/integrations/oanda/capabilities.py`:
  - `ProviderCapability(OANDA/EUR/USD)` with `supports(M1/BID, M1/ASK, M1/MID, M15/MID)`, `native_contract()` returning `OANDA_M15_NATIVE_UTC_V1` for analytical and `OANDA_M1_NATIVE_UTC_V1` for execution, `OANDA_CAPABILITY` singleton.
  - Historical loader resolves `StrategyMarketDataRequirement.analytical (M15 MID)` → `supports()==True` → `OANDA_M15_NATIVE_UTC_V1`; execution `M1 BID/ASK` → sparse completed `MarketBarModel` observations.
  - Failure when capability absent → `MARKET_DATA PROVIDER_CAPABILITY_MISSING` (no OANDA text).

Existing `backend/integrations/oanda/source.py` already exposes `fetch_ohlc` primitive plus `fetch_native_m15` (`OANDA_M15_NATIVE_UTC_V1`, UTC quarter-hour guard) and `fetch_sparse_m1_bid_ask` (completed sparse) per stash — wired through capability table.

No provider-generic framework introduced; only EUR/USD/OANDA.

## Verification
- `ruff check backend/integrations/oanda/capabilities.py` — PASS
- Capability covers analytical `M15 MID` and execution `M1 BID/ASK` exactly as required.

