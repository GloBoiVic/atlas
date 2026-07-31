# Atlas — Vision

## Why Atlas Exists

Algorithmic trading is powerful but unnecessarily complex. Most traders who want to automate their strategies face a fragmented ecosystem: one tool for backtesting, another for paper trading, another for live execution, and spreadsheets for journaling. The learning curve is steep, the tooling is disjointed, and the gap between "I have a strategy idea" and "my strategy is trading live" is unnecessarily wide.

Atlas exists to close that gap.

> **Atlas is an opinionated, strategy-first algorithmic trading platform that makes it simple to build, test, deploy, monitor, and improve trading strategies — without hiding the underlying logic from the trader.**

---

## What Atlas Is

Atlas is designed to help a trader move through a complete lifecycle:

**Build → Test → Deploy → Monitor → Improve**

1. **Build** — Develop a Python trading strategy.
2. **Test** — Backtest it against historical market data.
3. **Deploy** — Paper trade it against live market data, then go live.
4. **Monitor** — Watch bots, positions, and P&L in real time.
5. **Improve** — Review completed trades through journaling and analytics, then refine the strategy.

Atlas is a tool built by traders for traders. It is not a research platform, a social network, or a black box. It is a focused, transparent system that gives traders control over their automation.

---

## Product Philosophy

### Simplicity First

Traders value simplicity. Atlas should not add complexity merely because it is technically interesting or because other platforms have the feature.

- Simple workflows
- Clean interfaces
- Obvious actions
- Minimal configuration
- Useful defaults
- Progressive disclosure

Complexity should exist underneath the system when necessary, but the user experience should remain simple. When choosing between a simpler solution and a more sophisticated one, prefer the simpler solution unless the complexity provides clear, measurable value.

### Opinionated

Atlas is intentionally opinionated. It does not attempt to support every possible trading workflow. It provides a consistent and intuitive workflow for developing and operating algorithmic strategies. This opinionation is a feature — it reduces decision fatigue and keeps the trader focused on what matters: their strategy.

### Strategy First

Strategies are the center of Atlas. The platform is not organized primarily around brokers or markets. Markets and brokers are infrastructure that strategies use. The same strategy should work across backtesting, paper trading, and live trading without modifying the strategy's core logic.

### Transparent

Atlas should never hide what it is doing from the trader. The trader should always understand:
- What the system is doing
- Why it is doing it
- What data it is using
- What decisions it is making

Automation is valuable, but blind automation is dangerous. Atlas automates execution while keeping the trader informed and in control.

---

## Who Atlas Is For

Atlas is for traders who:

- Want to automate their trading strategies
- Prefer to write strategies in Python
- Value simplicity and clarity over feature density
- Want to understand what their system is doing, not just trust a black box
- Trade across multiple markets (Forex, Crypto, Futures)
- Want a single platform that covers the full strategy lifecycle

Atlas is not for:

- Non-technical traders who want a no-code solution
- Academic researchers who need deep quantitative analysis tools
- Social traders who want copy-trading or community features
- Traders who want AI to generate strategies for them

---

## Core Values

### Simple Enough to Understand Immediately

A new user should be able to look at Atlas and immediately understand what it does and how to use it. The dashboard should answer: "How is my automated trading doing right now?"

### Powerful Enough to Automate Serious Strategies

Simple does not mean limited. Atlas should support real strategies with proper risk management, multiple timeframes, and multiple markets. The simplicity is in the interface, not in the capability.

### Transparent Enough That the Trader Always Understands

The trader should never have to guess what the system is doing. Every signal, every order, every risk decision should be traceable and explainable.

### Reliable Enough to Trust with Automation

When a trader deploys a strategy to Atlas, they are trusting it with real money. Atlas must be dependable, deterministic, and predictable. Backtests must be reproducible. Live execution must be consistent with backtest behavior.

---

## What Atlas Is Not

Atlas is intentionally **not**:

- **A social trading platform** — No copy-trading, no leaderboards, no social features.
- **A no-code strategy builder** — Strategies are written in Python. Atlas does not try to hide the code behind a visual builder.
- **An AI trading bot** — AI is out of scope for the MVP. The trader's knowledge is the optimizer.
- **A generic portfolio management platform** — Atlas is focused on algorithmic strategy execution, not portfolio tracking.
- **An academic research platform** — Atlas is a tool for traders, not researchers. It does not need to support every possible quantitative methodology.
- **A replacement for every discretionary trading terminal** — Atlas automates strategies. It does not attempt to be a full trading workstation.

---

## The Atlas Workflow

The MVP workflow is:

```
Create Strategy
      ↓
Import/Access Historical Data
      ↓
Backtest
      ↓
Review Results
      ↓
Paper Trade
      ↓
Monitor Bot
      ↓
Live Trade
      ↓
Review Trades / Journal
```

This workflow should work reliably before Atlas attempts to build advanced capabilities.

---

## Success Criteria

Atlas is successful when:

1. A trader can write a strategy in Python and have it running in paper trading within minutes.
2. Backtests are deterministic — same inputs produce same results.
3. The dashboard clearly shows what the system is doing at any moment.
4. The trader trusts the system enough to deploy strategies with real money.
5. The journaling and analytics help the trader improve their strategies over time.

---

## The Name

**Atlas.** Named after the Titan who held up the sky. Atlas holds up the trader's strategies, so they can focus on what matters — making better trading decisions.
