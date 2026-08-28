# Vision

The product North Star is authoritative for long-term direction:
[context/product/north-star.md](north-star.md).

## What Atlas Is

Atlas is an opinionated, strategy-first algorithmic trading workstation for independent systematic traders. It is intended as a proprietary, licensed, local-first product: the application, runtime, and durable product state operate under the customer's control, with broker and market-data integrations remaining external dependencies. Core lifecycle: Build → Experiment → PAPER → LIVE → Monitor → Improve. One immutable StrategyVersion should move from historical research to paper trading to live trading without changing its trading methodology.

## Primary Goal

Help the trader answer: Does my strategy work? Is it profitable? Is risk under control? What should I improve? Make those answers trustworthy, explainable, and easy to inspect.

## Target User

Built for a single independent systematic trader who writes Python strategies, wants deterministic Experiments, realistic paper trading, controlled live deployment, values reliability over feature count, and wants one coherent workflow. Not multi-user SaaS: the current scope is a single-trader, customer-controlled workstation, not a hosted service.

## Strategy First

The Strategy is the center of Atlas. A StrategyVersion moves through Experiment → PAPER Deployment → LIVE Deployment using the same methodology. Differences between environments belong to market data, time, account state, execution, and broker adapters — not Strategy logic.

## Initial Market / Future

Begins with Forex, EUR/USD, OANDA, and the EMA Sweep Confirmation Break v2
Strategy. The authoritative historical analysis product is native M15 MID with
sparse native M1 BID/ASK execution observations. OANDA is the first adapter, not
the definition of Atlas. Future expansion may include crypto derivatives.
Market-specific economics modeled explicitly. Atlas should remain market
agnostic but market aware.

## Out of Scope (initially)

crypto spot, U.S. exchange-traded futures, equities, options, multi-user SaaS, social/copy trading, no-code strategy creation, automated AI strategy generation, HFT, tick-level execution simulation, portfolio-level multi-strategy netting, optimization engines.

## Product Character

Professional workstation: focused, calm, deterministic, transparent, operationally clear. Not: generic SaaS dashboard, retail charting terminal clone, bot collection, infrastructure-control panel.

## Human Oversight / Reliability

Automates execution but keeps trader in control. Trader should understand: what Strategy is running, what exposure exists, why a Trade occurred, what Risk allowed/rejected, whether system is safe, what failed. Automation never requires surrendering explainability. Prefer small working trading path over large incomplete platform.

## Success

Atlas succeeds when the trader can confidently take a Python trading hypothesis through the canonical lifecycle — Build → Experiment → PAPER → LIVE → Monitor → Improve — with reproducible evidence, controlled Risk, reliable execution, and clear operational state.
