# Atlas — Database

## Overview

Atlas uses PostgreSQL for persistent storage. SQLAlchemy 2.0 is the ORM. Alembic handles schema migrations.

All data access goes through repository abstractions. Engines never directly manipulate database tables.
The detailed SQLAlchemy API patterns are in `context/library-docs.md` and
`.agents/skills/sqlalchemy-orm/SKILL.md`; this document owns Atlas's schema and persistence
invariants.

---

## Identity Convention

**UUID identity is implemented end-to-end:**

- Python domain types use `UUID` from the standard library.
- SQLAlchemy ORM models use `Uuid` column type (native PostgreSQL UUID).
- Alembic migrations create `UUID` columns, not `String(36)`.
- Repository protocols accept and return `UUID` typed identifiers.

The foundation migrations 001–004 introduced `String(36)` identifiers with
`str(uuid4())` defaults for SQLite test compatibility. Migration **005** converted the
existing tables to native PostgreSQL `UUID` (`ALTER COLUMN ... TYPE UUID USING ...` with
FK constraint recreation), and migration **006** created `instruments` and `candles`
with native `UUID` from the start. All new models, migrations, and repository protocols
use the UUID convention; `String(36)` survives only as historical migration notes.

---

## Database Connection

```python
# backend/persistence/database.py
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
```

**Transaction ownership:** The `get_async_session()` dependency yields read-only sessions
by default — it never commits. Commit and rollback ownership is explicit at the service
or unit-of-work boundary. Domain services and trading components requiring controlled
transaction boundaries create their own sessions from the `async_session` factory and own
commit/rollback explicitly.

The `SqlAlchemySupervisorRepositories` pattern demonstrates the correct approach: it
receives `async_session_factory`, and write operations use
`async with self._session_factory.begin() as session:` for a managed scope that commits
on success and rolls back on exception.

---

## Tables

Migration order must create reference tables before dependent trading tables. The core
foundation tables that exist in the deployed schema are documented below. Feature 03
delivered `instruments` and `candles` (migration 006); the remaining trading tables
(Feature 04+) are listed under Planned Schema but are not yet migrated.

### Accounts

The MVP has one configured trading account, but account identity is explicit so paper and
broker state cannot be mixed.

```sql
-- Deployed schema: accounts uses native UUID (id UUID PRIMARY KEY DEFAULT gen_random_uuid()).
-- The foundation String(36) id was converted by migration 005.
CREATE TABLE accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    broker VARCHAR(50) NOT NULL,
    mode VARCHAR(20) NOT NULL,  -- "paper", "testnet", "production"
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL
);
```

### Strategies

Stores registered strategy definitions. Strategy code is deployed from a private Git repository;
the database stores metadata and the exact commit selected for a bot. Atlas never loads
arbitrary class paths supplied by an API request.

```sql
CREATE TABLE strategies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL UNIQUE,
    entrypoint VARCHAR(500) NOT NULL,
    repository VARCHAR(500) NOT NULL,
    version VARCHAR(50) NOT NULL DEFAULT '1.0.0',
    commit_sha VARCHAR(64) NOT NULL,
    parameters JSONB NOT NULL DEFAULT '{}',
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### Strategy Versions

Immutable strategy versions that can be selected by backtests and bots.

```sql
CREATE TABLE strategy_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id UUID NOT NULL REFERENCES strategies(id),
    repository VARCHAR(500) NOT NULL,
    commit_sha VARCHAR(64) NOT NULL,
    parameters JSONB NOT NULL DEFAULT '{}',
    deployed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE(strategy_id, commit_sha)
);
```

### Bots

Trading bot instances. Lifecycle state is persisted here; runtime ownership is implicit in
the single-worker topology.

```sql
CREATE TABLE bots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    strategy_id UUID REFERENCES strategies(id),
    strategy_version_id UUID REFERENCES strategy_versions(id),
    account_id UUID NOT NULL REFERENCES accounts(id),
    broker VARCHAR(50) NOT NULL,
    mode VARCHAR(20) NOT NULL,
    instrument VARCHAR(50) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    desired_status VARCHAR(20) NOT NULL DEFAULT 'stopped',
    status VARCHAR(20) NOT NULL DEFAULT 'stopped',
    pnl NUMERIC(20, 8) DEFAULT 0,
    started_at TIMESTAMP WITH TIME ZONE,
    stopped_at TIMESTAMP WITH TIME ZONE,
    last_error TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### Reconciliation Runs

