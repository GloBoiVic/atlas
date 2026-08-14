# Reference Strategy

## Purpose

Atlas's first reference Strategy: EMA Sweep Engulfing. Phase 1 proves the Strategy slice itself: public Strategy contract, completed-bar handling, deterministic evaluation, and immutable versioned provenance. Its further capabilities — deterministic Experiments, Risk integration, PAPER/LIVE reuse — are proven in later phases, not as part of Phase 1 acceptance.

## Configuration

EUR/USD MID 15m bars, EMA 100, ATR 14, 0.5 ATR stop buffer, 1.7R target, 5-candle confirmation window measured from reference selection: W1–W5 count received canonical completed evaluation bars, not elapsed wall-clock time. Exposed through Strategy parameter schema. Indicator warm-up requires 100 supplied completed bars; with exposure enabled, fewer supplied bars is an input error, not silent warm-up.

Phase 1 scope is fixed: EUR/USD, MID, 15m only. 5m or 1m evaluation is explicitly deferred future work — not a configurable timeframe, resampling feature, or generalized implementation. No timeframe parameters or multi-timeframe abstractions are added in Phase 1.

## Candle Classification

Bullish: close > open. Bearish: close < open. Doji: close == open (not bullish/bearish for setup logic).

## Reference Window

Selecting a reference candle establishes that bar as the fixed reference and starts a window comprising exactly the next five received canonical completed evaluation bars: W1–W5. The reference candle is not one of the five and cannot serve as its own sweep/confirmation candle. The count is bar-based, not clock-based: elapsed wall-clock time and missing 15m intervals neither consume a slot nor are fabricated, and the count advances only when a received completed evaluation bar is processed. Sweep and confirmation must occur on one of W1–W5 and may occur on the same window bar. Confirmation on W5 is a valid OPEN. The count advances from reference selection whether or not a sweep has occurred.

## Long Setup

1. **Trend Filter (reference qualification only)**: close > EMA(100) on the completed 15m bar. The EMA trend relation is evaluated only while searching, to decide whether the current completed candle qualifies as a reference. It is not re-evaluated as a validity condition afterward.
2. **Reference Candle**: Identify completed bearish candle that passes the trend filter. Store: reference_high, reference_low, reference_time.
3. **Sweep**: Completed bullish candle within W1–W5 with low < reference_low AND close > open. Setup becomes active (AWAITING_CONFIRMATION). Store sweep_time.
4. **Confirmation**: Completed bullish candle with close > reference_high, on the sweep candle or a later candle within W1–W5.
5. **Entry Decision**: OPEN_LONG on confirmation-candle completion. Strategy does not submit Order.
6. **Stop**: confirmation_candle_low - (0.5 × ATR). ATR from completed 15m bars at confirmation time.
7. **Target**: 1.7R where R = executable_entry_price - stop_price. Target = entry_price + (1.7 × R). Uses actual executable entry, not the confirmation-candle close.

## Short Setup (exact inverse)

Trend (reference qualification only): close < EMA(100). Reference: completed bullish candle. Sweep: bearish candle within W1–W5 with high > reference_high, close < open. Confirmation: close < reference_low. Entry: OPEN_SHORT. Stop: confirmation_candle_high + (0.5 × ATR). Target: entry_price - (1.7 × R).

## Setup Expiration

The only window-based reset is failure to emit OPEN by the close of the fifth received canonical completed evaluation bar after reference selection (W5). If processing W5 does not produce OPEN — whether unswept, previously swept without confirmation, or a first sweep on W5 that fails confirmation — reset to SEARCHING. W5 is consumed only as the final window bar and must not be reconsidered as a new reference; search resumes with W6 or a later received completed bar. The window counts received bars: elapsed wall-clock time and interval gaps neither expire a setup nor consume a slot.

The exposure-allowed and Position boundaries below independently clear pending state; they are not window-expiry events.

No EMA-cross invalidation: once a reference is selected, later EMA trend changes neither replace nor invalidate the setup, before or after a sweep. The fixed unswept reference remains valid for its five-candle window even if price later crosses the EMA; a swept pending setup likewise remains valid through that same window. The EMA trend is a reference-selection predicate only.

## State Model

SEARCHING → REFERENCE_IDENTIFIED → AWAITING_CONFIRMATION → ENTRY_DECISION (transient output) → SEARCHING. Only SEARCHING, REFERENCE_IDENTIFIED, and AWAITING_CONFIRMATION are persisted; ENTRY_DECISION is a transient output, not a persisted phase. Selecting the reference leaves the state active with zero window bars processed; each received and processed window bar advances the count from reference selection whether or not a sweep has occurred. With exposure disallowed, evaluation returns NO_ACTION, remains SEARCHING with all pending setup fields cleared, and neither selects a reference nor creates or advances a setup. A non-FLAT Position behaves identically. An OPEN is a transient output whose next_state resets to SEARCHING; a later bar may be eligible for reference selection only if the context remains FLAT.

