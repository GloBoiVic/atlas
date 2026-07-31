# Atlas — Project Context Brief

## Project Name

The application is called **Atlas**.

Atlas is an opinionated, strategy-first algorithmic trading platform built in Python with a modern web UI.

The name and product direction are already decided. Do not rename the application or propose an alternative product direction unless explicitly asked.

---

# What Atlas Is

Atlas is designed to help a trader:

> **Build → Test → Deploy → Monitor → Improve**

The core purpose is to make algorithmic trading simpler and more accessible without hiding the underlying trading logic from the trader.

Atlas should support the full lifecycle:

1. Develop a Python trading strategy.
2. Backtest it against historical market data.
3. Paper trade it against live market data.
4. Deploy it to live trading.
5. Monitor bots, positions, and P&L.
6. Review completed trades through journaling and analytics.
7. Improve the strategy and repeat.

The MVP is a single-user deployment intended to run remotely on one VPS. It is not local-only and is not a multi-user SaaS platform. Atlas manages multiple configured bots inside one worker process while PostgreSQL persists durable trading and recovery state.

Atlas is **not** intended to be an academic quantitative research platform. Keep the product focused and simple.

---

# Product Philosophy

## Simplicity First

Traders value simplicity.

Do not add complexity merely because it is technically interesting or because other algorithmic trading platforms have the feature.

Prefer:

- Simple workflows
- Clean interfaces
- Obvious actions
- Minimal configuration
- Useful defaults
- Progressive disclosure

Complexity should exist underneath the system when necessary, but the user experience should remain simple.

---

## Opinionated

Atlas is intentionally opinionated.

We are not attempting to support every possible trading workflow.

The platform should provide a consistent and intuitive workflow for developing and operating algorithmic strategies.

---

## Strategy First

Strategies are the center of Atlas.

The platform is not organized primarily around brokers or markets.

Markets and brokers are infrastructure that strategies use.

The same strategy should ideally work across:

- Backtesting
- Paper trading
- Live trading

without modifying the strategy's core logic.

---

## Market Agnostic

Atlas should not be tied to one market.

The intended markets are:

- Forex
- Cryptocurrency
- Futures

The architecture should allow additional markets later.

Do not design the strategy engine around Forex-specific assumptions.

The MVP uses one net position per account and instrument. Hedged or multiple independent positions are deferred.

---

## Broker Agnostic

The initial broker/data integrations being considered are:

- Oanda
- Binance

A futures provider has not yet been selected.

The architecture remains broker-agnostic, but Binance Spot is the first concrete integration because it provides practical public market data and an accessible testnet path. Oanda and futures are deferred until the initial paper-trading workflow is stable.

Do not hard-code Atlas around Oanda or Binance.

Broker-specific functionality must live behind broker interfaces/adapters.

---

# Trading Strategy Philosophy

The initial strategy philosophy is based on:

- Trend following
- Breakouts
- Market structure
- Momentum following a confirmed breakout

The trader believes that directional market movement often requires a break from the current trading range, while recognizing that breakouts are never guaranteed.

The initial implementation should support strategies that can reason about market structure and indicators without assuming that every strategy is indicator-driven.

Indicators such as EMA, ATR, etc. should be available as tools rather than becoming the architecture's central concept.

---

# Timeframes

Atlas must support multiple timeframes.

The trader is particularly interested in eventually trading on the **1-minute timeframe**, but the platform must not be designed exclusively around 1-minute trading.

Strategies should be able to operate on different granularities.

---

# Signal Timing

Trading signals are based on **completed candles**.

The expected lifecycle is:

```text
Candle closes
    ↓
Strategy evaluates completed candle
    ↓
Pattern/signal confirmed
    ↓
Signal generated
    ↓
Risk Engine evaluates signal
    ↓
Approved order executes on the next candle
```

Do not allow strategies to accidentally use incomplete candle data when the strategy is configured for completed-candle confirmation.

This behavior must be deterministic in both backtesting and live trading.

---

# Risk Management

Risk management is centralized.

Atlas has a dedicated **Risk Engine**.

Strategies generate signals.

They do not independently decide whether a trade is permitted.

The Risk Engine should centrally manage controls such as:

- Position sizing
- Maximum drawdown
- Maximum open positions
- Per-trade risk limits
- Stop-loss/take-profit enforcement
- Daily loss limits
- Trading session restrictions

Every order must pass through the Risk Engine before execution.

Risk defaults should be defined in Python/configuration, while the UI should be able to override supported settings.

The UI should also provide a way to restore settings to their defaults.

Do not duplicate risk-management logic across individual strategies.

The initial risk slice is position sizing, stop-loss/take-profit calculation, and maximum open net positions. Daily loss limits, maximum drawdown halts, and trading sessions follow after the core risk contract is proven.

---

# Journaling

Journaling is important to Atlas.

The system should record completed trades and useful context around them.

Potential information includes:

- Entry price
- Exit price
- Entry time
- Exit time
- P&L
- Strategy
- Strategy version
- Trade reason
- Market conditions
- Notes
- Screenshots
- Position information

The journal is intended to help the trader understand their trading behavior and strategy performance.

Do not turn journaling into a complicated social/research platform.

---

# Dashboard Philosophy

The dashboard is the primary operational view.

The trader specifically wants to immediately see:

- P&L
- Open trades
- Current positions
- Active bots
- Account information
- Strategy/bot status

The dashboard should answer:

> **"How is my automated trading doing right now?"**

Do not turn the dashboard into a research laboratory.

Advanced analytics can exist elsewhere in the application.

---

# Core UI

The intended application is a clean, modern trading application. Navigation, page inventory, and visual behavior are owned by `context/design.md` and the UI feature specification. The UI should prioritize clarity over information density.

---

