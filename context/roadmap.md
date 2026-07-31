# Atlas — Roadmap

## Overview

Atlas is a single-user trading operations platform deployed remotely as one Docker Compose application. The MVP workflow is:

```text
Deploy strategy package → Backtest → Paper trade on Binance data → Monitor → Validate on Binance testnet → Journal and analyze
```

The architecture remains broker-agnostic, but implementation is deliberately narrow: Binance Spot is the first concrete integration. Oanda, futures, production live trading, multi-account support, and automated infrastructure deployment are deferred.

Development happens through vertical slices. Each phase includes tests and produces a usable, verifiable capability.

---

## Phase 1: Project Foundation

**Goal:** Create a remotely deployable single-user skeleton.

### Deliverables

- [ ] Project directory structure created
- [ ] Docker Compose for frontend, API, worker, and PostgreSQL
- [ ] Persistent PostgreSQL volume and Alembic migration setup
- [ ] FastAPI health and worker liveness endpoints
- [ ] Next.js frontend connected to the API
- [ ] `.env.example` with non-secret configuration names
- [ ] Server environment secret documentation
- [ ] Cloudflare DNS/HTTPS and Access with Google authentication documented
- [ ] Ruff, mypy, ESLint, and frontend type checking configured

### Done when

- `docker compose up` starts all required services
- Backend responds to `GET /health`
- Worker reports liveness
- Frontend loads through the API boundary
- Required checks pass

---

## Phase 2: Core Infrastructure

**Goal:** Define the deterministic runtime contracts used by every later phase.

### Deliverables

- [ ] Typed, bot-scoped in-process EventBus
- [ ] Event IDs, correlation IDs, timestamps, account IDs, bot IDs, and execution modes
- [ ] Deterministic sequential delivery and failure handling
- [ ] LiveClock and SimulationClock
- [ ] Pydantic Settings and YAML configuration
- [ ] Structured logging
- [ ] Retry logic, circuit breaker, health monitor, and BotSupervisor contracts

### Done when

- Event ordering, idempotency, and handler failures are tested
- Simulation time advances deterministically
- Configuration rejects unsafe mode combinations
- Supervisor lifecycle operations are idempotent

---

## Phase 3: Data Layer

**Goal:** Normalize historical and public Binance Spot data behind provider-agnostic interfaces.

### Deliverables

- [ ] Candle, Tick, Instrument, and dataset contracts
- [ ] CSV historical provider
- [ ] Binance Spot historical provider through ccxt
- [ ] Binance completed-candle/trade streaming provider
- [ ] Candle persistence and bulk loading
- [ ] Timestamp, ordering, duplicate, precision, and Decimal validation

### Done when

- CSV and Binance data produce the same normalized Candle model
- Historical datasets are identifiable and reproducible
- Only completed candles produce `CandleClosed`
- Reconnects do not duplicate candles or subscriptions

---

## Phase 4: Strategy Engine

**Goal:** Run version-pinned Python strategies against completed candles.

### Deliverables

- [ ] Strategy base class and completed-candle contract
- [ ] Optional tick observation without tick-generated trading signals
- [ ] Signal model with strategy version metadata
- [ ] SMA crossover and Bollinger Bands examples
- [ ] Strategy registry backed by a deployed private Git package
- [ ] Strategy commit and parameter validation
- [ ] Per-bot strategy state isolation

### Done when

- A strategy receives completed candles and emits scoped signals
- The same strategy package can run in simulation and paper mode
- Strategy state resets between runs
- Signals identify the exact strategy commit and candle timestamp

---

## Phase 5: Risk Engine

**Goal:** Centrally approve or reject every order using explicit account and market context.

### Deliverables

- [ ] Position sizing from equity, risk-per-trade, and stop distance
- [ ] Maximum open net positions
- [ ] Stop-loss/take-profit calculation
- [ ] Decimal quantity and instrument constraint validation
- [ ] Per-bot risk state
- [ ] YAML defaults and supported configuration overrides

### Done when

- Risk decisions are deterministic and independently tested
- Invalid risk inputs reject signals safely
- Risk rules are reused by backtesting and paper trading

Daily loss limits, maximum drawdown, and trading sessions are deferred until the initial risk contract is stable.

---

## Phase 6: Execution Layer

**Goal:** Provide deterministic paper execution through broker-agnostic interfaces.

### Deliverables

- [ ] Broker interface for orders, account, positions, and reconciliation
- [ ] Execution engine scoped to one bot
- [ ] Paper broker with next-candle-open backtest fills
- [ ] One net position per account and instrument
- [ ] Fees, slippage, quantity precision, and protective exits
- [ ] Order, fill, position, and trade state machines
- [ ] Idempotent client order IDs and unknown-order handling

### Done when