Records broker synchronization before a bot resumes after startup or connection loss.

```sql
CREATE TABLE reconciliation_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES accounts(id),
    bot_id UUID REFERENCES bots(id),
    status VARCHAR(20) NOT NULL,
    broker_snapshot JSONB NOT NULL DEFAULT '{}',
    differences JSONB NOT NULL DEFAULT '{}',
    started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT
);
```

---

## Schema — Feature 03 Delivered and Feature 04+ Planned

`instruments` and `candles` (documented below) were delivered by migration **006** and are
part of the deployed schema, alongside the foundation tables. The remaining tables (Orders
through Backtest Trades) document the target domain shape and are **not yet migrated**.

### Instruments

Provider-aware instrument reference. Uniqueness is scoped to `(symbol, provider)`.
Provider-specific constraints are stored as structured JSONB metadata rather than
pretending Binance and OANDA share identical fields. **Migrated in 006** — native `UUID`
from creation.

```sql
CREATE TABLE instruments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR(50) NOT NULL,              -- normalized symbol, e.g. "BTCUSDT"
    asset_type VARCHAR(20) NOT NULL,          -- "crypto", "forex"
    provider VARCHAR(50) NOT NULL,            -- "binance", "oanda"
    base_currency VARCHAR(10),
    quote_currency VARCHAR(10),
    price_precision INT NOT NULL,             -- display precision
    quantity_precision INT NOT NULL,          -- trade units precision
    constraints JSONB NOT NULL DEFAULT '{}',  -- provider-specific metadata
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(symbol, provider)
);
```

**Constraints structure (examples):**

```jsonc
// Binance LOT_SIZE, PRICE_FILTER, MIN_NOTIONAL
{
  "min_qty": "0.001",
  "max_qty": "100000",
  "step_size": "0.001",
  "tick_size": "0.01",
  "min_notional": "10"
}

// OANDA marginRate, displayPrecision, tradeUnitsPrecision, pipLocation
{
  "margin_rate": "0.05",
  "display_precision": 5,
  "trade_units_precision": 0,
  "pip_location": -4
}
```

### Candles

Historical and streaming OHLC data. Candles reference an `instrument_id` rather than
duplicating fragile symbol strings. **Migrated in 006** — native `UUID` from creation.
Volume fields distinguish provider-specific semantics:

- **`base_volume`**: Traded quantity of the base asset (Binance kline `v`).
- **`quote_volume`**: Traded quantity of the quote asset (Binance kline `q`).
- **`trade_count`**: Number of trades in the interval (Binance kline `n`).
- **`tick_volume`**: Number of price updates or tick count (OANDA volume).

The `price_basis` column identifies the price source: `"trade"` for Binance (trade prices),
`"mid"`, `"bid"`, or `"ask"` for OANDA. Uniqueness includes `price_basis` because OANDA
may store multiple price bases for the same interval.

```sql
CREATE TABLE candles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instrument_id UUID NOT NULL REFERENCES instruments(id),
    provider VARCHAR(50) NOT NULL,              -- "binance", "oanda"
    timeframe VARCHAR(10) NOT NULL,             -- "1m", "5m", "1h", "4h", "1d"
    open_time TIMESTAMP WITH TIME ZONE NOT NULL,  -- start of the interval (UTC)
    close_time TIMESTAMP WITH TIME ZONE,          -- end of the interval
    price_basis VARCHAR(10) NOT NULL DEFAULT 'trade',  -- "trade", "mid", "bid", "ask"
    open NUMERIC(20, 8) NOT NULL,
    high NUMERIC(20, 8) NOT NULL,
    low NUMERIC(20, 8) NOT NULL,
    close NUMERIC(20, 8) NOT NULL,
    base_volume NUMERIC(20, 8) NOT NULL DEFAULT 0,
    quote_volume NUMERIC(20, 8),                -- Binance quote asset volume
    trade_count INT,                             -- Binance trade count
    taker_buy_base_volume NUMERIC(20, 8),        -- Binance taker buy base volume
    taker_buy_quote_volume NUMERIC(20, 8),       -- Binance taker buy quote volume
    tick_volume BIGINT,                          -- OANDA price-update count
    is_complete BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(instrument_id, provider, timeframe, open_time, price_basis)
);

CREATE INDEX idx_candles_lookup ON candles(instrument_id, provider, timeframe, open_time);
```

