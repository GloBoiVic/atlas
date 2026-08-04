from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.account_mode import AccountMode
from backend.persistence.database import Base


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    broker: Mapped[str] = mapped_column(String(50), nullable=False)
    mode: Mapped[AccountMode] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class Strategy(Base):
    __tablename__ = "strategies"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    entrypoint: Mapped[str] = mapped_column(String(500), nullable=False)
    repository: Mapped[str] = mapped_column(String(500), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False, default="1.0.0")
    commit_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    parameters: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=True, default=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class StrategyVersion(Base):
    __tablename__ = "strategy_versions"
    __table_args__ = (UniqueConstraint("strategy_id", "commit_sha"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    strategy_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("strategies.id"), nullable=False
    )
    repository: Mapped[str] = mapped_column(String(500), nullable=False)
    commit_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    parameters: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    deployed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


class Bot(Base):
    __tablename__ = "bots"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    strategy_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("strategies.id"), nullable=True
    )
    strategy_version_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("strategy_versions.id"), nullable=True
    )
    account_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("accounts.id"), nullable=False
    )
    broker: Mapped[str] = mapped_column(String(50), nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    instrument: Mapped[str] = mapped_column(String(50), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    desired_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="stopped"
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="stopped")
    pnl: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 8), nullable=True, default=Decimal("0"), server_default=text("0")
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class ReconciliationRun(Base):
    __tablename__ = "reconciliation_runs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("accounts.id"), nullable=False
    )
    bot_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("bots.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    broker_snapshot: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    differences: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class Instrument(Base):
    """Provider-aware instrument reference table.

    Uniqueness is scoped to ``(symbol, provider)``.  Provider-specific constraints
    are stored as JSONB metadata rather than flattened into shared columns.
    """

    __tablename__ = "instruments"
    __table_args__ = (UniqueConstraint("symbol", "provider"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(20), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    base_currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    quote_currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    price_precision: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_precision: Mapped[int] = mapped_column(Integer, nullable=False)
    constraints: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=True, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class Candle(Base):
    """Historical and streaming OHLC candle table.

    Uniqueness is ``(instrument_id, provider, timeframe, open_time, price_basis)``
    so that OANDA can store multiple price bases for the same interval.
    Volume semantics are explicit: ``base_volume`` vs ``tick_volume`` are not
    interchangeable.
    """

    __tablename__ = "candles"
    __table_args__ = (
        UniqueConstraint(
            "instrument_id", "provider", "timeframe", "open_time", "price_basis"
        ),
        Index(
            "idx_candles_lookup",
            "instrument_id",
            "provider",
            "timeframe",
            "open_time",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    instrument_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("instruments.id"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    open_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    close_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    price_basis: Mapped[str] = mapped_column(
        String(10), nullable=False, default="trade"
    )
    open: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    base_volume: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), nullable=False, default=Decimal("0")
    )
    quote_volume: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    trade_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    taker_buy_base_volume: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 8), nullable=True
    )
    taker_buy_quote_volume: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 8), nullable=True
    )
    tick_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    is_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class ExecutionOrder(Base):
    """Durable market order state and all broker idempotency keys."""

    __tablename__ = "orders"
    __table_args__ = (Index("idx_orders_status", "status"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("accounts.id"), nullable=False
    )
    bot_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("bots.id"))
    strategy_version_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("strategy_versions.id")
    )
    instrument_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("instruments.id"), nullable=False
    )
    client_order_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    broker_order_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(28, 12), nullable=False)
    order_type: Mapped[str] = mapped_column(String(20), nullable=False)
    stop_loss: Mapped[Decimal] = mapped_column(
        Numeric(28, 12), nullable=False, default=Decimal("0")
    )
    take_profit: Mapped[Decimal] = mapped_column(
        Numeric(28, 12), nullable=False, default=Decimal("0")
    )
    reduce_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    leverage: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, default=Decimal("1"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    filled_quantity: Mapped[Decimal] = mapped_column(
        Numeric(28, 12), nullable=False, default=Decimal("0")
    )
    average_fill_price: Mapped[Decimal | None] = mapped_column(Numeric(28, 12))
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class ExecutionFill(Base):
    """Append-only fill fact; broker execution IDs are globally idempotent."""

    __tablename__ = "fills"
    __table_args__ = (
        Index(
            "idx_fills_broker_execution",
            "broker_fill_id",
            unique=True,
            postgresql_where=text("broker_fill_id IS NOT NULL"),
            sqlite_where=text("broker_fill_id IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("orders.id"), nullable=False)
    account_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("accounts.id"), nullable=False
    )
    instrument_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("instruments.id"), nullable=False
    )
    broker_fill_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(28, 12), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(28, 12), nullable=False)
    fee: Mapped[Decimal] = mapped_column(
        Numeric(28, 12), nullable=False, default=Decimal("0")
    )
    filled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ExecutionPosition(Base):
    """One active one-way isolated position per account/instrument/mode."""

    __tablename__ = "positions"
    __table_args__ = (
        Index(
            "idx_one_active_net_position",
            "account_id",
            "instrument_id",
            "mode",
            unique=True,
            postgresql_where=text("status IN ('open', 'reducing')"),
            sqlite_where=text("status IN ('open', 'reducing')"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("accounts.id"), nullable=False
    )
    bot_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("bots.id"))
    strategy_version_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("strategy_versions.id")
    )
    instrument_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("instruments.id"), nullable=False
    )
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(28, 12), nullable=False)
    entry_price: Mapped[Decimal] = mapped_column(Numeric(28, 12), nullable=False)
    current_price: Mapped[Decimal | None] = mapped_column(Numeric(28, 12))
    stop_loss: Mapped[Decimal | None] = mapped_column(Numeric(28, 12))
    take_profit: Mapped[Decimal | None] = mapped_column(Numeric(28, 12))
    unrealized_pnl: Mapped[Decimal] = mapped_column(
        Numeric(28, 12), nullable=False, default=Decimal("0")
    )
    realized_pnl: Mapped[Decimal] = mapped_column(
        Numeric(28, 12), nullable=False, default=Decimal("0")
    )
    leverage: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, default=Decimal("1"))
    isolated_margin: Mapped[Decimal] = mapped_column(
        Numeric(28, 12), nullable=False, default=Decimal("0")
    )
    maintenance_margin: Mapped[Decimal] = mapped_column(
        Numeric(28, 12), nullable=False, default=Decimal("0")
    )
    liquidation_price: Mapped[Decimal | None] = mapped_column(Numeric(28, 12))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ExecutionTrade(Base):
    """Position lifecycle aggregate used by journal and analytics."""

    __tablename__ = "trades"
    __table_args__ = (Index("idx_trades_status", "status"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("accounts.id"), nullable=False
    )
    bot_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("bots.id"))
    strategy_version_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("strategy_versions.id")
    )
    position_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("positions.id"), nullable=False
    )
    instrument_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("instruments.id"), nullable=False
    )
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    entry_price: Mapped[Decimal] = mapped_column(Numeric(28, 12), nullable=False)
    exit_price: Mapped[Decimal | None] = mapped_column(Numeric(28, 12))
    quantity: Mapped[Decimal] = mapped_column(Numeric(28, 12), nullable=False)
    gross_pnl: Mapped[Decimal | None] = mapped_column(Numeric(28, 12))
    net_pnl: Mapped[Decimal | None] = mapped_column(Numeric(28, 12))
    total_fees: Mapped[Decimal] = mapped_column(
        Numeric(28, 12), nullable=False, default=Decimal("0")
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="entered")
    signal_metadata: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    market_context: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    entry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    exit_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# Persistence names remain explicit internally to avoid confusing ORM rows with the
# immutable execution-domain contracts; these aliases provide the conventional public names.
Order = ExecutionOrder
Fill = ExecutionFill
Position = ExecutionPosition
Trade = ExecutionTrade
