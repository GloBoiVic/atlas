# Dispatch Plan

## What we are building

Feature 06 — Risk Engine: a deterministic, broker-agnostic risk gate enforcing a
maximum 2% of current account equity per trade, with configuration-driven stop
resolution and shared behavior for paper trading and backtesting.

## Complexity tier

Feature with trading-safety implications.

## Authoritative blueprint

`dispatch/ARCHITECTURE.md` owns the implementation design. Implementers must follow it
without deviation.

## Sequential tasks

1. Revise the blueprint to incorporate the approved no-ATR stop policy and take-profit
   boundary.
2. Implement event/configuration contracts and the pure Risk Engine evaluator.
3. Implement the EventBus adapter and complete tests/quality gates.
4. Review the completed Feature 06 against the blueprint and safety constraints.

## Approved decisions

- Maximum risk per trade is 2% of current account equity.
- Default risk per trade is 1%.
- ATR is not required for the MVP.
- Stop sources are percentage of entry, absolute distance, or explicit stop price.
- Missing or invalid stops reject the signal.
- Strategy stop proposals may be supported later but remain subject to Risk approval.
- No scaling or automatic reversal in the MVP.
- CLOSE is an approved zero-quantity close intent.
- Take-profit is optional and, when configured, uses a risk/reward multiple.

## Explicit non-goals

- No execution engine, broker, persistence, migrations, API, or UI.
- No ATR calculation, trailing stops, daily loss limits, drawdown halts, or leverage.