**Binance kline specifics:** Binance Spot klines use millisecond integers for both
`open_time` and `close_time`. Volume/price values arrive as decimal strings. The WebSocket
payload includes `"x": true/false` indicating whether the kline is closed. The
`binance_` prefixed fields preserve raw Binance data; `base_volume` maps to kline `v`,
`quote_volume` to `q`, `trade_count` to `n`, `taker_buy_base_volume` to `V`,
`taker_buy_quote_volume` to `Q`.

**OANDA candle specifics (deferred):** OANDA candles use RFC3339 timestamps. Volume is
`tick_volume` (number of price changes), not traded asset volume. OANDA live pricing is a
stream of price updates, not completed OHLC candles — candle construction from live OANDA
data is a deferred design concern.

### Orders

```sql
CREATE TABLE orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES accounts(id),
    bot_id UUID REFERENCES bots(id),
    strategy_version_id UUID REFERENCES strategy_versions(id),
    broker_order_id VARCHAR(255),
    client_order_id VARCHAR(255) NOT NULL UNIQUE,
    instrument_id UUID REFERENCES instruments(id),
    symbol VARCHAR(50) NOT NULL,
    side VARCHAR(10) NOT NULL,
    quantity NUMERIC(20, 8) NOT NULL,
    order_type VARCHAR(20) NOT NULL,
    price NUMERIC(20, 8),
    stop_loss NUMERIC(20, 8),
    take_profit NUMERIC(20, 8),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    fill_price NUMERIC(20, 8),
    filled_quantity NUMERIC(20, 8) NOT NULL DEFAULT 0,
    filled_at TIMESTAMP WITH TIME ZONE,
    strategy_name VARCHAR(255),
    signal_metadata JSONB DEFAULT '{}',
    broker VARCHAR(50) NOT NULL,
    mode VARCHAR(20) NOT NULL,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_orders_status ON orders(status);
CREATE UNIQUE INDEX idx_orders_broker_id ON orders(broker_order_id) WHERE broker_order_id IS NOT NULL;
```

### Fills

Append-only fill records. Positions, trades, and P&L are derived from fills.

```sql
CREATE TABLE fills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES orders(id),
    account_id UUID NOT NULL REFERENCES accounts(id),
    broker_fill_id VARCHAR(255),
    quantity NUMERIC(20, 8) NOT NULL,
    price NUMERIC(20, 8) NOT NULL,
    fee NUMERIC(20, 8) NOT NULL DEFAULT 0,
    filled_at TIMESTAMP WITH TIME ZONE NOT NULL,
    UNIQUE(order_id, broker_fill_id)
);
```

### Positions

One net position per account and instrument.

```sql
CREATE TABLE positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES accounts(id),
    bot_id UUID REFERENCES bots(id),
    strategy_version_id UUID REFERENCES strategy_versions(id),
    instrument_id UUID REFERENCES instruments(id),
    symbol VARCHAR(50) NOT NULL,
    side VARCHAR(10) NOT NULL,
    entry_price NUMERIC(20, 8) NOT NULL,
    current_price NUMERIC(20, 8),
    quantity NUMERIC(20, 8) NOT NULL,
    stop_loss NUMERIC(20, 8),
    take_profit NUMERIC(20, 8),
    unrealized_pnl NUMERIC(20, 8) DEFAULT 0,
    realized_pnl NUMERIC(20, 8) DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'open',
    broker VARCHAR(50) NOT NULL,
    mode VARCHAR(20) NOT NULL,
    opened_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    closed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_one_open_net_position
    ON positions(account_id, instrument_id, mode) WHERE status = 'open';
```

### Trades

Explicit Trade entity connecting fills to journaling/analytics. Created when a position
opens, finalized when the position closes.

