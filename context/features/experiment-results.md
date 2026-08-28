# Experiment Results

## Purpose

Helps the trader answer: Did this StrategyVersion work, how risky was it, and why? Presents evidence from a completed Experiment. Simulation: [Experiments](experiments.md). Accounting: [Accounting Model](../architecture/accounting-model.md).

## Core Workflow

Completed Experiment → headline metrics → equity/drawdown → Trade history → individual Trade inspection → assumptions/provenance. Move naturally from summary to underlying trading facts.

## Result Validity

Full results only for COMPLETED Experiments. FAILED shows failure, not partial output as trustworthy. Zero-Trade is valid: explicitly report 0 Trades.

## Experiment Header

Identify: Strategy, StrategyVersion, Instrument, tested period, status. Example: "EMA Sweep Confirmation Break v2 · EUR/USD · Jan 1 – Dec 31, 2025 · COMPLETED". No raw internal IDs.

## Primary Metrics (shown first)

Net Return, Maximum Drawdown, Sharpe Ratio, Profit Factor, Win Rate, Expectancy, Trade Count. Not a large analytics catalog initially.

## Net Return / Max Drawdown / Sharpe

Net Return = (final equity - starting equity) / starting equity, after modeled costs. Max Drawdown = largest peak-to-trough equity decline from canonical equity history (not just closed Trade P&L). Sharpe: one canonical methodology — return series, sampling interval, annualization, risk-free rate defined; made available through assumptions, not formula detail on primary display.

## Profit Factor / Win Rate / Expectancy / R Multiple

Profit Factor = gross profit / |gross loss|; handle zero-loss case. Win Rate = winning closed Trades / closed Trades; break-even defined consistently; rejected intents/unfilled Orders not Trades. Expectancy = average net outcome per completed Trade; prefer one primary measure. R = realized net outcome / initial monetary risk; consistent with canonical accounting.

## Trade Count

Completed Trade episodes — not Orders, Fills, Strategy decisions, or TradeIntents.

## Equity Curve / Drawdown / Trade List

Equity over time via TradingView Lightweight Charts. Drawdown visualization subordinate to equity curve. Trade list compact table: Entry Time, Direction, Entry, Exit, Exit Reason, P&L, R. Optional duration where useful. No Order detail in primary table.

## Trade Inspection

Trade Detail: direction, entry/exit times/prices, initial stop, target, exit reason, P&L, R multiple, Strategy rationale, execution info. Focused candlestick chart for EMA Sweep Confirmation Break v2: EMA 100, reference/sweep/confirmation candles, entry/stop/target/exit annotations. Strategy rationale captured at decision time. Do not re-implement Strategy pattern detection in UI. Progressive disclosure for execution lineage: TradeIntent → RiskDecision → Order → Fill → Trade.

## Ambiguous Outcomes / Assumptions / Provenance

Affected Trades identified: "Ambiguous intrabar resolution — Stop-first policy applied". Summary of affected count. Assumptions disclosed: analysis price (MID), execution (BID/ASK), simulation resolution (1m), intrabar ambiguity (adverse-first), slippage model, financing (Included/Excluded). Trader should not need source code for major assumptions. Provenance section (secondary): StrategyVersion, parameter snapshot, DatasetSnapshot, requested period, Risk config, starting capital, simulation config, engine version, timestamps.

## Parameters / Costs

Exact Strategy parameter snapshot used (not current defaults). Costs distinguished where supported: spread, slippage, commission, financing. No double-count spread. Excluded costs disclosed.

## Failed / Zero-Trade / Unavailable Metrics

Failed Experiment: failure reason, stage, config, actionable next step. No misleading zero cards. Zero-Trade: "No Trades — Strategy produced no executed Trades during this period." Still show config, assumptions, provenance. Metrics requiring Trades: unavailable state ("—") not fabricated zeros.

## Result Immutability / Comparison Boundary / UI

Completed results reflect immutable inputs. UI must not recalculate using current defaults, RiskProfile, or changed DatasetSnapshot. Metrics may be recomputed from Experiment's own facts when compatible. Cross-Experiment comparison: [Experiment Comparison](experiment-comparison.md). UI hierarchy: identity/status → headline metrics → equity curve → drawdown → Trades → assumptions → provenance. Trade inspection opens focused detail view.

## Current vs Future Scope

Current implementation persists and presents completed historical Experiment evidence, including simulated Orders, Fills, Positions, and Trades. PAPER/LIVE broker Trades and broker-confirmed execution are future deployment behavior, not current Experiment Results capability. See [Current status](../../CURRENT.md) and the [Accounting Model](../architecture/accounting-model.md).

## Design

Follow [Design](../design/design.md): horizontal nav, low noise, restrained metric cards, compact tables, one analytical question per view. Not institutional analytics terminal.

## Non-Goals

No Monte Carlo, parameter heatmaps, optimization reports, benchmark comparison, monthly tear sheets, PDF/email reporting, AI analysis, automated scoring, dozens of ratios, portfolio analytics.

## Required Tests

Completed Experiment retrieval, failed/zero-Trade presentation, net return, max drawdown, canonical Sharpe, profit factor, win rate, expectancy, Trade count, realized R, unavailable metric handling, equity history, Trade detail lineage, Strategy rationale, ambiguity disclosure, simulation assumptions, financing disclosure, historical parameter snapshot, provenance uses immutable Experiment data.

## Acceptance Flow

Open completed Experiment → understand headline performance → inspect equity/drawdown → review Trades → open suspicious/interesting Trade → see market context + Strategy rationale → inspect execution lineage if needed → review assumptions/provenance.

## Success Criteria

Trader answers: Did the Strategy perform? How much risk? When struggle? Which Trades drove result? Why specific Trade? How simulated? What config/data? — without needing application code or database records.
