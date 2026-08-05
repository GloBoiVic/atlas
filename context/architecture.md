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

## Identity Convention

**UUID identity is implemented end-to-end:**

- Python domain types use `UUID` from the standard library.
- ORM models use native PostgreSQL `UUID` columns (SQLAlchemy `Uuid` type).
- Repository protocols accept and return `UUID`.

The foundation migrations (001–004) introduced `String(36)` identifiers; migration 005
converted the existing tables to native PostgreSQL `UUID`, and migration 006 created
`instruments` and `candles` with `UUID` from the start. New code must continue to use
`UUID` — no `String(36)` or `str` identifiers.

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

Engines never access database tables directly. Repositories are the only database access boundary. Repository callers depend on `Protocol` interfaces, not ORM model classes.

**Session ownership:** Sessions yielded by the `get_async_session()` dependency are
read-only by default — the dependency never commits. Services that write create sessions
from the `async_session` factory and own commit/rollback explicitly — following the
`SqlAlchemySupervisorRepositories` pattern that uses
`async with self._session_factory.begin() as session:` for write scopes.

### Market Data

**Historical and live data provider interfaces are separate.** The historical interface
returns bounded lists of normalized candles. The live interface is an async generator of
streaming candles and ticks.

Providers must:

- Normalize timestamps to UTC.
- Return Decimal domain values.
- Sort and deduplicate candles.
- Use the shared Clock for observable/domain-time deadline decisions. Transport cancellation
  uses explicit asyncio timeout policy; SimulationClock must not control real network I/O.
- Reconnect without duplicate subscriptions or events.

**CandleClosed is emitted only by the live streaming feed or by historical replay
(Feature 05).** Feature 03 (historical data loader) does not emit CandleClosed.

**Instruments are provider-aware.** Candles reference an `instrument_id` FK rather than
duplicating fragile symbol strings. Provider-specific constraints (Binance LOT_SIZE vs.
OANDA margin rate) are stored as structured JSONB metadata, not flattened into shared
columns. Volume semantics are explicit: `base_volume`, `quote_volume`, `trade_count`,
`tick_volume`. OANDA's `tick_volume` (price-update count) is not the same as Binance's
`base_volume` (traded asset quantity).

**Rate-limit awareness:** Binance Spot REST API enforces a 1200-weight-per-minute ceiling.
The combination of REST candle fetching, streaming subscription management, and periodic
reconciliation in one worker process may approach this limit. Safe backoff (exponential
retry with jitter and circuit-breaker integration) is required for all REST calls; the
exact backoff implementation is deferred to the Binance adapter (Feature 09). Adapters
must not block async code during backoff.

### Strategy Engine

Strategies evaluate completed candles and return a lightweight trading decision. The
Strategy Engine assembles the canonical immutable `Signal` with full provenance —
`strategy_version_id`, instrument UUID, completed-candle timestamp, Decimal strength,
and strategy metadata. The engine owns bot/account scope, instrument and candle
provenance, strategy identity, validation, and deduplication.

**Strategy contracts:**

- Strategies return `StrategyDecision` (direction, Decimal strength, metadata); they
  never construct `Signal` objects.
- Strategies declare a timeframe-aware `DataRequirement`. Feature 04 validates one
  candle requirement against the bot configuration.
- Tick observation via `on_tick()` is supported for state/monitoring but does not
  generate trading signals in the MVP.
- Strategy hooks are synchronous and computation-focused; they perform no I/O.

**Engine responsibilities:**

- Validates completed-candle instrument, timeframe, and completeness before evaluation.
- Silently rejects duplicate candle events.
- Owns warm-up lifecycle: feeds historical candles to rebuild strategy state without
  emitting signals. Signal generation begins only after warm-up completes.
- Wraps strategy execution: an exception produces no signal, publishes `StrategyError`,
  and pauses the affected bot (fail-closed under EventBus safety rules).

**Deployment trust:**

- The runtime registry resolves only already-deployed, explicitly registered strategy
  packages with verified pinned commit SHAs.
- The deployed package owns the parameter schema and safe defaults; bots and backtests
  own selected YAML values that are validated, frozen, and recorded alongside the
  strategy version identity.
- Registry code does not clone repositories, install dependencies, or execute
  API-supplied import paths.