```sql
CREATE TABLE trades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES accounts(id),
    bot_id UUID REFERENCES bots(id),
    strategy_version_id UUID REFERENCES strategy_versions(id),
    position_id UUID REFERENCES positions(id),
    instrument_id UUID REFERENCES instruments(id),
    symbol VARCHAR(50) NOT NULL,
    direction VARCHAR(10) NOT NULL,
    entry_price NUMERIC(20, 8) NOT NULL,
    exit_price NUMERIC(20, 8),
    quantity NUMERIC(20, 8) NOT NULL,
    gross_pnl NUMERIC(20, 8),
    net_pnl NUMERIC(20, 8),
    total_fees NUMERIC(20, 8) DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'entered',
    signal_metadata JSONB DEFAULT '{}',
    market_context JSONB DEFAULT '{}',
    entry_time TIMESTAMP WITH TIME ZONE NOT NULL,
    exit_time TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_trades_status ON trades(status);
```

### Journal Entries

Human-readable trade journal attached to completed trades via `trade_id`.

```sql
CREATE TABLE journal_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES accounts(id),
    bot_id UUID REFERENCES bots(id),
    strategy_version_id UUID REFERENCES strategy_versions(id),
    trade_id UUID NOT NULL UNIQUE,
    instrument_id UUID REFERENCES instruments(id),
    symbol VARCHAR(50) NOT NULL,
    direction VARCHAR(10) NOT NULL,
    entry_price NUMERIC(20, 8) NOT NULL,
    exit_price NUMERIC(20, 8),
    quantity NUMERIC(20, 8) NOT NULL,
    pnl NUMERIC(20, 8),
    strategy_name VARCHAR(255) NOT NULL,
    signal JSONB DEFAULT '{}',
    market_conditions JSONB DEFAULT '{}',
    notes TEXT,
    risk_metadata JSONB DEFAULT '{}',
    opened_at TIMESTAMP WITH TIME ZONE NOT NULL,
    closed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_journal_strategy ON journal_entries(strategy_name);
```

### Backtest Runs

```sql
CREATE TABLE backtest_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_name VARCHAR(255) NOT NULL,
    strategy_version VARCHAR(50) NOT NULL,
    strategy_commit_sha VARCHAR(64) NOT NULL,
    strategy_parameters JSONB NOT NULL,
    instrument_id UUID REFERENCES instruments(id),
    symbol VARCHAR(50) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    data_source VARCHAR(255) NOT NULL,
    dataset_id VARCHAR(255) NOT NULL,
    start_date TIMESTAMP WITH TIME ZONE NOT NULL,
    end_date TIMESTAMP WITH TIME ZONE NOT NULL,
    risk_config JSONB NOT NULL,
    execution_config JSONB NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    fill_model VARCHAR(100) NOT NULL DEFAULT 'next_candle_open',
    total_return NUMERIC(20, 8),
    win_rate FLOAT,
    sharpe_ratio FLOAT,
    max_drawdown NUMERIC(20, 8),
    profit_factor FLOAT,
    total_trades INT,
    winning_trades INT,
    losing_trades INT,
    error_message TEXT,
    last_processed_timestamp TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_backtest_status ON backtest_runs(status);
```

### Backtest Trades

```sql
CREATE TABLE backtest_trades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    backtest_run_id UUID NOT NULL REFERENCES backtest_runs(id) ON DELETE CASCADE,
    instrument_id UUID REFERENCES instruments(id),
    symbol VARCHAR(50) NOT NULL,
    direction VARCHAR(10) NOT NULL,
    entry_price NUMERIC(20, 8) NOT NULL,
    exit_price NUMERIC(20, 8),
    quantity NUMERIC(20, 8) NOT NULL,
    pnl NUMERIC(20, 8),
    entry_time TIMESTAMP WITH TIME ZONE NOT NULL,
    exit_time TIMESTAMP WITH TIME ZONE,
    signal_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_backtest_trades_run ON backtest_trades(backtest_run_id);
```

---

## Deferred Tables

The following tables were considered speculatively but are **not required for the MVP**:

- **risk_configurations** — Risk configuration lives in the bot's YAML configuration, not
  a separate table.
- **health_status** — Health monitoring is in-process (EventBus + circuit breaker).
- **dead_letter_events** — Event failures are recorded in-memory by
  `InMemoryFailureRecorder`. Durable dead-letter storage is deferred.

---

## Entity Relationship Diagram (Current Schema)

```
accounts ─────────────────────
    |                         |
    ├── strategies            |
    |       |                 |
    |       └── strategy_versions
    |                         |
    ├── bots ───── reconciliation_runs
    |
instruments ──── candles        (migration 006)
```