- Paper orders create deterministic fills and position updates
- Protective exits follow documented candle assumptions
- Duplicate submissions cannot create duplicate orders
- Broker reconciliation can recover unknown state

---

## Phase 7: Backtesting

**Goal:** Produce reproducible performance results using the same Strategy, Risk, and Paper Execution implementations used by paper bots.

### Deliverables

- [ ] Historical replay with SimulationClock
- [ ] Signal-at-close and fill-at-next-candle-open timing
- [ ] BacktestRun and BacktestTrade persistence with run-level metrics
- [ ] Documented metrics with fees, slippage, and fill assumptions
- [ ] Backtest API endpoints
- [ ] Backtest result UI

### Done when

- Historical data → Strategy → Risk → Paper Execution → Metrics works end to end
- Same inputs produce identical results
- Backtest records remain separate from paper/testnet trading records
- Metrics have fixture-based expected values

---

## Phase 8: Bot Runtime and Paper Trading

**Goal:** Operate multiple isolated paper bots against Binance Spot live public data.

### Deliverables

- [ ] Bot model and persisted lifecycle state
- [ ] BotSupervisor with independent in-process pipelines
- [ ] Start, stop, pause, and resume
- [ ] Binance completed-candle feed integration
- [ ] Paper account, positions, P&L, and heartbeat tracking
- [ ] Startup restoration and broker/account reconciliation
- [ ] Real-time bot status events

### Done when

- Multiple bots cannot cross event or strategy state
- Paper bots react only to completed candles
- Restart restores active bots only after successful reconciliation
- A failed reconciliation prevents new orders

---

## Phase 9: Journal and Analytics

**Goal:** Record completed trades and explain strategy performance.

### Deliverables

- [ ] Journal entries linked to bot, account, strategy version, fills, and trade
- [ ] Signal and market context capture
- [ ] Analytics service and API
- [ ] Total return, win rate, Sharpe ratio, max drawdown, and profit factor formulas documented
- [ ] Journal and analytics UI

### Done when

- Completed trades are journalized automatically
- Metrics are reproducible from persisted trades
- Open and closed trade treatment is documented

---

## Phase 10: Operational UI

**Goal:** Provide the primary operational view for the single trader.

### Deliverables

- [ ] Dashboard with P&L, positions, active bots, account, and health
- [ ] Strategies and strategy-version pages
- [ ] Backtests page
- [ ] Paper Trading page
- [ ] Trades, Journal, and Analytics pages
- [ ] Settings for supported risk and deployment configuration
- [ ] WebSocket real-time updates
- [ ] Confirmation dialogs for destructive actions

### Done when

- The dashboard answers “How is automated trading doing right now?”
- Bot and position controls are deliberate and observable
- Real-time data displays correct persisted state

---

## Phase 11: Binance Testnet Trading

**Goal:** Validate authenticated broker execution and reconciliation without production orders.

### Deliverables

- [ ] Binance Spot testnet adapter
- [ ] Submit, fill, cancel, and reconcile orders
- [ ] Environment-secret authentication
- [ ] Explicit paper/testnet account separation
- [ ] Testnet-only endpoint and credential safety checks

### Done when

- Testnet orders are handled through the same Execution Engine contract
- Unknown responses reconcile before retry
- Testnet positions match broker state after restart

---

## Phase 12: Hardening and Operations

**Goal:** Make the remote single-user deployment reliable and safe to operate.

### Deliverables

- [ ] Global trading pause/kill switch
- [ ] Reconciliation and restart recovery tests
- [ ] Broker failure and network timeout tests
- [ ] Structured operational logs and health dashboard
- [ ] Backup and restore procedure for PostgreSQL
- [ ] Deployment, strategy versioning, and recovery documentation

### Done when

- Expected restart and broker failure scenarios are tested
- No credential reaches the browser or database
- The system fails closed when execution safety is uncertain

---

## Deferred Scope

- [ ] Oanda integration
- [ ] Futures markets
- [ ] Production live trading
- [ ] Multiple accounts
- [ ] Multiple net/hedged positions per instrument
- [ ] Automated strategy deployment
- [ ] Strategy upload through the UI
- [ ] Parameter sweeps, walk-forward analysis, and Monte Carlo
- [ ] AI features
- [ ] Multi-user support

## MVP Completion Criteria

The MVP is complete when one trader can:

1. Deploy a versioned Python strategy package.
2. Load or import historical data.
3. Run a deterministic backtest.
4. Review persisted results and metrics.
5. Run multiple paper bots against Binance Spot live public data.
6. Monitor bot status, positions, and P&L.
7. Recover active bots safely after an Atlas restart.
8. Validate broker execution on Binance Spot testnet.
9. Review completed trades in the journal and analytics views.

The same strategy code and risk rules are reused across backtesting and paper trading, with testnet execution added through the same broker-agnostic execution contract.