- Missing packages or identity mismatches fail closed — the bot does not start.

Strategy packages are deployed from a private Git repository. Bots pin a repository
commit SHA. The same contracts run in backtesting and paper trading.

### Risk Engine

Every order intent passes through the Risk Engine. The initial controls are:

- Position sizing from account equity, risk-per-trade, and stop distance.
- Maximum open net positions.
- Stop-loss and take-profit calculation.
- Decimal quantity and instrument constraint validation.

Daily loss, maximum drawdown, and trading session controls are deferred follow-up controls. Risk receives an explicit account and market context (`RiskContext`); it does not query database tables directly. Risk configuration lives in the bot's YAML configuration, not a separate database table.

### Execution Engine

The Execution Engine converts `RiskApproved` decisions into broker orders and owns order, fill, position, and trade transitions. The MVP uses one net position per account and instrument.

The `Broker` interface exposes order submission, cancellation, account state, positions, and reconciliation. Paper execution is deterministic and uses the shared Broker fill algorithm for both backtests and live paper trading. The algorithm is identical in both modes; only the price source differs: in backtest replay the fill price comes from the next candle's open price, while in live paper mode it comes from the current executable market price supplied by the execution context. Binance Spot testnet execution is added later through the same interface.

**Trade lifecycle:** A `Trade` entity is created when a position opens and finalized when the position closes. It aggregates fills and carries gross/net P&L, fees, and market context. Trades are the canonical source of truth for journaling and analytics.

**Order-type scope:** MVP order types are market entries and execution-managed protective exits only. Limit, stop-limit, OCO, iceberg, and order-book-aware fill models are deferred.

**Fees and slippage:** Configurable taker fee (default 0.05% per fill) and fixed adverse slippage (default 0.05% per fill). Both are recorded in `execution_config` on every backtest run. Maker/rebate tiers and OHLC-based spread/volume inference are deferred.

**Partial fills:** The state contract supports partial fills, but the default Paper Broker fills complete. When partial fills are enabled, quantity-weighted average entry/exit prices are used with one net position per account/instrument.

**Protective-trigger ambiguity:** When both stop-loss and take-profit levels could be touched in a single candle (high and low both exceeding limits), a conservative deterministic rule applies: stop-loss first. This rule is recorded in `execution_config`.

**Unknown order state:** A broker timeout or non-deterministic response produces an `unknown` order state. The system fails closed — unknown orders are never retried until reconciliation resolves the state. The EventBus does not retry unknown broker operations; reconciliation decides whether retry is safe.

### Journal and Analytics

Journal and Analytics consume completed Trade facts and read persisted repositories. They do not own execution state. Journal writes are idempotent and associate trades with the account, bot, strategy version, and market context.

**Numeric policy:** Monetary metrics (P&L, fees, drawdown amounts, account equity) use `Decimal`/`NUMERIC`. Non-monetary ratios (Sharpe, profit factor) may use `Float`/`FLOAT`. A third category — **Decimal ratios** (total_return: normalized cumulative return as an exact Decimal, e.g. 0.125 = 12.5%) — uses `Decimal`/`NUMERIC` for precision but is not a monetary value. The canonical metric definition authority is `context/features/10-journal-analytics.md`. All categories must define serialization behavior and explicit undefined-value handling (e.g., zero variance, no losing trades).

## EventBus

The EventBus is lightweight, typed, in-process pub/sub. It is not a durable queue and must not be treated as the source of truth.

### Delivery Contract

- `publish()` is asynchronous and awaits handlers.
- Handlers run in deterministic registration order for trading-critical events.
- Every event includes `event_id` (`UUID`), `occurred_at`, and `correlation_id` (`UUID`).
- Trading events include `account_id` (`UUID`), `bot_id` (`UUID`), and `mode`.
- Handlers are idempotent and use event IDs or durable broker IDs for side effects.
- A handler failure is logged, recorded via `FailureRecorder`, and pauses the affected bot.
- The EventBus does not retry unknown broker operations; reconciliation decides whether retry is safe.
- `FailureRecorder` is an in-memory protocol (`InMemoryFailureRecorder`). Durable dead-letter storage is deferred.

### Domain Events (Payload Contracts)

