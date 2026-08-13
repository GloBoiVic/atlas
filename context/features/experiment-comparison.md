# Experiment Comparison

## Purpose

Compare completed Experiments and understand how configuration changes affected results. Goal: compare hypotheses, not automatically optimize Strategies. Individual results: [Experiment Results](experiment-results.md).

## Core Workflow

Run Experiment A → change parameter/config → run Experiment B → compare → form next hypothesis. Atlas assists analysis; does not select "best" Strategy automatically.

## Comparison Scope

Initial: 2–4 Experiments for deliberate manual research. Not designed for ranking hundreds of permutations.

## Compatibility

Clearly identify important differences between compared Experiments: StrategyVersion, Instrument, period, DatasetSnapshot, parameters, Risk config, starting capital, simulation assumptions. Experiments need not be identical, but differences must be visible. Strongest comparison: same StrategyVersion + Instrument + DatasetSnapshot/period + Risk + simulation assumptions + one intentional parameter change. Atlas should make this pattern easy without requiring it as absolute rule.

## Comparison Header / Config Differences

Identify each Experiment with meaningful labels (e.g., "Experiment A: EMA Sweep Engulfing v1, ATR Buffer 0.5"). No raw UUIDs. Show config differences before performance. Prioritize: StrategyVersion, parameters, date range, DatasetSnapshot, Risk config, simulation assumptions. Unchanged config visually de-emphasized. Trader understands "What changed?" before "What performed better?"

## Metric Comparison

Same canonical metric definitions as Experiment Results: Net Return, Max Drawdown, Sharpe, Profit Factor, Win Rate, Expectancy, Trade Count. No comparison-specific formulas. Compact comparison table preferred.

## Configuration Comparison / Equity Comparison

Compact view for changed parameters. Highlight differences without excessive visual treatment. Equity curve overlay may be supported where share meaningfully comparable period (via TradingView Lightweight Charts). Do not force overlay when date ranges/assumptions make comparison misleading. May normalize to percentage return where appropriate — do not silently normalize.

## Warnings / Failed / Zero-Trade

Warn when major assumptions differ: different DatasetSnapshots, StrategyVersions, periods, Risk, simulation assumptions. Warning informs interpretation; does not block. Only COMPLETED Experiments participate in performance comparison. Zero-Trade Experiment may be compared; unavailable metrics remain unavailable (not zero).

## No Winner / No Composite Score

Atlas must not label BEST/WINNER/OPTIMAL/RECOMMENDED based solely on metrics. Higher historical return ≠ superior future performance. Trader interprets evidence. No proprietary composite score combining Sharpe/return/drawdown/win rate — different objectives require different trade-offs.

## Iteration Flow

From comparison: inspect Experiment → inspect Trades → return → run another Experiment. Future convenience may prefill from existing Experiment (creates new, never mutates original). StrategyVersion changes clearly shown as methodology change, not parameter adjustment. DatasetSnapshot differences surfaced prominently. Simulation assumption differences shown.

## Design

Follow [Design](../design/design.md): one comparison workspace, compact tables, restrained highlighting, optional useful chart. Avoid giant metric grids, leaderboard aesthetics, optimization-terminal density.

## Non-Goals

No grid/random/Bayesian/genetic search, automated parameter sweeps, walk-forward optimization, Strategy leaderboards, automatic recommendations, composite scores, mass ranking.

## Required Tests

Compare two completed Experiments, compare up to limit, parameter difference detection, StrategyVersion/DatasetSnapshot/date-range/Risk/simulation-assumption warnings, canonical metric reuse, zero-Trade handling, FAILED exclusion, unavailable metric handling, normalized equity presentation where implemented.

## Acceptance Flow

Run baseline → change one parameter → run second → select both → see config differences → compare performance/risk → inspect individual Experiment/Trade → form next hypothesis.

## Success Criteria

Trader quickly answers: What changed? How did performance/risk change? Are these genuinely comparable? What next? — without Atlas pretending to know which config will perform best in the future.