## Persisted Strategy State

State: phase, direction, reference_high/low/time, optional sweep_time, window-candle count since reference selection (received canonical completed evaluation bars processed), last evaluated bar end. Persist only what is required to continue deterministic evaluation after restart. No whole DataFrames or indicator objects.

## Additional Rules

- Deterministic reference-candle selection; once active, later opposite candles don't silently replace it.
- After expiration or OPEN: search for a new reference from subsequent received bars. An expired W5 is never reused as a reference; search resumes with W6 or a later received completed bar. After OPEN the next_state is SEARCHING, and a later bar is eligible for reference selection only if the caller-supplied Position remains FLAT.
- While Position exists: no new OPEN_LONG/OPEN_SHORT (no pyramiding). Whenever the Position is non-FLAT, evaluation returns NO_ACTION, advances only the duplicate-detection frontier, clears all pending setup fields, remains SEARCHING, and neither selects a reference nor emits OPEN.
- Exposure disallowed: when exposure_allowed=false, evaluation returns NO_ACTION, advances only the duplicate-detection frontier, remains SEARCHING with all pending setup fields cleared, and neither selects a reference nor creates or advances a setup; it never emits OPEN. Indicator calculation remains deterministic but creates no methodology continuation state.
- Normal exits: stop loss and 1.7R take profit.
- All logic uses completed 15m bars only. Never inspect partially formed candles.
- Analysis price: MID 15m bars (candle pattern, EMA, ATR). Execution price separate: BID/ASK.
- One canonical EMA and ATR implementation, deterministic and centralized. No different implementations across Experiment/PAPER/LIVE.
- Strategy decision on confirmation-candle completion; execution at first eligible post-decision executable observation. Do not assume entry at confirmation close.
- Rationale at decision time: trend state at reference selection, reference/sweep/confirmation candles, ATR value, proposed stop structure. Environment independent (no Experiment/PAPER/LIVE branching).

## Non-Goals

No generic Atlas engine may contain special-case logic for this Strategy. No trailing stops, discretionary exits, partial exits, scale-ins, instant reversal. No 5m/1m evaluation, configurable timeframes, or cross-timeframe behavior in Phase 1.

## Required Tests

Bullish/bearish/doji classification, EMA trend filter at reference selection only, reference identification, sweep detection (strict inequality; equality is not a sweep), same-candle sweep/confirmation, delayed confirmation, confirmation on the fifth window bar (W5), no OPEN by W5 close expires unswept and swept setups including a W5 sweep that fails confirmation, expired W5 not reused as a reference (search resumes with W6 or later), unswept and swept setups survive later EMA trend reversal, deterministic reference retention, no duplicate entry while Position exists, exposure disallowed returns NO_ACTION and stays SEARCHING without selecting or advancing a setup, non-FLAT Position clears pending state and stays SEARCHING without reference selection or OPEN, OPEN returns next_state SEARCHING with renewed selection only on a subsequent FLAT bar, elapsed wall-clock time and missing 15m intervals neither consume window slots nor fabricate bars, state serialization, restart with active setup, EMA/ATR behavior, proposed long/short stop, 1.7R target based on actual entry, completed-bar behavior, identical inputs → identical outputs.

## Acceptance Examples

**Long**: Price above EMA 100 at reference selection → bearish reference → within W1–W5 a bullish candle sweeps the reference low → the same or a later window candle closes above the reference high → OPEN_LONG.
**Short**: Price below EMA 100 at reference selection → bullish reference → within W1–W5 a bearish candle sweeps the reference high → the same or a later window candle closes below the reference low → OPEN_SHORT.
**Fifth-candle confirmation**: Confirmation on W5 is a valid OPEN.
**Expiry**: No OPEN by the close of W5 (unswept or swept) → reset to SEARCHING; W5 is not reused as a reference; search resumes with W6 or a later completed candle.
**No invalidation**: Price crossing the EMA during the window, before or after a sweep, neither replaces nor invalidates the setup.
**Exposure disallowed**: evaluation returns NO_ACTION, remains SEARCHING with pending setup cleared, and neither selects a reference nor creates or advances a setup.
**Position non-FLAT**: evaluation returns NO_ACTION from any phase, clears pending setup, remains SEARCHING, and neither selects a reference nor emits OPEN.

## Success Criteria

Deterministically: identify reference → detect sweep → persist active setup → confirm or expire → produce the correct Strategy decision for both long and short using the public Atlas Strategy contract, convertible to a canonical TradeIntent by a later phase.