Events are frozen `@dataclass` subclasses of `DomainEvent`. `DomainEvent` carries common
metadata (`event_id: UUID`, `occurred_at: datetime`, `correlation_id: UUID`,
`account_id: UUID | None`, `bot_id: UUID | None`, `mode: AccountMode | None`).

**Required payload contracts** (each event type must carry its own typed payload fields):

```text
Trading:
CandleClosed          —  candle: Candle
TickReceived          —  tick: Tick
SignalGenerated       —  signal: Signal  (strategy_version_id is canonical on Signal)
RiskApproved          —  signal: Signal, position_size: Decimal,
                         stop_loss: Decimal, take_profit: Decimal
RiskRejected          —  signal: Signal, reason: str
OrderSubmitted        —  order: Order, broker_order_id: str
OrderFilled           —  order: Order, fill: Fill
PositionOpened        —  position: Position
PositionUpdated       —  position: Position
PositionClosed        —  position: Position
TradeClosed           —  trade: Trade

Error and lifecycle:
ApiError              —  component: str, error: str
DataFeedError         —  instrument_id: UUID, error: str
OrderRejected         —  order_id: UUID, reason: str
OrderFailed           —  order_id: UUID, error: str
StrategyError         —  bot_id: UUID, error: str
ConnectionLost        —  provider: str
ConnectionRestored    —  provider: str
CircuitBreakerOpen    —  component: str
CircuitBreakerClosed  —  component: str
BotStatusChanged      —  (inherits DomainEvent metadata)
HealthStatusChanged   —  component: str, status: str
```

**Current implementation status:** `CandleClosed` carries `candle: Candle` and
`TickReceived` carries `tick: Tick` (both keyword-only dataclass fields). The remaining
event subclasses are still defined with `pass` — their payload fields must be added before
the Feature 04+ event emission integration. The `DomainEvent` base class uses `UUID` typed
fields.

### EventBus Implementation

The `EventBus` class supports typed subscription, sequential awaited delivery, failure
recording, and bot-pause on safety-critical failures. It uses per-type handler lists and
continues processing remaining handlers after a failure.

### Candle Signal Flow

```text
Candle closes at T
  → CandleClosed
  → Strategy evaluates completed candle
  → SignalGenerated
  → Risk approves or rejects
  → RiskApproved / RiskRejected
  → Execution submits order
  → OrderSubmitted / OrderFilled
  → Position and Trade events
  → Journal and Analytics consume facts
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

Each pipeline owns its subscriptions, strategy instance, risk context, feed tasks, and execution context. Database state records the desired and observed lifecycle state and the last error.

On worker startup:

1. Load bots persisted as active (`desired_status != "stopped"`), filtering for those with `status` of `running` or `starting`.
2. Create isolated pipelines for those bots.
3. Query the broker/account for orders and positions (`Reconciler.reconcile`).
4. Persist a reconciliation result.
5. Enable execution only after successful reconciliation (`is_safe_to_execute`).

Failed reconciliation leaves the bot in `starting` state with `last_error` set and prevents new orders. Start, stop, pause, resume, and shutdown operations are idempotent.

## Trading State Contracts

```text
Order: pending → submitted → partially_filled → filled
                         ↘ rejected / cancelled / unknown

Position: flat → open → reducing → closed

Trade: entered → exited
```

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

Every run records its strategy commit, parameters, dataset identity (fingerprint), risk configuration, execution configuration, fill model, status, and results. Backtest records never become paper or testnet trading records.

## Production Mode

`AccountMode.PRODUCTION` exists in the enum but must **never** be accepted in the MVP. A production adapter and a deployment-specific safety gate (e.g., a physical confirmation step, a separate configuration file, or a dedicated deployment manifest) must exist before the system allows a `PRODUCTION` mode bot to start. Until those mechanisms are designed and implemented, `production` in the enum is a reserved value that should be rejected by configuration validation.

## Error and Safety Rules

- Never silently swallow errors; log structured context and publish an error event.
- Retry only explicitly transient failures.
- Never retry an unknown order without reconciliation.
- Pause a bot when feed freshness, broker state, or execution safety cannot be established.
- Use circuit breakers for external dependencies.
- Keep a global trading pause/kill switch in the operational hardening scope.
- Surface health and trading pauses through the API and UI.
