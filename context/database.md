# Atlas — Database

## Overview

Atlas uses PostgreSQL for persistent storage. SQLAlchemy 2.0 is the ORM. Alembic handles schema migrations.

All data access goes through repository abstractions. Engines never directly manipulate database tables.

---

## Database Connection

```python
# backend/persistence/database.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

DATABASE_URL = "postgresql+asyncpg://atlas:atlas@localhost:5432/atlas"

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)

async def get_session():
    async with async_session() as session:
        yield session
```

---

## Tables

Migration order must create reference tables (`strategies`, `strategy_versions`, `accounts`, `instruments`, and `bots`) before dependent trading tables (`orders`, `fills`, `positions`, and `journal_entries`). The SQL below documents the domain shape; Alembic migrations should enforce the dependency order.

### Strategies

Stores registered strategy definitions. Strategy code is deployed from a private Git repository; the database stores metadata and the exact commit selected for a bot. Atlas never loads arbitrary class paths supplied by an API request.

```sql
CREATE TABLE strategies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL UNIQUE,
    entrypoint VARCHAR(500) NOT NULL,  -- registry key, not user-supplied import path
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

### Accounts

The MVP has one configured trading account, but account identity is explicit so paper and broker state cannot be mixed.

```sql
CREATE TABLE accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL UNIQUE,
    broker VARCHAR(50) NOT NULL,
    mode VARCHAR(20) NOT NULL,  -- "paper", "testnet"
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### Instruments

Stores available trading instruments.

```sql
CREATE TABLE instruments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) NOT NULL UNIQUE,  -- e.g., "BTCUSDT", "EUR_USD"
    type VARCHAR(20) NOT NULL,  -- "forex", "crypto", "futures"
    provider VARCHAR(50) NOT NULL,  -- "binance", "oanda"
    pip_location INT DEFAULT 0,
    display_precision INT DEFAULT 2,
    trade_units_precision INT DEFAULT 8,
    margin_rate DECIMAL(10, 4) DEFAULT 1.0,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### Candles

Historical OHLC data.

```sql
CREATE TABLE candles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instrument VARCHAR(50) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,  -- "1m", "5m", "1h", "4h", "1d"
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    open DECIMAL(20, 8) NOT NULL,
    high DECIMAL(20, 8) NOT NULL,
    low DECIMAL(20, 8) NOT NULL,
    close DECIMAL(20, 8) NOT NULL,
    volume DECIMAL(20, 8) NOT NULL DEFAULT 0,
    provider VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(instrument, timeframe, timestamp, provider)
);

CREATE INDEX idx_candles_lookup ON candles(instrument, timeframe, timestamp);
```

### Orders

All orders placed by the system.

```sql
CREATE TABLE orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES accounts(id),
    bot_id UUID REFERENCES bots(id),
    strategy_version_id UUID REFERENCES strategy_versions(id),
    broker_order_id VARCHAR(255),
    client_order_id VARCHAR(255) NOT NULL UNIQUE,
    instrument VARCHAR(50) NOT NULL,
    side VARCHAR(10) NOT NULL,  -- "buy", "sell"
    quantity DECIMAL(20, 8) NOT NULL,
    order_type VARCHAR(20) NOT NULL,  -- "market", "limit", "stop"
    price DECIMAL(20, 8),
    stop_loss DECIMAL(20, 8),
    take_profit DECIMAL(20, 8),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- "pending", "submitted", "partially_filled", "filled", "cancelled", "rejected", "unknown"
    fill_price DECIMAL(20, 8),
    filled_quantity DECIMAL(20, 8) NOT NULL DEFAULT 0,
    filled_at TIMESTAMP WITH TIME ZONE,
    strategy_name VARCHAR(255),
    signal_metadata JSONB DEFAULT '{}',
    broker VARCHAR(50) NOT NULL,  -- "binance", "oanda", "paper"
    mode VARCHAR(20) NOT NULL,  -- "paper", "testnet"
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_instrument ON orders(instrument);
CREATE UNIQUE INDEX idx_orders_broker_id ON orders(broker_order_id) WHERE broker_order_id IS NOT NULL;
```

### Fills

Broker or simulator fills are append-only facts. Positions and trades are derived from fills.

```sql
CREATE TABLE fills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES orders(id),
    account_id UUID NOT NULL REFERENCES accounts(id),
    broker_fill_id VARCHAR(255),
    quantity DECIMAL(20, 8) NOT NULL,
    price DECIMAL(20, 8) NOT NULL,
    fee DECIMAL(20, 8) NOT NULL DEFAULT 0,
    filled_at TIMESTAMP WITH TIME ZONE NOT NULL,
    UNIQUE(order_id, broker_fill_id)
);
```

### Positions

Open and closed positions.

```sql
CREATE TABLE positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES accounts(id),
    bot_id UUID REFERENCES bots(id),
    strategy_version_id UUID REFERENCES strategy_versions(id),
    instrument VARCHAR(50) NOT NULL,
    side VARCHAR(10) NOT NULL,  -- "buy", "sell"
    entry_price DECIMAL(20, 8) NOT NULL,
    current_price DECIMAL(20, 8),
    quantity DECIMAL(20, 8) NOT NULL,
    stop_loss DECIMAL(20, 8),
    take_profit DECIMAL(20, 8),
    unrealized_pnl DECIMAL(20, 8) DEFAULT 0,
    realized_pnl DECIMAL(20, 8) DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'open',  -- "open", "closed"
    strategy_name VARCHAR(255),
    broker VARCHAR(50) NOT NULL,
    mode VARCHAR(20) NOT NULL,  -- "paper", "testnet"
    opened_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    closed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_positions_status ON positions(status);
