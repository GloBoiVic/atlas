# Journal

## Purpose

Historical record of Trades. Answers: What happened, why, and what can I learn? Current implementation presents persisted historical Experiment Trades; the same Journal is the target view for future PAPER/LIVE Trades. Journal is a view over canonical Trade history — do not create a separate trading-history model. Uses Trade, Orders, Fills, StrategyVersion, RiskDecision, TradeIntent. Canonical: [Domain Model](../architecture/domain-model.md).

## Primary Views

Trade List + Trade Detail. Keep workflow focused. No broad analytics suite inside Journal.

## Trade List

Completed Trades compact table: Closed, Direction, Entry, Exit, P&L, R, Exit Reason. Since initial Instrument is always EUR/USD, repeating it in each row unnecessary until more Instruments supported.

## Open Trades

If active Trade exists: show separately from completed history. Direction, entry, current price, unrealized P&L, stop, target, Deployment. Not included in completed performance statistics.

## Filtering / Trade Detail

Initial filters small: date range, direction, win/loss, exit reason. No advanced filtering infrastructure for narrow scope. Trade Detail answers "Why did Atlas take this Trade and what happened?" Shows: Strategy, StrategyVersion, context (EXPERIMENT/PAPER/LIVE), direction, entry/exit times/prices, quantity, stop, target, gross/net P&L, costs, R multiple, duration, exit reason.

## Trade Chart

Primary analytical surface via TradingView Lightweight Charts. Surrounding price context. For EMA Sweep Confirmation Break v2: EMA 100, bearish/bullish reference, sweep, confirmation candles, entry/stop/target/exit with subtle markers. Use rationale captured at TradeIntent creation — do not re-run Strategy logic in frontend.

## Entry Rationale / Risk Detail / Execution Detail

Strategy decision-time rationale (trend, reference/sweep/confirmation candles). Must reflect what Strategy knew at decision time. Risk: Risk Per Trade, Risk Budget, Stop Distance, Approved Quantity — via progressive disclosure. Execution: TradeIntent → PRE_FLIGHT → PRE_SUBMISSION → Entry Order → Fill → Stop/Target → Exit. Secondary to summary and chart. No raw provider payloads by default.

## Entry/Exit Price / Exit Reason / P&L / Costs / R Multiple

Actual canonical Fill prices (not signal close or theoretical). For current Experiments: simulated execution. For future PAPER/LIVE: broker truth. Canonical exit reasons: TAKE_PROFIT, STOP_LOSS, END_OF_EXPERIMENT, MANUAL_CLOSE, RISK_EXIT. Not inferred from win/loss. P&L: canonical accounting — not frontend-calculated. Gross + Costs + Net where useful. Costs: spread, slippage, commission, financing. If excluded → label exclusion. R: realized outcome / initial approved risk — consistent with canonical accounting. Not inferred from exit reason alone.

## Experiment / PAPER / LIVE Trades

Same Trade Detail is the target for all environments. Current: Experiment Trades are identified with EXPERIMENT + originating Experiment and simulated execution facts. Future: PAPER/LIVE entries show PAPER/LIVE, OANDA context, and broker-confirmed Fills. No separate Journal per environment.

## Provenance / Notes / Tags / Editing

Trace Trade back to: StrategyVersion + Experiment/Deployment + parameters + Risk config. Experiment Trades also expose DatasetSnapshot + simulation assumptions via Experiment context. Notes: free-form user metadata (observations, market context, lessons). Tags: simple user-defined (clean, range, trend, news, review). No taxonomy-management subsystem. User edits notes/tags only. Cannot alter: entry/exit price, quantity, Fills, StrategyVersion, P&L, R, exit reason. Execution corrections through canonical trading/reconciliation.

## Search / Navigation / From Experiment/Dashboard

Simple: notes, tags. No external search infrastructure. Trade Detail navigates to StrategyVersion, Experiment, Deployment — no dead-ends. Experiment Results and Dashboard both open same core Trade Detail. No separate implementations.

## Chart Time Window / Ambiguity / Broker Detail

Default: enough candles before/after to explain setup/outcome. Not entire multi-year dataset. Reasonable adjustment. For Experiment Trades affected by simulation ambiguity: "Intrabar ambiguity — Adverse-first policy applied." Visible in Trade Detail. Future PAPER/LIVE technical detail (Atlas/external Order IDs, execution timestamps) belongs behind the technical section. External IDs are not primary identity.

## Trade Identity / Journal Metrics / Empty State

Human-readable: "EUR/USD Long — Aug 11, 2026 · 14:15 UTC". No raw UUIDs prominently. Small summary over current filter set: Trades, Net P&L, Win Rate, Average R — secondary. No Trades: "No Trades yet. Run an Experiment or PAPER Deployment to begin." No empty metric cards showing zeros.

## Design

Follow [Design](../design/design.md): compact Trade List → focused Trade Detail → chart → rationale → secondary detail. No sidebar. No dense institutional layout. No sidebar. One screen per mockup image; visual reference only.

## Non-Goals

No manual discretionary trade entry, screenshot attachment, AI analysis, automated coaching, complex tagging, playbook management, calendar journal, report generator, PDF/Excel export, social sharing, separate Journals by environment.

## Required Tests

Completed Trade list, open Trade presentation, EXPERIMENT/PAPER identification, canonical entry/exit Fill, P&L/R display, exit reason, Strategy rationale, EMA/reference/sweep/confirmation chart metadata, ambiguity disclosure, Risk/execution lineage, notes/tags editing, canonical facts not manually changeable, Dashboard links to Journal, Experiment Result Trade uses same detail, empty state.

## Acceptance Flow

Open Journal → review completed Trades → select Trade → see price chart → identify reference/sweep/confirmation → see actual entry/stop/target/exit → understand rationale → inspect Risk/execution detail if needed → add note/tag.

## Success Criteria

Inspect any Atlas Trade and understand: what happened, why entered, what Risk allowed, how executed, how exited, what earned/lost, what trader wants to remember — without maintaining a separate manual trading diary.
