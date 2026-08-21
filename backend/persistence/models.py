"""SQLAlchemy persistence models for Atlas durable domain facts."""

# fmt: off
# ruff: noqa: E501

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    PrimaryKeyConstraint,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class StrategyModel(Base):
    __tablename__ = "strategies"

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    strategy_key: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(2000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    versions: Mapped[list["StrategyVersionModel"]] = relationship(
        back_populates="strategy", passive_deletes=True
    )


class StrategyVersionModel(Base):
    __tablename__ = "strategy_versions"
    __table_args__ = (
        CheckConstraint("version_number > 0", name="positive_version_number"),
        CheckConstraint(
            "source_fingerprint ~ '^[0-9a-f]{64}$'", name="sha256_fingerprint"
        ),
        UniqueConstraint(
            "strategy_id", "version_number", name="uq_strategy_versions_strategy_id"
        ),
        UniqueConstraint(
            "strategy_id",
            "source_fingerprint",
            name="uq_strategy_versions_strategy_id_source_fingerprint",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    strategy_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("strategies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(nullable=False)
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    implementation_key: Mapped[str] = mapped_column(String(200), nullable=False)
    parameter_schema: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False
    )
    context_timeframes: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    capabilities: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    source_manifest: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    exact_source_snapshot: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False)
    primary_timeframe: Mapped[str] = mapped_column(String(20), nullable=False)
    warm_up_bars: Mapped[int] = mapped_column(nullable=False)
    state_schema_version: Mapped[int] = mapped_column(nullable=False)
    git_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    strategy: Mapped[StrategyModel] = relationship(back_populates="versions")


class InstrumentModel(Base):
    __tablename__ = "instruments"
    __table_args__ = (
        CheckConstraint("code = 'EUR/USD'", name="phase_2_code"),
        CheckConstraint("base_currency = 'EUR'", name="phase_2_base_currency"),
        CheckConstraint("quote_currency = 'USD'", name="phase_2_quote_currency"),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    quote_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class VenueInstrumentModel(Base):
    __tablename__ = "venue_instruments"
    __table_args__ = (
        CheckConstraint("provider = 'OANDA'", name="phase_2_provider"),
        CheckConstraint("provider_symbol = 'EUR_USD'", name="phase_2_provider_symbol"),
        UniqueConstraint("provider", "provider_symbol"),
        UniqueConstraint("instrument_id", "provider"),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    instrument_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("instruments.id", ondelete="RESTRICT"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class MarketBarModel(Base):
    __tablename__ = "market_bars"
    __table_args__ = (
        CheckConstraint("resolution = 'M1'", name="m1_only"),
        CheckConstraint("price_component IN ('ASK', 'BID', 'MID')", name="valid_component"),
        CheckConstraint("start_time = date_trunc('minute', start_time)", name="minute_aligned_start"),
        CheckConstraint("end_time = start_time + interval '1 minute'", name="exact_one_minute"),
        CheckConstraint("complete IS TRUE", name="completed_only"),
        CheckConstraint("open_price > 0 AND high_price > 0 AND low_price > 0 AND close_price > 0", name="positive_prices"),
        CheckConstraint("open_price <> 'NaN'::numeric AND high_price <> 'NaN'::numeric AND low_price <> 'NaN'::numeric AND close_price <> 'NaN'::numeric", name="finite_prices"),
        CheckConstraint("low_price <= open_price AND low_price <= close_price AND high_price >= open_price AND high_price >= close_price", name="ohlc_containment"),
        CheckConstraint("volume IS NULL OR (volume >= 0 AND volume <> 'NaN'::numeric)", name="non_negative_volume"),
        CheckConstraint("content_fingerprint ~ '^[0-9a-f]{64}$'", name="sha256_fingerprint"),
        CheckConstraint("source_request_id IS NULL OR source_request_id !~ '[[:cntrl:]]'", name="sanitized_request_id"),
        UniqueConstraint("venue_instrument_id", "resolution", "price_component", "start_time", "content_fingerprint"),
        Index("uq_market_bars_current", "venue_instrument_id", "resolution", "price_component", "start_time", unique=True, postgresql_where=text("is_current")),
        Index("ix_market_bars_current_range", "venue_instrument_id", "resolution", "price_component", "start_time", postgresql_where=text("is_current")),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    venue_instrument_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("venue_instruments.id", ondelete="RESTRICT"), nullable=False
    )
    resolution: Mapped[str] = mapped_column(String(3), nullable=False)
    price_component: Mapped[str] = mapped_column(String(3), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    open_price: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    high_price: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    low_price: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    close_price: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    volume: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    complete: Mapped[bool] = mapped_column(nullable=False, server_default=text("true"))
    content_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    source_request_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_current: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))


class DatasetSnapshotModel(Base):
    __tablename__ = "dataset_snapshots"
    __table_args__ = (
        CheckConstraint("base_resolution = 'M1'", name="base_resolution_m1"),
        CheckConstraint("components = '[\"ASK\",\"BID\",\"MID\"]'::jsonb", name="fixed_components"),
        CheckConstraint("alignment_convention = 'UTC_HALF_OPEN_V1'", name="alignment_v1"),
        CheckConstraint("session_policy = 'OANDA_FX_NY_V1'", name="session_policy_v1"),
        CheckConstraint("fingerprint_schema = 'ATLAS_DATASET_SHA256_V1'", name="fingerprint_schema_v1"),
        CheckConstraint("coverage_start = date_trunc('minute', coverage_start) AND coverage_end = date_trunc('minute', coverage_end) AND coverage_end > coverage_start", name="valid_coverage_range"),
        CheckConstraint("fingerprint ~ '^[0-9a-f]{64}$'", name="sha256_fingerprint"),
        CheckConstraint("jsonb_typeof(integrity_summary) = 'object' AND integrity_summary ?& ARRAY['status','expected_open_minutes','expected_closure_minutes','member_minutes','bar_count','unexpected_gap_count','unexpected_observation_count','session_policy'] AND integrity_summary->>'status' = 'VALID' AND integrity_summary->>'session_policy' = 'OANDA_FX_NY_V1'", name="valid_integrity_summary"),
        UniqueConstraint("fingerprint"),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    venue_instrument_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("venue_instruments.id", ondelete="RESTRICT"), nullable=False
    )
    base_resolution: Mapped[str] = mapped_column(String(3), nullable=False)
    components: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    coverage_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    coverage_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    alignment_convention: Mapped[str] = mapped_column(String(30), nullable=False)
    session_policy: Mapped[str] = mapped_column(String(30), nullable=False)
    fingerprint_schema: Mapped[str] = mapped_column(String(40), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    integrity_summary: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class DatasetSnapshotBarModel(Base):
    __tablename__ = "dataset_snapshot_bars"
    __table_args__ = (PrimaryKeyConstraint("dataset_snapshot_id", "market_bar_id"),)

    dataset_snapshot_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("dataset_snapshots.id", ondelete="RESTRICT"), nullable=False
    )
    market_bar_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("market_bars.id", ondelete="RESTRICT"), nullable=False
    )
