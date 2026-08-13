# Reference Strategy

## Purpose

Atlas's first reference Strategy: EMA Sweep Engulfing. Proves: public Strategy contract, completed-bar handling, state persistence, deterministic Experiments, Risk integration, PAPER/LIVE reuse.

## Configuration

EUR/USD, 15m, EMA 100, ATR 14, 0.5 ATR stop buffer, 1.7R target, 5-bar confirmation expiry. Exposed through Strategy parameter schema.

## Candle Classification

Bullish: close > open. Bearish: close < open. Doji: close == open (not bullish/bearish for setup logic).

## Long Setup

1. **Trend Filter**: close > EMA(100) on completed 15m bars.
2. **Reference Candle**: Identify completed bearish candle. Store: reference_high, reference_low, reference_time.
3. **Sweep**: Later completed bullish candle with low < reference_low AND close > open. Setup becomes active. Store sweep_time.
4. **Confirmation**: Completed bullish candle with close > reference_high. May occur on sweep candle or later within expiry.
5. **Entry Decision**: OPEN_LONG on confirmation-candle completion. Strategy does not submit Order.
6. **Stop**: entry_candle_low - (0.5 × ATR). ATR from completed 15m bars at confirmation time.
7. **Target**: 1.7R where R = executable_entry_price - stop_price. Target = entry_price + (1.7 × R). Uses actual executable entry, not signal close.

## Short Setup (exact inverse)

Trend: close < EMA(100). Reference: completed bullish candle. Sweep: bearish candle high > reference_high, close < open. Confirmation: close < reference_low. Entry: OPEN_SHORT. Stop: entry_candle_high + (0.5 × ATR). Target: entry_price - (1.7 × R).

## Setup Expiration / Trend Invalidation

Once sweep activates setup: sweep may confirm immediately; otherwise 5 subsequent 15m candles for confirmation. If no confirmation by close of 5th: setup expired. Sweep candle itself does not count as one of five subsequent bars. Pending long expires immediately if close <= EMA(100) before entry; short if close >= EMA(100).

## State Model

SEARCHING → REFERENCE_IDENTIFIED → SWEEP_ACTIVE → AWAITING_CONFIRMATION → ENTRY_DECISION → SEARCHING. Implementation may simplify equivalent states if behavior identical.

## Persisted Strategy State

State: direction, reference_high/low/time, sweep_time, confirmation_bars_elapsed. Persist only what required to continue deterministic evaluation after restart. No whole DataFrames or indicator objects.

## Additional Rules

- Deterministic reference-candle selection; once active, later opposite candles don't silently replace it.
- After expiration/invalidation/completed Trade/reset: search for new reference from subsequent bars.
- While Position exists: no new OPEN_LONG/OPEN_SHORT (no pyramiding).
- Normal exits: stop loss and 1.7R take profit.
- All logic uses completed 15m bars only. Never inspect partially formed candles.
- Analysis price: MID 15m bars (candle pattern, EMA, ATR). Execution price separate: BID/ASK.
- One canonical EMA and ATR implementation, deterministic and centralized. No different implementations across Experiment/PAPER/LIVE.
- Strategy decision on confirmation-candle completion; execution at first eligible post-decision executable observation. Do not assume entry at confirmation close.
- Rationale at decision time: trend state, reference/sweep/confirmation candles, ATR value, proposed stop structure. Environment independent (no Experiment/PAPER/LIVE branching).

## Non-Goals

No generic Atlas engine may contain special-case logic for this Strategy. No trailing stops, discretionary exits, partial exits, scale-ins, instant reversal.

## Required Tests

Bullish/bearish/doji classification, long/short trend filter, reference identification, sweep detection, sweep immediate confirmation (long+short), delayed confirmation, confirmation on 5th bar, expiry after 5th failed, trend invalidation (long+short), deterministic reference retention, no duplicate entry while Position exists, state serialization, restart with active setup, EMA/ATR behavior, proposed long/short stop, 1.7R target based on actual entry, completed-bar behavior, identical inputs → identical outputs.

## Acceptance Examples

**Long**: Price above EMA 100 → bearish reference → bullish candle sweeps reference low → within window: bullish closes above reference high → OPEN_LONG.
**Short**: Price below EMA 100 → bullish reference → bearish candle sweeps reference high → within window: bearish closes below reference low → OPEN_SHORT.

## Success Criteria

Deterministically: identify reference → detect sweep → persist active setup → confirm or expire → produce correct TradeIntent structure for both long and short using the public Atlas Strategy contract.