CREATE INDEX idx_positions_instrument ON positions(instrument);
CREATE UNIQUE INDEX idx_one_open_net_position
    ON positions(account_id, instrument, mode) WHERE status = 'open';
```

### Journal Entries

Trade journal with context.

```sql
CREATE TABLE journal_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES accounts(id),
    bot_id UUID REFERENCES bots(id),
    strategy_version_id UUID REFERENCES strategy_versions(id),
    trade_id UUID NOT NULL UNIQUE,
    position_id UUID REFERENCES positions(id),
    instrument VARCHAR(50) NOT NULL,
    direction VARCHAR(10) NOT NULL,
    entry_price DECIMAL(20, 8) NOT NULL,
    exit_price DECIMAL(20, 8),
    quantity DECIMAL(20, 8) NOT NULL,
    pnl DECIMAL(20, 8),
    strategy VARCHAR(255) NOT NULL,
    strategy_version VARCHAR(50),
    signal JSONB DEFAULT '{}',
    market_conditions JSONB DEFAULT '{}',
    notes TEXT,
    screenshots JSONB DEFAULT '[]',  -- Array of screenshot URLs
    risk_metadata JSONB DEFAULT '{}',
    opened_at TIMESTAMP WITH TIME ZONE NOT NULL,
    closed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_journal_strategy ON journal_entries(strategy);
CREATE INDEX idx_journal_instrument ON journal_entries(instrument);
```

### Bots

Trading bot instances.

```sql
CREATE TABLE bots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    strategy_id UUID REFERENCES strategies(id),
    strategy_version_id UUID REFERENCES strategy_versions(id),
    account_id UUID NOT NULL REFERENCES accounts(id),
    broker VARCHAR(50) NOT NULL,
    mode VARCHAR(20) NOT NULL,  -- "paper", "testnet"
    instrument VARCHAR(50) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'stopped',  -- "stopped", "starting", "running", "pausing", "paused", "stopping", "error"
    pnl DECIMAL(20, 8) DEFAULT 0,
    started_at TIMESTAMP WITH TIME ZONE,
    stopped_at TIMESTAMP WITH TIME ZONE,
    last_error TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### Bot Runs

Records each runtime instance and supports restart/recovery diagnostics.

```sql
CREATE TABLE bot_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bot_id UUID NOT NULL REFERENCES bots(id) ON DELETE CASCADE,
    process_id VARCHAR(255),
    status VARCHAR(20) NOT NULL,  -- "starting", "running", "stopped", "failed"
    started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    stopped_at TIMESTAMP WITH TIME ZONE,
    last_heartbeat_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT
);
```

### Reconciliation Runs

Records broker synchronization before a bot resumes after startup or connection loss.

