# Reference Strategy

## Purpose

Atlas's current reference Strategy is **EMA Sweep Confirmation Break v2**. It
uses the public Strategy contract, completed native M15 MID bars, deterministic
evaluation, and immutable versioned provenance. Legacy EMA Sweep Engulfing text
is historical only and is not the current production methodology.

## Configuration

EUR/USD native M15 MID bars, EMA 100, ATR 14, 0.5 ATR stop buffer, 1.7R
target, same-bar sweep/confirmation, and a five-bar pending-trigger window.
W1–W5 count received canonical completed evaluation bars, not elapsed wall-clock
time. Exposed through the Strategy parameter schema. Indicator warm-up requires
100 supplied completed bars; fewer is an input error, not silent warm-up.

Phase 1 scope is fixed: EUR/USD, MID, 15m only. 5m or 1m evaluation is explicitly deferred future work — not a configurable timeframe, resampling feature, or generalized implementation. No timeframe parameters or multi-timeframe abstractions are added in Phase 1.

## Candle Classification

Bullish: close > open. Bearish: close < open. Doji: close == open (not bullish/bearish for setup logic).

## Reference Window

Selecting a reference candle establishes that bar as the fixed reference. The next received canonical completed evaluation bar is the sole sweep/confirmation opportunity: it must satisfy the direction-specific strict sweep on that same bar, which is the immediate price-triggered decision event. After the decision, ARMED watches exactly five subsequent received canonical completed evaluation bars, W1–W5, for trigger eligibility/expiry. Counts are bar-based, not clock-based: elapsed wall-clock time and missing 15m intervals neither consume a slot nor are fabricated.

## Long Setup

1. **Trend Filter (reference qualification only)**: close > EMA(100) on the completed 15m bar. The EMA trend relation is evaluated only while searching, to decide whether the current completed candle qualifies as a reference. It is not re-evaluated as a validity condition afterward.
2. **Reference Candle**: Identify completed bearish candle that passes the trend filter. Store: reference_high, reference_low, reference_time.
3. **Immediate sweep decision**: The next completed bar must be bullish and sweep the reference low strictly (`low < reference_low`). This same-bar strict sweep is the immediate price-triggered decision event; no close-through-reference-high requirement applies. Later completed analytical bars only advance the pending-trigger watch window.
4. **Entry Decision**: Emit an OPEN_LONG price-triggered decision on confirmation-candle completion and enter ARMED with its trigger price. Strategy does not submit Order; a later eligible sparse native M1 ASK observation may fill the trigger.
6. **Stop**: confirmation_candle_low - (0.5 × ATR). ATR from completed 15m bars at confirmation time.
7. **Target**: 1.7R where R = executable_entry_price - stop_price. Target = entry_price + (1.7 × R). Uses actual executable entry, not the confirmation-candle close.

## Short Setup (exact inverse)

Trend (reference qualification only): close < EMA(100). Reference: completed bullish candle. Immediate sweep decision: the next completed bar must be bearish and sweep the reference high strictly (`high > reference_high`). No close-through-reference-low requirement applies. Entry: OPEN_SHORT price-triggered decision with its trigger price; a later eligible sparse native M1 BID observation may fill it. Stop: confirmation_candle_high + (0.5 × ATR). Target: entry_price - (1.7 × R).

## Setup Expiration

The only window-based reset is failure to fill the ARMED price trigger during the five received canonical completed evaluation bars after the confirmation decision (W1–W5). W5 remains eligible for execution observations; expiry is observed at the next completed analytical frontier (W6), and search resumes with W6 or a later received completed bar. The window counts received bars: elapsed wall-clock time and interval gaps neither expire a setup nor consume a slot.

The exposure-allowed and Position boundaries below independently clear pending state; they are not window-expiry events.

No EMA-cross invalidation: once a reference is selected, the next-bar sweep/confirmation decision does not re-evaluate the EMA trend; later EMA changes do not affect the ARMED pending trigger. The EMA trend is a reference-selection predicate only.

## State Model

SEARCHING → REFERENCE_IDENTIFIED → ARMED → OPEN (transient output) → SEARCHING. Only SEARCHING, REFERENCE_IDENTIFIED, and ARMED are persisted; OPEN is a transient price-triggered decision output. Confirmation is immediate on the sweep bar; ARMED carries the trigger and exact received-bar W1–W5 pending-trigger count while later completed analytical bars are watched for expiry. With exposure disallowed or a non-FLAT Position, evaluation returns NO_ACTION, clears pending setup fields, remains SEARCHING, and advances only the duplicate-detection frontier.

## Persisted Strategy State

