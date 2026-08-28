# Design

## Purpose

Atlas should feel like a focused trading workstation — not a dense institutional terminal, not a generic SaaS dashboard. Optimize for clarity, speed, confidence, low visual noise, obvious trading state. Initial target scope: OANDA Practice, EUR/USD, EMA Sweep Confirmation Break v2. The current UI implementation is historical Experiments; PAPER/LIVE screens are future target references and must not be read as implemented behavior.

## Core Design Principle

Every screen should answer one primary question: Dashboard (What is Atlas doing?), Strategies (What StrategyVersions do I have?), Experiments (How did this perform?), Deployments (What is running?), Journal (What happened in this Trade?), Data (Is data available and valid?). Avoid combining multiple unrelated workflows onto one screen.

## Navigation

Horizontal top navigation (NO sidebar). Primary: Atlas, Dashboard, Strategies, Experiments, Deployments, Journal, Data, Settings. Active section shown through restrained emphasis (text weight, subtle background, underline/border). No large tabs or excessive color.

## Top Navigation Layout

Left: Atlas logo/wordmark + primary navigation. Right: globally useful context/actions (PAPER/LIVE environment, connection status, user/settings). No search without enough content. Do not fill with controls merely because space exists.

## Page Header / Desktop First

Each page: title + short supporting context + primary action. No redundant breadcrumbs for top-level pages. Desktop-first workstation optimized for laptops, desktops, wide screens. Remains usable at smaller widths but mobile not initial priority.

## Visual Character

Clean, modern, restrained, technical, calm, precise. Approved V2 appearance is dark-first: deep blue-black canvas, dark navy surfaces, cool-neutral text and borders, and sparse semantic color. This is not a dense institutional terminal. Avoid excessive green/red, dense walls, oversized KPI dashboards, gradients, ornamental shadows, decorative animations, and generic fintech visuals. See [`ui-tokens.md`](ui-tokens.md) and [`visual-guide.md`](visual-guide.md) for the recurring visual roles and evidence-backed guidance.

## Initial Scope / Information Density

Do not design as if Atlas supports 20 accounts, 50 Strategies, multiple brokers. Screens naturally reflect: 1 OANDA account, 1 Instrument, small number of StrategyVersions and Deployments. Compact but not crowded: a few meaningful summary values, one main chart/table, secondary detail beneath/beside. Avoid stacking 6-7 panels.

## Cards / Tables

Use cards selectively (account summary, current Position, active Deployment, Experiment metrics, focused config groups). No nested card grids or dashboard tile walls. Tables for Experiments, Trades, StrategyVersions, data coverage. Keep simple — no advanced column managers, huge filters, complex pagination until data volume warrants.

## Dashboard

Primary: What is Atlas doing? Summary: Account Equity, Today's P&L, Current Position, Active Deployment. Main Content: Equity Curve, Recent Activity, Recent Trades. Show meaningful flat-state instead of empty Position card. Small status line: OANDA Practice, EUR/USD, Live Data, Runtime Healthy. Critical failures surfaced prominently.

## Strategies / Strategy Detail

Simple methodology workspace. Show: name, description, StrategyVersions, latest version, last used, status where meaningful. Detail focuses on Overview, Versions, Experiments, Deployments. Not a code editor.

## Experiments / Results

Centered around: Run → inspect result → compare with prior. List shows name, StrategyVersion, date range, net return, max drawdown, Sharpe, status, created date. Results show Net Return, Max Drawdown, Sharpe, Profit Factor, Win Rate, Trade Count, Expectancy, Equity Curve, Drawdown, Trades. Assumptions/provenance secondary.

## Deployments

Very simple with one Instrument and one account. Show StrategyVersion, status, Instrument, Account, Timeframe, Current Position, Risk, [Pause], [Stop]. Not an institutional multi-strategy table. Deployment activity shows meaningful events only.

## Journal / Trade Detail

Two screens: Trade List (date, direction, entry, exit, P&L, R multiple, result) and Trade Detail (summary, candlestick chart, entry/stop/target/exit, rationale, execution lineage, notes/tags). Journal mockups may depict the future trading scope: EUR/USD, EMA Sweep Confirmation Break v2, USD, OANDA Practice. They do not imply that PAPER/LIVE trading is currently implemented.

## Data / Settings

Data answers: Can Atlas run the Experiment I want? Shows EUR/USD, OANDA, 1m, coverage, integrity, last updated. Actions: Load Data, Update Data, Inspect Coverage. Not a multi-provider catalog. Settings: actual configuration only (OANDA connection, Risk defaults, app preferences). No runtime architecture as settings.

## Charts

TradingView Lightweight Charts for candles, trade visualization, equity curves, drawdown. Not dozens of indicators, drawing tools, or TradingView-terminal functionality. For EMA Sweep Confirmation Break v2: EMA 100, reference candle, sweep candle, confirmation candle, entry/stop/target/exit annotations — subtle, not overwhelming.

## Color / PAPER vs LIVE / Connection State

Color for meaning: green (positive/healthy/long), red (negative/critical/short), blue (selection/primary action/info). Neutral text remains neutral. PAPER/LIVE unmistakable. Initial: OANDA Practice/PAPER. LIVE only when roadmap phase exists. Connection state compact: PAPER ● CONNECTED. Only elevate when something is wrong.

## Safety States / Sonner / Internal IDs

Critical safety conditions interrupt normal hierarchy. Show what happened, whether new exposure blocked, whether exposure protected, available action. Persistent failures never rely solely on toasts. Sonner for transient feedback only. No raw UUIDs in normal UI.

## Human-Readable Language / Actions

Canonical terminology: Strategy, StrategyVersion, Experiment, Deployment, Trade, Position. Not Bot, Algo Instance, Backtest Run, Worker, Engine. Primary actions few and obvious: Run Experiment, Create Deployment, Start/Pause/Resume/Stop, Load Data, Inspect Trade. No multiple equivalent actions on same screen.

## Detail Navigation / Empty States

Full detail pages for major workspaces (Experiment Results, Strategy Detail, Trade Detail). Drawers only where quick inspection improves workflow without leaving current list. Empty states reflect Golden Path — guide the user toward the next meaningful action.

## Responsive / Mockups / Screenshot

Narrower screens: keep horizontal nav as long as practical, collapse secondary controls, scroll tables, stack secondary detail, preserve safety info. Mockups are visual reference only; written context governs behavior and scope. The approved V2 screenshot set is documented in [`visual-guide.md`](visual-guide.md): `context/design/atlas-overview-page.png`, `context/design/atlas-strategies-page.png`, `context/design/atlas-strategies-details-page.png`, `context/design/atlas-experiments-page.png`, `context/design/atlas-experiments-detail-page.png`, `context/design/atlas-experiment-run-page.png`, `context/design/atlas-compare-experiments-page.png`, `context/design/atlas-deployments-page.png`, `context/design/atlas-journal-page.png`, and `context/design/atlas-journal-detail-page.png`. No screenshot-only difference authorizes navigation or behavior changes.

## USD Base Currency / Design Review

Initial account presentation: USD ($52,840.50). Review each screen: horizontal nav? matches narrow scope? unnecessary info? primary question obvious? healthy infrastructure understated? safety problems obvious? PAPER/LIVE clear? internal IDs hidden? Could agent misread mock data as requirement? Can anything be removed? When in doubt: remove something.

## Success Criteria

Each screen feels: simple, focused, modern, trader-oriented, easy to scan — and the trader can understand the primary state/workflow within a few seconds without navigating a dense trading terminal.
