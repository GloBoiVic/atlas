# Dispatch Plan

## What we are building

Feature 07 — Execution Layer: a broker-agnostic, Futures-shaped execution core for
Binance USDⓈ-M `BTCUSDT` perpetuals. It will provide deterministic paper execution,
durable order/fill/position/trade state, netted multi-strategy exposure, margin and
liquidation behavior, and fail-closed reconciliation contracts. Authenticated Binance
connectivity remains a later Feature 09 slice.

## Complexity tier

Architecture-level feature with trading-safety implications.

## Authoritative blueprint

`dispatch/ARCHITECTURE.md` owns the implementation design. Implementers must follow it
without deviation.

## Sequential tasks

1. Implement the approved execution domain contracts, event payloads, and state machines.
2. Implement repositories/migrations and the Futures-aware Paper Broker with deterministic
   fees, funding, margin, liquidation, and protective-exit behavior.
3. Implement account-level net exposure coordination, FIFO strategy attribution, and the
   Execution Engine integration with RiskApproved.
4. Implement broker reconciliation contracts, startup/unknown-order recovery, and the
   remaining reconciliation tests.
5. Run quality gates and review the completed Feature 07 against the authoritative blueprint
   and safety rules.

## Approved decisions

- Initial authenticated target: Binance USDⓈ-M Futures `BTCUSDT` perpetual.
- Isolated margin; default leverage 1×; hard maximum leverage 2×.
- One-way position mode; no Hedge Mode in the MVP.
- Different strategies may trade the same account/instrument; duplicate active
  `(account, instrument, strategy)` combinations are rejected.
- Each bot has virtual strategy exposure; the broker receives one account-level net position.
- Opposing exposure is allocated FIFO by virtual-position opening time.
- Reversals are explicit close-then-open sequences, never implicit flips.
- Protective exits are Atlas-managed, reduce-only, and use mark price for triggers.
- Backtest fills use next-candle open; live paper fills use executable bid/ask context.
- Paper execution models margin, funding, maintenance margin, and deterministic liquidation.
- Futures taker fee default is configurable, initially 0.05%; funding is separate.
- Client order IDs are persisted before broker submission; unknown states block retries.
- Broker streams provide updates; REST snapshots are authoritative during reconciliation.
- Feature 07 excludes authenticated Binance connectivity, which belongs to Feature 09.

## Explicit non-goals

- No Binance REST/WebSocket adapter or live/testnet credentials.
- No production trading, cross-margin, Hedge Mode, or leverage above 2×.
- No limit-order, smart-routing, OCO, or broker-native protective-order implementation.
- No distributed messaging or cross-worker coordination.