State: phase, direction, reference_high/low/time, optional sweep_time, pending-trigger watch count after confirmation (received canonical completed evaluation bars processed), last evaluated bar end. Persist only what is required to continue deterministic evaluation after restart. No whole DataFrames or indicator objects.

## Additional Rules

- Deterministic reference-candle selection; once active, later opposite candles don't silently replace it.
- After expiration or OPEN: search for a new reference from subsequent received bars. An expired W5 is never reused as a reference; search resumes with W6 or a later received completed bar. After OPEN the next_state is SEARCHING, and a later bar is eligible for reference selection only if the caller-supplied Position remains FLAT.
- While Position exists: no new OPEN_LONG/OPEN_SHORT (no pyramiding). Whenever the Position is non-FLAT, evaluation returns NO_ACTION, advances only the duplicate-detection frontier, clears all pending setup fields, remains SEARCHING, and neither selects a reference nor emits OPEN.
- Exposure disallowed: when exposure_allowed=false, evaluation returns NO_ACTION, advances only the duplicate-detection frontier, remains SEARCHING with all pending setup fields cleared, and neither selects a reference nor creates or advances a setup; it never emits OPEN. Indicator calculation remains deterministic but creates no methodology continuation state.
- Normal exits: stop loss and 1.7R take profit.
- All logic uses completed 15m bars only. Never inspect partially formed candles.
- Analysis price: MID 15m bars (candle pattern, EMA, ATR). Execution price separate: BID/ASK.
- One canonical EMA and ATR implementation, deterministic and centralized. No different implementations across Experiment/PAPER/LIVE.
- Price-triggered Strategy decision on confirmation-candle completion; execution at the first eligible post-decision sparse native M1 executable observation. Do not assume entry at confirmation close.
- Rationale at decision time: trend state at reference selection, reference/sweep/confirmation candles, ATR value, proposed stop structure. Environment independent (no Experiment/PAPER/LIVE branching).

## Non-Goals

No generic Atlas engine may contain special-case logic for this Strategy. No trailing stops, discretionary exits, partial exits, scale-ins, instant reversal. No 5m/1m evaluation, configurable timeframes, or cross-timeframe behavior in Phase 1.

## Required Tests

Bullish/bearish/doji classification, EMA trend filter at reference selection only, reference identification, strict sweep detection (equality is not a sweep), same-candle sweep/confirmation on the next completed bar, price-triggered ARMED output and sparse M1 fill handoff, post-confirmation ARMED trigger-watch behavior across received W1–W5 bars (with W5 still fill-eligible), and expiry at the W6 analytical frontier when no fill occurs, expired W5 not reused as a reference (search resumes with W6 or later), unswept setups survive later EMA trend reversal, deterministic reference retention, no duplicate entry while Position exists, exposure disallowed returns NO_ACTION and stays SEARCHING without selecting or advancing a setup, non-FLAT Position clears pending state and stays SEARCHING without reference selection or OPEN, OPEN returns next_state SEARCHING with renewed selection only on a subsequent FLAT bar, elapsed wall-clock time and missing 15m intervals neither consume window slots nor fabricate bars, state serialization, restart with active setup, EMA/ATR behavior, proposed long/short stop, 1.7R target based on actual entry, completed-bar behavior, identical inputs → identical outputs.

## Acceptance Examples

**Long**: Price above EMA 100 at reference selection → bearish reference → the next completed bar is bullish and strictly sweeps the reference low (`low < reference_low`) → immediate price-triggered OPEN_LONG decision and ARMED trigger; a later sparse M1 ASK may fill it.
**Short**: Price below EMA 100 at reference selection → bullish reference → the next completed bar is bearish and strictly sweeps the reference high (`high > reference_high`) → immediate price-triggered OPEN_SHORT decision and ARMED trigger; a later sparse M1 BID may fill it.
**Pending-trigger window**: After the sweep/confirmation decision, subsequent completed M15 bars advance the ARMED W1–W5 watch count; the trigger remains eligible for later sparse M1 execution observations until the window expires.
**Expiry**: No trigger fill during W1–W5 → the trigger expires at the W6 analytical frontier; search resumes with W6 or a later completed candle.
**No invalidation**: Price crossing the EMA after reference selection neither replaces nor invalidates the ARMED pending trigger.
**Exposure disallowed**: evaluation returns NO_ACTION, remains SEARCHING with pending setup cleared, and neither selects a reference nor creates or advances a setup.
**Position non-FLAT**: evaluation returns NO_ACTION from any phase, clears pending setup, remains SEARCHING, and neither selects a reference nor emits OPEN.

## Success Criteria

Deterministically: identify reference → detect sweep → persist active setup → confirm or expire → produce the correct Strategy decision for both long and short using the public Atlas Strategy contract, convertible to a canonical TradeIntent by a later phase.
