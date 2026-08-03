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
