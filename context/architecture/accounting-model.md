# Accounting Model

## Purpose

The Accounting Model defines the minimum financial state Atlas needs to size trades, track realized/unrealized P&L, calculate equity, evaluate drawdown, support Experiments, and normalize PAPER/LIVE account state. Atlas is not an accounting platform; do not build a general ledger.

## Core Principle

Simple explainable account model. For Experiments: starting capital + realized P&L + unrealized P&L - costs = current equity. For PAPER/LIVE: broker is authoritative for actual account state.

## Account State

Canonical state: base currency, balance/realized account value, unrealized P&L, equity, available margin, margin used, timestamp, source. Not every field required in every environment initially.

## Experiment Account

Simulated account with: starting_capital, realized_pnl, unrealized_pnl, equity. Margin-related values added when required. Do not create fake TradingAccount records for Experiments. Starting capital is immutable Experiment configuration.

## Balance / Unrealized P&L / Equity

balance = starting capital + realized net P&L (open unrealized P&L not included in balance). Unrealized P&L uses relevant executable liquidation side (Long: BID, Short: ASK). Do not value open Positions using MID for executable exposure unless explicitly documented. equity = balance + unrealized P&L. Equity is primary value used by Risk unless stated otherwise.

## Realized P&L

Created when exposure reduced/closed through actual Fill(s). Trade P&L derives from actual Fill prices, not requested Order prices.

## Gross / Net P&L / Costs

Gross P&L = (exit - entry) × quantity for long, (entry - exit) × quantity for short. Track costs separately: spread, slippage, commission, financing. Net P&L = gross P&L - explicit costs. Spread already reflected through BID/ASK Fill prices — do not double-count.

## Spread / Slippage / Commission / Financing

Spread embedded in executable BID/ASK prices; may still calculate analytic impact. Slippage distinct from spread — deviation between expected reference and actual Fill. Commission included only when charged or explicitly modeled. Forex financing: if modeled → apply; if excluded → FINANCING EXCLUDED disclosed in results. Do not silently represent unavailable data as zero-cost.

## Trade / Position Accounting

Trade exposes: entry/exit Fill values, gross/net P&L, spread/slippage/commission/financing, R multiple. Position derives: quantity, direction, average entry price, unrealized P&L. Do not use Position as permanent historical record.

## Fill Authority

Accounting changes originate from canonical Fill facts: Fill → Position update → Trade update → realized/unrealized account update. Not: Order submitted → assume value changed.

## Atomic Updates

Local trading-state updates from one Fill persisted atomically where practical. Do not hold database transactions open while waiting on broker network requests.

## Base Currency / Currency Conversion

Every account has a base currency. Initial: USD. Risk/P&L logic must not assume every Instrument is quoted in account currency. Initial EUR/USD + USD case is simpler; do not hardcode throughout architecture.

## Risk Equity / Drawdown / Daily Loss

Initial sizing: current equity × risk_per_trade = risk budget. Drawdown derives from equity history (current equity relative to peak). Daily loss rules use explicitly defined facts; policy must be unambiguous and tested.

## Equity History

Experiments retain sufficient time-series info to reproduce equity curve, drawdown curve, max drawdown, performance metrics. Do not store only final headline metrics.

## Experiment End

If Position open at end: close at final eligible executable price with exit reason END_OF_EXPERIMENT.

## PAPER / LIVE

Broker-reported state is authoritative. Atlas projections for UI use, but reconciliation must compare with broker truth. Do not treat Atlas-calculated equity as more authoritative than OANDA.

## Broker Normalization

OANDA adapter normalizes account values into canonical state. Provider-specific names (NAV, marginAvailable, marginUsed) translated at adapter boundary. Do not leak OANDA response models through Risk or domain code.

## Simulation / Broker Parity

Experiment and broker account state do not need identical internal implementations. Both expose common economic info (current equity, exposure, margin where required). Risk should not care which environment produced it.

## No Ledger

Do not introduce double-entry accounting, journal-entry tables, chart of accounts, or generalized cash-flow ledger. Fills, Trades, costs, and equity history are sufficient for initial analytics.

## Numeric Precision

Decimal-safe financial representations. Persist with PostgreSQL NUMERIC. Use Python Decimal where exact arithmetic matters. No binary floating-point for authoritative financial storage.

## Derived Metrics

Metrics (return, drawdown, expectancy, profit factor, Sharpe) are derived analytics. Primary facts: Fills, Trades, costs, account/equity history.

## Required Tests

At minimum test: starting capital, long/short realized P&L, long unrealized P&L using BID, short unrealized P&L using ASK, balance vs equity, cost application, no spread double-counting, slippage, commission, financing exclusion disclosure, base-currency handling, drawdown calculation, end-of-Experiment close, Fill-driven updates, deterministic Risk equity from identical inputs.

## Success Criteria

Sufficient when Atlas can: start Experiment with capital → size Trade → process Fills → maintain Position value → calculate realized/unrealized P&L → apply supported costs → update equity → derive drawdown → produce final net performance — without a general accounting subsystem.