```sql
CREATE TABLE reconciliation_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES accounts(id),
    bot_id UUID REFERENCES bots(id),
    status VARCHAR(20) NOT NULL,  -- "running", "matched", "mismatched", "failed"
    broker_snapshot JSONB NOT NULL DEFAULT '{}',
    differences JSONB NOT NULL DEFAULT '{}',
    started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT
);
```

### Backtest Runs

Backtest execution records.

```sql
CREATE TABLE backtest_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_name VARCHAR(255) NOT NULL,
    strategy_version VARCHAR(50) NOT NULL,
    strategy_commit_sha VARCHAR(64) NOT NULL,
    strategy_parameters JSONB NOT NULL,
    instrument VARCHAR(50) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    data_source VARCHAR(255) NOT NULL,
    dataset_id VARCHAR(255) NOT NULL,
    start_date TIMESTAMP WITH TIME ZONE NOT NULL,
    end_date TIMESTAMP WITH TIME ZONE NOT NULL,
    risk_config JSONB NOT NULL,
    execution_config JSONB NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- "pending", "running", "completed", "failed", "cancelled"
    fill_model VARCHAR(100) NOT NULL DEFAULT 'next_candle_open',
    total_return DECIMAL(20, 8),
    win_rate FLOAT,
    sharpe_ratio FLOAT,
    max_drawdown DECIMAL(20, 8),
    profit_factor FLOAT,
    total_trades INT,
    winning_trades INT,
    losing_trades INT,
    error_message TEXT,
    error_traceback TEXT,
    last_processed_timestamp TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_backtest_status ON backtest_runs(status);
CREATE INDEX idx_backtest_strategy ON backtest_runs(strategy_name);
```

### Backtest Trades

Individual trades from backtest runs.

```sql
CREATE TABLE backtest_trades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    backtest_run_id UUID NOT NULL REFERENCES backtest_runs(id) ON DELETE CASCADE,
    instrument VARCHAR(50) NOT NULL,
    direction VARCHAR(10) NOT NULL,
    entry_price DECIMAL(20, 8) NOT NULL,
    exit_price DECIMAL(20, 8),
    quantity DECIMAL(20, 8) NOT NULL,
    pnl DECIMAL(20, 8),
    entry_time TIMESTAMP WITH TIME ZONE NOT NULL,
    exit_time TIMESTAMP WITH TIME ZONE,
    signal_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_backtest_trades_run ON backtest_trades(backtest_run_id);
```

### Risk Configuration

Risk settings per bot or global.

