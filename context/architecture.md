# Atlas — Architecture

## Purpose

Atlas is a single-user trading operations platform deployed remotely as one Docker Compose application. It manages version-pinned Python strategies through backtesting, paper trading, monitoring, and Binance Spot testnet validation.

The MVP is not multi-tenant, does not deploy arbitrary infrastructure, and does not use distributed messaging. PostgreSQL is the durable source of truth; the in-process EventBus coordinates work within one worker process.

Detailed persistence is defined in `context/database.md`. Feature-specific behavior and acceptance criteria are defined in `context/features/`. Library usage is defined in `context/library-docs.md`.

## Invariants

1. Strategies contain strategy logic only. Risk and execution decisions are centralized.
2. Broker and provider-specific API logic lives behind adapters.
3. The same Strategy, Risk, and Paper Execution contracts are reused in backtesting and paper trading.
4. Every bot has isolated strategy state, risk state, subscriptions, and execution context.
5. Every trading-critical operation is scoped by account, bot, strategy version, and execution mode.
6. The system fails closed when execution safety or broker state is uncertain.
7. All money, prices, quantities, fees, and P&L use `Decimal` in the backend domain.
8. Backtest behavior is deterministic through the shared Clock abstraction.

## Runtime Topology

```text
Cloudflare HTTPS + Access / Google
              ↓
        Next.js frontend
              ↓ REST + WebSocket
          FastAPI API
              ↓ commands/services
       PostgreSQL repositories

       Trading worker process
              ↓
          BotSupervisor
              ↓ one isolated pipeline per bot
    Market Data → Strategy → Risk → Execution → Broker Adapter
                                      ↓
                              orders / fills / positions
```

Docker Compose runs four services in the MVP:

- `frontend`: Next.js operational UI.
- `api`: FastAPI REST and WebSocket API.
- `worker`: BotSupervisor, feeds, engines, and background jobs.
- `postgres`: durable application state.

Cloudflare supplies DNS, HTTPS, and Google authentication through Access. Atlas does not implement passwords. Broker credentials are server-side environment secrets and never enter the browser or PostgreSQL.

## Component Boundaries

### API and Services

API routes validate transport input and call application services. Routes do not construct ORM models, manipulate trading state, or contain business logic. Services coordinate repositories and domain components.

### Persistence

Engines never access database tables directly. Repositories are the only database access boundary. The schema, relationships, statuses, and migration rules live in `context/database.md`.

### Market Data

Providers normalize external data into common `Candle`, `Tick`, and `Instrument` models. The first implementation supports CSV historical data and Binance Spot public data. Oanda and futures providers are deferred.

Providers must:

- Normalize timestamps to UTC.
- Return Decimal domain values.
- Sort and deduplicate candles.
- Emit `CandleClosed` only for completed candles.
- Use the shared Clock for timeout decisions.
- Reconnect without duplicate subscriptions or events.

### Strategy Engine

Strategies evaluate completed candles and may observe ticks for state or monitoring. Tick observation does not create trading signals in the MVP. Strategy packages are deployed from a private Git repository and bots pin a repository commit SHA.

### Risk Engine

Every order intent passes through the Risk Engine. The initial controls are:

- Position sizing from account equity, risk-per-trade, and stop distance.
- Maximum open net positions.
- Stop-loss and take-profit calculation.
- Decimal quantity and instrument constraint validation.

Daily loss, maximum drawdown, and session restrictions are deferred follow-up controls. Risk receives an explicit account and market context; it does not query database tables directly.

### Execution Engine

The Execution Engine converts `RiskApproved` decisions into broker orders and owns order, fill, position, and trade transitions. The MVP uses one net position per account and instrument.

The `Broker` interface exposes order submission, cancellation, account state, positions, and reconciliation. Paper execution is deterministic and supports the shared next-candle-open backtest fill model. Binance Spot testnet execution is added later through the same interface.

### Journal and Analytics

Journal and Analytics consume completed trade facts and read persisted repositories. They do not own execution state. Journal writes are idempotent and associate trades with the account, bot, strategy version, fills, and market context.

## EventBus

The EventBus is lightweight, typed, in-process pub/sub. It is not a durable queue and must not be treated as the source of truth.

### Delivery Contract