# Trading Controls

The UI should allow traders to monitor and control their bots and trades.

Important interactions include:

- Start bot
- Stop bot
- Pause bot where appropriate
- View bot status
- View open trades
- View current positions
- View P&L
- Close a position manually

Closing a trade should require a confirmation dialog.

Potentially destructive actions should always require deliberate user confirmation.

---

# Architecture

Atlas uses the event-driven component architecture defined in `context/architecture.md`, with REST/WebSocket access through FastAPI and a supervised trading worker.

---

# EventBus

Atlas uses an internal EventBus to decouple major subsystems.

The initial implementation should be lightweight and in-process.

Do **not** introduce Kafka, RabbitMQ, Redis Streams, or other distributed messaging infrastructure unless a future requirement actually justifies it.

Canonical event types, metadata, delivery ordering, and failure behavior are defined in `context/architecture.md`.

---

# Market Data

Market data must be provider-agnostic.

Atlas should use a common market-data interface.

Initial providers may include:

- CSV
- Oanda
- Binance

The first implementation is CSV plus Binance Spot public market data. Oanda is a future provider.

The strategy engine should receive normalized market data regardless of its source.

Strategies must not contain provider-specific API logic.

---

# Broker Execution

Execution is broker-agnostic. The Execution Engine owns orders and positions while adapters own broker APIs. The first authenticated adapter is Binance Spot testnet; production live trading is deferred. Detailed contracts live in `context/architecture.md` and Feature 07/09.

---

# Persistence

Atlas uses PostgreSQL. Engines access persistence through repositories, and the UI/API uses domain services rather than modifying trading state directly. The canonical schema is `context/database.md`.

The remote MVP runs as one Docker Compose deployment containing the Next.js frontend, FastAPI API, trading worker, and PostgreSQL. Cloudflare provides HTTPS and Access with Google authentication. Atlas does not implement passwords, and broker credentials are supplied through server environment secrets rather than stored in PostgreSQL.

---

# Backtesting

Backtesting is a core MVP capability.

The intended backtest pipeline is:

```text
Historical Data
      ↓
Simulation Clock
      ↓
Strategy
      ↓
Risk Engine
      ↓
Simulated Execution
      ↓
Performance Metrics
```

The Backtester should be separate from live infrastructure in terms of execution environment, but it must reuse the same core Strategy and Risk implementations whenever possible.

Do **not** create a completely separate version of strategy logic for backtesting.

The goal is to minimize differences between:

- Backtest
- Paper Trading
- Live Trading

For the first vertical slice, live market data feeds paper execution. Authenticated execution begins with Binance Spot testnet after paper trading is stable.

---

# Simulation Clock

The Simulation Clock is a true virtual clock.

During a backtest:

```text
09:30 → process events
09:31 → process events
09:32 → process events
09:33 → process events
```

The backtest may run much faster than real time, but Atlas components should perceive the simulated historical timestamp as the current time.

Use a clock abstraction such as:

```text
Clock
├── LiveClock
└── SimulationClock
```

Trading logic must not directly depend on:

```python
datetime.now()
```

for behavior that needs to be deterministic in backtests.

---

# Backtest Persistence

Backtest results should be stored in the same PostgreSQL database as Atlas's other data, but logically separated from live/paper trading records.

Backtests should have distinct domain entities such as:

- BacktestRun
- BacktestTrade
- Run-level backtest metrics

A backtest should record enough information to reproduce the run, including:

- Strategy/version
- Strategy parameters
- Instrument
- Timeframe
- Data source/dataset
- Date range
- Risk configuration
- Execution configuration
- Results
- Metrics
- Status
- Creation timestamp

Backtest trades must never be treated as real/paper trades.

The UI should access backtests through dedicated backtest API endpoints.

---

# Deterministic Backtesting

A critical architectural requirement:

> Given the same dataset, strategy version, parameters, risk configuration, execution configuration, and environment, the same backtest must produce the same results.

Backtests must be reproducible.

The canonical candle timing rule is: a signal confirmed at candle close becomes eligible for a fill at the next candle open. This applies to deterministic backtests and the paper execution model.

---

# Optimization

Do **not** build advanced strategy optimization into the MVP.

The initial philosophy is:

> **The trader's knowledge is the optimizer.**

The MVP should focus on:

- Writing strategies
- Running backtests
- Reviewing results
- Making informed strategy changes

Advanced capabilities such as:

- Parameter sweeps
- Walk-forward analysis
- Monte Carlo analysis
- Automated optimization

can be considered in a future version.

---

# AI

AI is intentionally **out of scope for the MVP**.

Do not add:

- AI strategy generation
- AI trade recommendations
- AI trade analysis
- AI autonomous strategy optimization
- AI journaling

After the core platform is stable and useful, AI capabilities can be revisited.

---

# Product Scope

Atlas is intentionally **not**:

- A donor/CRM system
- A generic portfolio management platform
- A social trading platform
- A copy-trading platform
- A no-code strategy builder
- An AI trading bot
- An academic quantitative research platform
- A replacement for every discretionary trading terminal

Keep the product focused.

---

# Current MVP Priority

The MVP should establish this workflow:

```text
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

The product should not attempt to build every advanced capability before this workflow works reliably.

---

Agent workflow and documentation ownership are defined in `AGENTS.md`. Strategy packages are deployed from a private Git repository; bots pin and record a repository commit.

---

# Final Product Principle

Atlas should feel like a tool built by traders for traders:

**Simple enough to understand immediately.**

**Powerful enough to automate serious strategies.**

**Transparent enough that the trader always understands what the system is doing.**

**Reliable enough to trust with automation.**

When deciding between a simpler solution and a more sophisticated solution, prefer the simpler solution unless the complexity provides clear, measurable value.