```sql
CREATE TABLE risk_configurations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bot_id UUID REFERENCES bots(id) ON DELETE CASCADE,
    max_open_positions INT DEFAULT 5,
    per_trade_risk DECIMAL(10, 4) DEFAULT 0.01,
    stop_loss_multiplier DECIMAL(10, 4) DEFAULT 2.0,
    take_profit_multiplier DECIMAL(10, 4) DEFAULT 3.0,
    is_default BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### Health Status

Component health tracking.

```sql
CREATE TABLE health_status (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    component VARCHAR(100) NOT NULL UNIQUE,
    status VARCHAR(20) NOT NULL DEFAULT 'healthy',  -- "healthy", "degraded", "unhealthy"
    last_error TEXT,
    last_error_time TIMESTAMP WITH TIME ZONE,
    consecutive_failures INT DEFAULT 0,
    last_success_time TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### Dead Letter Events

Events that failed processing.

```sql
CREATE TABLE dead_letter_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(100) NOT NULL,
    event_data JSONB NOT NULL,
    failed_component VARCHAR(100) NOT NULL,
    error_message TEXT NOT NULL,
    error_traceback TEXT,
    retry_count INT DEFAULT 0,
    max_retries INT DEFAULT 3,
    failed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    resolved BOOLEAN DEFAULT false,
    resolved_at TIMESTAMP WITH TIME ZONE
);
```

---

## Entity Relationship Diagram

```
strategies ────────> strategy_versions
                         │
accounts ───────────┐    │
                    ▼    ▼
                  bots ───────────────> risk_configurations
                    │
                    ├──> bot_runs
                    ├──> reconciliation_runs
                    ├──> positions ────> journal_entries
                    └──> orders ───────> fills

backtest_runs ───────────────────> backtest_trades

candles (standalone - historical data)

instruments (standalone - reference data)

health_status (standalone - system health)

dead_letter_events (standalone - error tracking)
```

---

## Repository Pattern

All data access goes through repositories. Engines never directly manipulate database tables.

### Base Repository

```python
# backend/persistence/repositories/base.py
from typing import Generic, TypeVar, List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

ModelType = TypeVar("ModelType")

class BaseRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session

    async def get_by_id(self, id: UUID) -> Optional[ModelType]:
        result = await self.session.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()

    async def get_all(self) -> List[ModelType]:
        result = await self.session.execute(select(self.model))
        return list(result.scalars().all())

    async def create(self, obj: ModelType) -> ModelType:
        self.session.add(obj)
        await self.session.commit()
        await self.session.refresh(obj)
        return obj

    async def update(self, obj: ModelType) -> ModelType:
        await self.session.commit()
        await self.session.refresh(obj)
        return obj

    async def delete(self, id: UUID) -> bool:
        obj = await self.get_by_id(id)
        if obj:
            await self.session.delete(obj)
            await self.session.commit()
            return True
        return False
```

### Specific Repositories

```python
# backend/persistence/repositories/strategy.py
class StrategyRepository(BaseRepository[Strategy]):
    async def get_by_name(self, name: str) -> Optional[Strategy]:
        result = await self.session.execute(
            select(Strategy).where(Strategy.name == name)
        )
        return result.scalar_one_or_none()

    async def get_active(self) -> List[Strategy]:
        result = await self.session.execute(
            select(Strategy).where(Strategy.is_active == True)
        )
        return list(result.scalars().all())
```

```python
# backend/persistence/repositories/journal.py
class JournalRepository(BaseRepository[JournalEntry]):
    async def get_closed_entries(
        self, start_date: datetime, end_date: datetime
    ) -> List[JournalEntry]:
        result = await self.session.execute(
            select(JournalEntry)
            .where(JournalEntry.closed_at >= start_date)
            .where(JournalEntry.closed_at <= end_date)
            .where(JournalEntry.pnl.isnot(None))
        )
        return list(result.scalars().all())

    async def get_by_strategy(self, strategy: str) -> List[JournalEntry]:
        result = await self.session.execute(
            select(JournalEntry)
            .where(JournalEntry.strategy == strategy)
        )
        return list(result.scalars().all())
```

---

## Migrations

Alembic manages schema migrations.

### Setup

```bash
# Initialize Alembic
alembic init alembic

# Generate migration after model changes
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

### Migration Example

```python
# alembic/versions/001_initial.py
def upgrade():
    op.create_table(
        'strategies',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('entrypoint', sa.String(500), nullable=False),
        sa.Column('repository', sa.String(500), nullable=False),
        sa.Column('commit_sha', sa.String(64), nullable=False),
        sa.Column('parameters', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

def downgrade():
    op.drop_table('strategies')
```

---

## Seeding Data

### Default Instruments

```python
# backend/persistence/seeds/instruments.py
DEFAULT_INSTRUMENTS = [
    # Crypto
    {"name": "BTCUSDT", "type": "crypto", "provider": "binance", "pip_location": 0, "display_precision": 2},
    {"name": "ETHUSDT", "type": "crypto", "provider": "binance", "pip_location": 0, "display_precision": 2},

]
```

### Default Risk Configuration

```python
# backend/persistence/seeds/risk_config.py
DEFAULT_RISK_CONFIG = {
    "max_open_positions": 5,
    "per_trade_risk": 0.01,
    "stop_loss_multiplier": 2.0,
    "take_profit_multiplier": 3.0,
}
```

---

## Key Rules

1. **No direct table manipulation.** All access goes through repositories.
2. **UUIDs for all primary keys.** No auto-increment integers.
3. **Timestamps with timezone.** All timestamps are `TIMESTAMP WITH TIME ZONE`.
4. **JSONB for flexible data.** Signal metadata, risk config, broker snapshots, and other variable data stored as JSONB.
5. **Soft deletes.** Use `is_active` or `status` fields instead of deleting rows.
6. **Migrations for all changes.** Never modify the schema manually.
7. **Backtest data is separate.** Backtest runs and trades are distinct from live/paper data; run-level metrics are stored on `backtest_runs` for the MVP.
8. **Broker identity is durable.** Client order IDs and broker order/fill IDs are unique where available.
9. **Secrets stay outside the database.** Broker credentials are server environment secrets and never persisted in Atlas tables.