- `publish()` is asynchronous and awaits handlers.
- Handlers run in deterministic registration order for trading-critical events.
- Every event includes `event_id`, `occurred_at`, and `correlation_id`.
- Trading events include `account_id`, `bot_id`, and `mode`.
- Handlers are idempotent and use event IDs or durable broker IDs for side effects.
- A handler failure is logged and classified; it is never silently swallowed.
- A safety-critical failure pauses the affected bot.
- The EventBus does not retry unknown broker operations; reconciliation decides whether retry is safe.

### Domain Events

```text
CandleClosed
TickReceived
SignalGenerated
RiskApproved
RiskRejected
OrderSubmitted
OrderFilled
PositionOpened
PositionUpdated
PositionClosed
TradeClosed
```

Error and lifecycle events include:

```text
ApiError
DataFeedError
OrderRejected
OrderFailed
StrategyError
ConnectionLost
ConnectionRestored
CircuitBreakerOpen
CircuitBreakerClosed
BotStatusChanged
HealthStatusChanged
```

### Candle Signal Flow

```text
Candle closes at T
  → CandleClosed
  → Strategy evaluates completed candle
  → SignalGenerated
  → Risk approves or rejects
  → Paper/real execution submits an order
  → OrderSubmitted / OrderFilled
  → Position and Trade events
  → Journal and Analytics persist/read facts
```

An approved signal confirmed at candle close is eligible for a fill at the next candle open in backtests and the paper simulator.

## Bot Runtime

`BotSupervisor` is the only component allowed to start or stop bot pipelines. It runs multiple independent pipelines in one worker process.

Atlas MVP explicitly supports **one** worker process. The supervisor coordinates concurrent operations within that process using in-process per-bot `asyncio.Lock` serialisation and durable PostgreSQL lifecycle state. There are **no cross-worker leases, heartbeats, or worker ownership** protocols; the single-worker deployment invariant replaces cross-worker mutual exclusion.

```text
STOPPED → STARTING → RUNNING → PAUSING → PAUSED
                         ↓          ↓
                       ERROR ← STOPPING
```

Each pipeline owns its subscriptions, strategy instance, risk context, feed tasks, and execution context. Database state records the desired and observed lifecycle state and the last error. There is no `bot_runs` table; runtime ownership is implicit in the single-worker topology.

On worker startup:

1. Load bots persisted as active (`desired_status != "stopped"`).
2. Create isolated pipelines for bots with `status` of `running` or `starting`.
3. Query the broker/account for orders and positions.
4. Persist a reconciliation result.
5. Resume only after successful reconciliation.

Failed reconciliation leaves the bot paused or errored and prevents new orders. Start, stop, pause, resume, and shutdown operations are idempotent.

**Health monitoring and orphan-state handling are deferred.** A crashed worker may leave a bot persisted as `RUNNING` or `STARTING` until Docker restart recovery triggers startup restoration. The single-worker invariant is safe only while Docker Compose runs one worker and Atlas does not support horizontal scaling, overlapping deployments, or externally launched duplicate workers. If that boundary changes, durable ownership must be designed before enabling multiple workers.

## Trading State Contracts

```text
Order: pending → submitted → partially_filled → filled
                         ↘ rejected / cancelled / unknown

Position: flat → open → reducing → closed

Trade: planned → entered → exited
```

An `unknown` order state is used after a broker timeout. Atlas reconciles before retrying to prevent duplicate orders. Client order IDs and broker order/fill IDs are persisted with uniqueness constraints.

## Backtesting

Backtesting uses the same Strategy, Risk, and Paper Execution contracts as paper trading, but runs in an isolated execution environment with a `SimulationClock`.

```text
Historical dataset
  → SimulationClock
  → Strategy
  → Risk
  → Paper Execution
  → Metrics
```

The canonical timing rule is:

```text
Signal confirmed at candle T close
  → order eligible at T+1
  → fill at T+1 open
```

Every run records its strategy commit, parameters, dataset identity, risk configuration, execution configuration, fill model, status, and results. Backtest records never become paper or testnet trading records.

## Error and Safety Rules

- Never silently swallow errors; log structured context and publish an error event.
- Retry only explicitly transient failures.
- Never retry an unknown order without reconciliation.
- Pause a bot when feed freshness, broker state, or execution safety cannot be established.
- Use circuit breakers for external dependencies.
- Keep a global trading pause/kill switch in the operational hardening scope.
- Surface health and trading pauses through the API and UI.