**Planned additions (Feature 04+):**

```
    bots ──── orders ──── fills ──── positions ──── trades ──── journal_entries

    backtest_runs ──── backtest_trades
```

---

## Repository Pattern

All data access goes through repositories. Callers depend on `Protocol` interfaces, not
ORM model classes or concrete repository implementations.

### Repository Protocol Pattern (UUID Target)

```python
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

@dataclass(frozen=True, slots=True)
class BotRecord:
    id: UUID
    # ...

class BotRepository(Protocol):
    async def get(self, bot_id: UUID) -> BotRecord | None:
        ...
```

**Status:** Repository protocols use `UUID` typed identifiers. The transitional `str`
identifiers from the foundation are gone.

### SQLAlchemy Implementation

SQLAlchemy repository implementations own their session lifecycles. They create sessions
from a factory and manage their own transaction boundaries:

```python
from uuid import UUID

class SqlAlchemySupervisorRepositories:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def persist_lifecycle(self, bot_id: UUID, state: LifecycleUpdate) -> BotRecord | None:
        async with self._session_factory.begin() as session:
            bot = await session.get(Bot, bot_id)
            if bot is None:
                return None
            bot.desired_status = state.desired_status
            bot.status = state.status
            bot.last_error = state.last_error
            bot.started_at = state.started_at
            bot.stopped_at = state.stopped_at
            await session.flush()
            return _bot_record(bot)
```

**Key pattern:** Write operations use `async with self._session_factory.begin()` which
commits on scope exit and rolls back on exception. Read-only methods use
`async with self._session_factory()` without `.begin()` and issue no commit.

### In-Memory Implementation (Tests)

```python
class InMemorySupervisorRepositories:
    """Deterministic repository implementation for tests."""
    ...
```

---

## Migration History

Alembic manages schema migrations. The migration history is preserved; no migrations are
rewritten or deleted.

- `001_initial_schema` — `accounts` table (uses `sa.String(36)` for ID).
- `002_bot_supervisor_schema` — `strategies`, `strategy_versions`, `bots`, `bot_runs`,
  `reconciliation_runs` (all use `sa.String(36)` for IDs).
- `003_bot_run_unique_constraint` — `uq_bot_runs_bot_id` unique constraint.
- `004_drop_bot_runs` — Drops `bot_runs` table.
- `005_uuid_identity_migration` — Converts existing `String(36)` primary-key and
  foreign-key columns to native PostgreSQL `UUID` across `accounts`, `strategies`,
  `strategy_versions`, `bots`, and `reconciliation_runs`. Uses `ALTER COLUMN ...
  TYPE UUID USING ...` with explicit casting. Drops and recreates FK constraints.
  Requires upgrade/downgrade tests in Codespace PostgreSQL.
- `006_create_instruments_and_candles` — Creates `instruments` and `candles` tables
  (native `UUID` columns, unique constraints, `idx_candles_lookup` index).
  Requires upgrade/downgrade tests in Codespace PostgreSQL.

Existing migrations use `String(36)`. Migration 005 closes the UUID gap for the
existing tables. Migration 006 creates all new tables with native PostgreSQL `UUID`
columns (no `String(36)` transitional gap). The migration history is immutable —
no existing migrations are rewritten or deleted.

---

## Key Rules

1. **No direct table manipulation.** All access goes through repositories.
2. **UUIDs for all primary keys.** Native PostgreSQL `UUID` with SQLAlchemy `Uuid`.
   Migrations 001–004 used `String(36)`; migration 005 converted existing tables and all
   later tables use native `UUID` from creation.
3. **Timestamps with timezone.** All timestamps are `TIMESTAMP WITH TIME ZONE`.
4. **JSONB for flexible data.** Signal metadata, risk config, broker snapshots,
   and provider-specific instrument constraints stored as JSONB.
5. **Soft deletes** via `is_active` or `status` fields where applicable.
6. **Migrations for all changes.** Never modify the schema manually.
7. **Backtest data is separate.** Backtest runs and trades are distinct from live/paper data.
8. **Broker identity is durable.** Client order IDs and broker order/fill IDs are unique
   where available.
9. **Secrets stay outside the database.** Broker credentials are server environment secrets.
10. **Repository protocols are the boundary.** Callers depend on `Protocol` interfaces.
