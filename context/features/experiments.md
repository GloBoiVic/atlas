# Experiments

## Purpose

Deterministic historical Experiments using the same canonical trading concepts as PAPER/LIVE. An Atlas backtest is an Experiment. Do not create a separate Experiment domain.

## Core Flow

Canonical pipeline: [Domain Model](../architecture/domain-model.md). Experiments replace the live broker with simulated components (SimulationClock, SimulatedExecutionAdapter, SimulatedAccount) while reusing the same Strategy/Risk/Order/Fill/Position/Trade types.

## Experiment Inputs

Preserve: StrategyVersion, Instrument, parameter snapshot, DatasetSnapshot, date range, starting capital + base currency, Risk configuration snapshot, simulation configuration, engine/version provenance. Completed config is immutable. Rerun → new Experiment.

## Reference Configuration

EMA Sweep Engulfing, EUR/USD, 15m Strategy, 1m simulation, MID analysis, BID/ASK execution, USD base.

## Simulation Clock / No Lookahead

Historical execution advances forward. At time T, only info available by T exposed. Strategy-visible bars: bar.end_time <= T. No lookahead.

## Strategy vs Simulation Resolution

Strategy evaluation: 15m. Execution simulation: 1m. Strategy evaluates only when completed 15m bar available. Simulator inspects later 1m observations for fills/protection. Strategy must not know simulation resolution.

## Signal-Bar Boundary

Decision only after full signal bar completes. Market data for completed bar not reused as post-decision entry data. Decision at 10:15 frontier for 10:00→10:15 bar; execution from first eligible observation after. Must be explicitly tested.

## Warm-Up

Prior history loaded → indicators initialized → trading disabled → requested period begins → trading enabled. Warm-up satisfies StrategyVersion requirements; may update state but no exposure attributed to Experiment period.

## Strategy Evaluation / Risk

Follows [Strategy Contract](../architecture/strategy-contract.md). Exact EMA Sweep Engulfing: [Reference Strategy](reference-strategy.md). Experiments use canonical Risk logic with simulated account/exposure state. Two-stage Risk: PRE_FLIGHT (structural eligibility) → executable context → PRE_SUBMISSION (valid at actual executable price, quantity). See [Risk Management](risk-management.md).

## Executable Entry / Stop Geometry / Target

Strategy does not assume entry at confirmation close. First executable entry after decision using post-decision data. Forex: Long BUY→ASK, Short SELL→BID. Simulated Fill price = economic entry. Risk validates stop geometry against executable entry. Long: stop < entry. Short: stop > entry. Market movement → PRE_SUBMISSION REJECTED. Target based on actual executable entry (not signal close). 1.7R: R = entry - stop (long), stop - entry (short).

## Simulated Execution

Uses SimulatedExecutionAdapter through same canonical execution boundary as external brokers. Produces canonical Order/OrderEvent/Fill. No BacktestOrder/BacktestFill/BacktestTrade. Initial: full fills assumed; domain supports multiple Fills for live partial fills. BID/ASK execution. Spread through executable prices — no double-count. Slippage separate from spread; deterministic explicit model (0, 1, N ticks adverse). No favorable price improvement.

## Protective Orders / Stop / Target / Gap-Through

Reference Strategy requires stop loss + take profit. Modeled after entry using canonical Order/Fill. Stops as stop-market: Long BID-side, Short ASK-side. Gap-through: fill at first eligible price after stop triggers — may be worse than requested. Targets as limit-style exits: fill at target. No positive price improvement.

## Intrabar Ordering / Ambiguity

OHLC doesn't reveal tick sequence. If same 1m bar contains both stop and target touched and sequence unknowable: adverse outcome first (stop wins). Record ambiguity. Experiment results expose ambiguous Trade count, affected Trades, resolution policy.

## Same-Bar Entry and Protection

If entry occurs and same subsequent bar could trigger protection: sequencing must obey actual simulation frontier. Stop/target cannot occur before entry Fill exists. Tested explicitly.

## Position / Trade / Exit Reasons

Canonical constraints apply: one Position, no pyramiding/partial exits/instant reversal. Trade opens on Fill(s) creating exposure; closes when exposure returns to zero. Initial historical exit reasons: TAKE_PROFIT, STOP_LOSS, END_OF_EXPERIMENT.

## Non-Goals

MANUAL_CLOSE and RISK_EXIT are deferred for Experiment scope — they belong to PAPER/LIVE.

## End of Experiment / Account / Costs

If Position open at end: close at final eligible price with exit reason END_OF_EXPERIMENT. Accounting: [Accounting Model](../architecture/accounting-model.md). Track starting capital, balance, realized/unrealized P&L, equity, Risk sizing, drawdown. Costs: spread, slippage, commission, financing. If excluded → explicitly disclose. Forex financing may be excluded initially with FINANCING EXCLUDED disclosure.

## Equity History / Status / Zero-Trade

Persist sufficient history for equity curve, drawdown, metrics. Statuses: PENDING, RUNNING, COMPLETED, FAILED. Failed preserves config + failure reason + diagnostics. Zero-Trade Experiment is valid — clearly communicate no executed exposure.

## Reproducibility / Dataset Integrity / Cancellation

Given identical StrategyVersion + parameters + DatasetSnapshot + Risk + simulation config + starting state + engine: identical TradeIntents, RiskDecisions, Orders, Fills, Trades, equity history. Validate data before starting. Cancel optional for first slice; if introduced, explicit, no COMPLETED status, partial results labeled incomplete.

## Execution Model Versioning / Performance

Simulation assumptions captured in immutable config (resolution, slippage, intrabar policy, financing). Correctness before optimization. Acceptable: efficient queries, Polars/NumPy, batched persistence. No distributed workers, Redis queues, parallel framework without measured need.

## Required Tests

Deterministic replay, warm-up (no Trade during), no lookahead, exact 15m decision frontier, signal bar not reused, long entry ASK, short entry BID, long liquidation BID, short liquidation ASK, PRE_FLIGHT rejection, PRE_SUBMISSION rejection after market movement, actual entry for R target, long/short stop, target execution, gap-through stop, same-bar ambiguity (adverse-first), ambiguity recording, same-bar entry/protection ordering, slippage, no spread double-count, end-of-Experiment close, zero-Trade Experiment, failed Experiment state, identical inputs → identical output.

## Golden Acceptance Flow

historical EUR/USD 1m MID/BID/ASK → deterministic 15m MID bars → EMA Sweep Engulfing → TradeIntent → Risk → post-decision BID/ASK → Order → Fill → protected Position → stop or target → closed Trade → account/equity update — for both long and short.

## Success Criteria

Reproducible Experiment whose execution behavior is conservative, explicit, and close enough to PAPER/LIVE semantics that the same StrategyVersion can progress to OANDA Practice without rewriting methodology.
