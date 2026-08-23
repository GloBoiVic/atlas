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


class ExperimentModel(Base):
    __tablename__ = "experiments"
    __table_args__ = (
        CheckConstraint("status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED')", name="valid_status"),
        CheckConstraint("trading_end > trading_start", name="valid_trading_range"),
        CheckConstraint("starting_capital > 0 AND starting_capital <> 'NaN'::numeric", name="positive_starting_capital"),
        CheckConstraint("risk_per_trade > 0 AND risk_per_trade < 1 AND risk_per_trade <> 'NaN'::numeric", name="valid_risk_per_trade"),
        CheckConstraint("(status IN ('PENDING', 'RUNNING') AND completed_at IS NULL) OR (status IN ('COMPLETED', 'FAILED') AND completed_at IS NOT NULL)", name="status_completion_consistency"),
        CheckConstraint("failure_category IS NULL OR failure_category IN ('VALIDATION', 'MARKET_DATA', 'STRATEGY', 'RISK', 'EXECUTION', 'PERSISTENCE')", name="valid_failure_category"),
        CheckConstraint("failure_code IS NULL OR failure_code ~ '^[A-Z0-9_]+$'", name="sanitized_failure_code"),
        CheckConstraint("failure_detail IS NULL OR (length(failure_detail) BETWEEN 1 AND 500 AND failure_detail !~ '[[:cntrl:]]')", name="sanitized_failure_detail"),
        CheckConstraint("(status = 'FAILED' AND failure_category IS NOT NULL AND failure_code IS NOT NULL AND failure_detail IS NOT NULL) OR (status <> 'FAILED' AND failure_category IS NULL AND failure_code IS NULL AND failure_detail IS NULL)", name="failure_consistency"),
        Index("ix_experiments_created_at_id_desc", text("created_at DESC"), text("id DESC")),
    )
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    strategy_version_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("strategy_versions.id", ondelete="RESTRICT"), nullable=False)
    dataset_snapshot_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("dataset_snapshots.id", ondelete="RESTRICT"), nullable=False)
    venue_instrument_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("venue_instruments.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'PENDING'"))
    trading_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    trading_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    starting_capital: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    risk_per_trade: Mapped[Decimal] = mapped_column(Numeric(12, 10), nullable=False)
    parameter_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    risk_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    simulation_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_category: Mapped[str | None] = mapped_column(String(20), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    failure_detail: Mapped[str | None] = mapped_column(String(500), nullable=True)


class ExperimentAccountModel(Base):
    __tablename__ = "experiment_accounts"
    __table_args__ = (
        CheckConstraint("base_currency = 'USD'", name="phase_3_base_currency"),
        CheckConstraint("starting_capital > 0 AND starting_capital <> 'NaN'::numeric", name="positive_starting_capital"),
        CheckConstraint("realized_pnl <> 'NaN'::numeric AND unrealized_pnl <> 'NaN'::numeric AND equity <> 'NaN'::numeric", name="finite_account_values"),
    )
    experiment_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("experiments.id", ondelete="RESTRICT"), primary_key=True)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default=text("'USD'"))
    starting_capital: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False, server_default=text("0"))
    unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False, server_default=text("0"))
    equity: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class TradeIntentModel(Base):
    __tablename__ = "trade_intents"
    __table_args__ = (
        CheckConstraint("action IN ('OPEN_LONG', 'OPEN_SHORT', 'CLOSE_POSITION', 'UPDATE_PROTECTION')", name="valid_action"),
        CheckConstraint("direction IS NULL OR direction IN ('LONG', 'SHORT')", name="valid_direction"),
        CheckConstraint("proposed_stop IS NULL OR (proposed_stop > 0 AND proposed_stop <> 'NaN'::numeric)", name="positive_stop"),
        UniqueConstraint("experiment_id", "decision_frontier", name="uq_trade_intents_experiment_frontier"),
    )
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    experiment_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("experiments.id", ondelete="RESTRICT"), nullable=False)
    strategy_version_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("strategy_versions.id", ondelete="RESTRICT"), nullable=False)
    venue_instrument_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("venue_instruments.id", ondelete="RESTRICT"), nullable=False)
    decision_frontier: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    direction: Mapped[str | None] = mapped_column(String(5), nullable=True)
    proposed_stop: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    target_multiple: Mapped[Decimal | None] = mapped_column(Numeric(12, 10), nullable=True)
    rationale: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class RiskDecisionModel(Base):
    __tablename__ = "risk_decisions"
    __table_args__ = (
        CheckConstraint("phase IN ('PRE_FLIGHT', 'PRE_SUBMISSION')", name="valid_phase"),
        CheckConstraint("outcome IN ('APPROVED', 'REJECTED')", name="valid_outcome"),
        CheckConstraint("quantity IS NULL OR (quantity > 0 AND quantity <> 'NaN'::numeric)", name="positive_quantity"),
        CheckConstraint("actual_risk IS NULL OR (actual_risk >= 0 AND actual_risk <> 'NaN'::numeric)", name="phase_4_actual_risk"),
        UniqueConstraint("trade_intent_id", "phase", name="uq_risk_decisions_intent_phase"),
    )
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    trade_intent_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("trade_intents.id", ondelete="RESTRICT"), nullable=False)
    phase: Mapped[str] = mapped_column(String(20), nullable=False)
    outcome: Mapped[str] = mapped_column(String(10), nullable=False)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(24, 10), nullable=True)
    entry_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    stop_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    target_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    risk_budget: Mapped[Decimal | None] = mapped_column(Numeric(24, 10), nullable=True)
    quote_bid: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    quote_ask: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    rejection_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    actual_risk: Mapped[Decimal | None] = mapped_column(Numeric(24, 10), nullable=True)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OrderModel(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("order_type IN ('MARKET', 'STOP', 'LIMIT')", name="valid_order_type"),
        CheckConstraint("purpose IN ('ENTRY', 'EXIT', 'STOP_LOSS', 'TAKE_PROFIT', 'PROTECTION_UPDATE')", name="valid_purpose"),
        CheckConstraint("current_status IN ('PENDING_SUBMISSION', 'SUBMITTED', 'FILLED', 'CANCELED', 'REJECTED', 'EXPIRED', 'UNKNOWN')", name="valid_status"),
        CheckConstraint("quantity > 0 AND quantity <> 'NaN'::numeric", name="positive_quantity"),
        UniqueConstraint("client_correlation_id", name="uq_orders_client_correlation_id"),
        UniqueConstraint("parent_entry_order_id", "purpose", name="uq_orders_parent_purpose"),
    )
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    experiment_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("experiments.id", ondelete="RESTRICT"), nullable=False)
    trade_intent_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("trade_intents.id", ondelete="RESTRICT"), nullable=False)
    risk_decision_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("risk_decisions.id", ondelete="RESTRICT"), nullable=False)
    order_type: Mapped[str] = mapped_column(String(10), nullable=False)
    purpose: Mapped[str] = mapped_column(String(25), nullable=False)
    direction: Mapped[str] = mapped_column(String(5), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    requested_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    current_status: Mapped[str] = mapped_column(String(25), nullable=False, server_default=text("'PENDING_SUBMISSION'"))
    client_correlation_id: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    parent_entry_order_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("orders.id", ondelete="RESTRICT"), nullable=True
    )


class FillModel(Base):
    __tablename__ = "fills"
    __table_args__ = (
        CheckConstraint("sequence_number > 0", name="positive_sequence"),
        CheckConstraint("quantity > 0 AND quantity <> 'NaN'::numeric AND execution_price > 0 AND execution_price <> 'NaN'::numeric", name="positive_financials"),
        UniqueConstraint("order_id", "sequence_number", name="uq_fills_order_sequence"),
        UniqueConstraint("external_execution_id", name="uq_fills_external_execution_id"),
        CheckConstraint("price_basis IS NULL OR price_basis IN ('OPEN', 'OPEN_GAP', 'INTRABAR_STOP', 'INTRABAR_TARGET', 'END_CLOSE')", name="phase_4_price_basis"),
    )
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    order_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False)
    sequence_number: Mapped[int] = mapped_column(nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    execution_price: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    external_execution_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    fee: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False, server_default=text("0"))
    source_market_bar_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("market_bars.id", ondelete="RESTRICT"), nullable=True
    )
    price_basis: Mapped[str | None] = mapped_column(String(20), nullable=True)
    executable_reference_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    slippage_per_unit: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    slippage_cost: Mapped[Decimal | None] = mapped_column(Numeric(24, 10), nullable=True)


class PositionModel(Base):
    __tablename__ = "positions"
    __table_args__ = (
        CheckConstraint("state IN ('FLAT', 'LONG', 'SHORT')", name="valid_state"),
        CheckConstraint("(state = 'FLAT' AND quantity IS NULL AND entry_price IS NULL AND opened_at IS NULL) OR (state IN ('LONG', 'SHORT') AND quantity > 0 AND entry_price > 0 AND opened_at IS NOT NULL)", name="state_exposure_consistency"),
        UniqueConstraint("experiment_id", "venue_instrument_id", name="uq_positions_experiment_instrument"),
    )
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    experiment_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("experiments.id", ondelete="RESTRICT"), nullable=False)
    venue_instrument_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("venue_instruments.id", ondelete="RESTRICT"), nullable=False)
    state: Mapped[str] = mapped_column(String(5), nullable=False, server_default=text("'FLAT'"))
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(24, 10), nullable=True)
    entry_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class TradeModel(Base):
    __tablename__ = "trades"
    __table_args__ = (
        CheckConstraint("direction IN ('LONG', 'SHORT')", name="valid_direction"),
        CheckConstraint("status IN ('OPEN', 'COMPLETED')", name="valid_status"),
        CheckConstraint("quantity > 0 AND quantity <> 'NaN'::numeric AND entry_price > 0 AND entry_price <> 'NaN'::numeric", name="positive_entry_financials"),
        CheckConstraint("status = 'OPEN' OR (exit_price IS NOT NULL AND closed_at IS NOT NULL AND gross_pnl IS NOT NULL)", name="completed_trade_facts"),
        CheckConstraint("exit_reason IS NULL OR exit_reason IN ('TAKE_PROFIT', 'STOP_LOSS', 'END_OF_EXPERIMENT')", name="phase_4_exit_reason"),
        CheckConstraint("financing_cost IS NULL OR financing_cost = 0", name="phase_4_financing_excluded"),
        UniqueConstraint("experiment_id", "sequence_number", name="uq_trades_experiment_sequence"),
    )
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    experiment_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("experiments.id", ondelete="RESTRICT"), nullable=False)
    trade_intent_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("trade_intents.id", ondelete="RESTRICT"), nullable=False)
    entry_order_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False)
    exit_order_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("orders.id", ondelete="RESTRICT"), nullable=True)
    sequence_number: Mapped[int] = mapped_column(nullable=False, server_default=text("1"))
    direction: Mapped[str] = mapped_column(String(5), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, server_default=text("'OPEN'"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    entry_price: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    exit_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    gross_pnl: Mapped[Decimal | None] = mapped_column(Numeric(24, 10), nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(String(30), nullable=True)
    initial_risk: Mapped[Decimal | None] = mapped_column(Numeric(24, 10), nullable=True)
    commission_cost: Mapped[Decimal | None] = mapped_column(Numeric(24, 10), nullable=True)
    financing_cost: Mapped[Decimal | None] = mapped_column(Numeric(24, 10), nullable=True)
    net_pnl: Mapped[Decimal | None] = mapped_column(Numeric(24, 10), nullable=True)
    r_multiple: Mapped[Decimal | None] = mapped_column(Numeric(24, 10), nullable=True)
    intrabar_ambiguous: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))
    ambiguity_policy: Mapped[str | None] = mapped_column(String(80), nullable=True)
    ambiguity_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ambiguity_source_market_bar_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("market_bars.id", ondelete="RESTRICT"), nullable=True
    )


class OrderEventModel(Base):
    __tablename__ = "order_events"
    __table_args__ = (
        CheckConstraint("sequence_number > 0", name="positive_sequence"),
        CheckConstraint("event_type IN ('ORDER_CREATED', 'ORDER_SUBMITTED', 'ORDER_FILLED', 'ORDER_CANCELED')", name="valid_event_type"),
        UniqueConstraint("order_id", "sequence_number", name="uq_order_events_order_sequence"),
    )
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    order_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False)
    sequence_number: Mapped[int] = mapped_column(nullable=False)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_market_bar_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("market_bars.id", ondelete="RESTRICT"), nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))


class ExperimentEquityPointModel(Base):
    __tablename__ = "experiment_equity_points"
    __table_args__ = (
        PrimaryKeyConstraint("experiment_id", "sequence_number"),
        UniqueConstraint("experiment_id", "observed_at", name="uq_equity_points_experiment_time"),
    )
    experiment_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("experiments.id", ondelete="RESTRICT"), nullable=False)
    sequence_number: Mapped[int] = mapped_column(nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    balance: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    equity: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    running_peak: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    drawdown_amount: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    drawdown_percent: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    valuation_bid: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    valuation_ask: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    source_bid_market_bar_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("market_bars.id", ondelete="RESTRICT"), nullable=True)
    source_ask_market_bar_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("market_bars.id", ondelete="RESTRICT"), nullable=True)


class ExperimentResultModel(Base):
    __tablename__ = "experiment_results"
    __table_args__ = (
        CheckConstraint("output_fingerprint ~ '^[0-9a-f]{64}$'", name="sha256_output_fingerprint"),
        CheckConstraint("financing_cost IS NULL OR financing_cost = 0", name="financing_excluded"),
        CheckConstraint("sharpe_ratio IS NULL OR (sharpe_ratio <> 'NaN'::numeric AND sharpe_ratio <> 'Infinity'::numeric AND sharpe_ratio <> '-Infinity'::numeric)", name="result_sharpe_ratio_finite"),
        CheckConstraint("profit_factor IS NULL OR (profit_factor <> 'NaN'::numeric AND profit_factor <> 'Infinity'::numeric AND profit_factor <> '-Infinity'::numeric)", name="result_profit_factor_finite"),
        CheckConstraint("win_rate IS NULL OR (win_rate <> 'NaN'::numeric AND win_rate <> 'Infinity'::numeric AND win_rate <> '-Infinity'::numeric)", name="result_win_rate_finite"),
        CheckConstraint("expectancy_net_pnl IS NULL OR (expectancy_net_pnl <> 'NaN'::numeric AND expectancy_net_pnl <> 'Infinity'::numeric AND expectancy_net_pnl <> '-Infinity'::numeric)", name="result_expectancy_net_pnl_finite"),
        CheckConstraint("jsonb_typeof(metric_states) = 'object' AND metric_states ?& ARRAY['sharpe_ratio', 'profit_factor', 'win_rate', 'expectancy_net_pnl'] AND (metric_states->>'sharpe_ratio') IN ('VALUE', 'INFINITE', 'UNAVAILABLE', 'LEGACY_UNCOMPUTED') AND (metric_states->>'profit_factor') IN ('VALUE', 'INFINITE', 'UNAVAILABLE', 'LEGACY_UNCOMPUTED') AND (metric_states->>'win_rate') IN ('VALUE', 'INFINITE', 'UNAVAILABLE', 'LEGACY_UNCOMPUTED') AND (metric_states->>'expectancy_net_pnl') IN ('VALUE', 'INFINITE', 'UNAVAILABLE', 'LEGACY_UNCOMPUTED')", name="result_metric_state_keys"),
        CheckConstraint("(metric_states->>'profit_factor' = 'INFINITE' AND profit_factor IS NULL) OR (metric_states->>'profit_factor' <> 'INFINITE')", name="result_metric_state_consistency"),
        CheckConstraint("result_schema_version NOT LIKE 'PHASE5_%' OR metric_schema_version <> 'LEGACY_UNCOMPUTED'", name="result_phase5_metric_schema"),
        CheckConstraint("profit_factor IS NULL OR profit_factor >= 0", name="result_profit_factor_nonnegative"),
        CheckConstraint("win_rate IS NULL OR (win_rate >= 0 AND win_rate <= 1)", name="result_win_rate_range"),
    )
    experiment_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("experiments.id", ondelete="RESTRICT"), primary_key=True)
    result_schema_version: Mapped[str] = mapped_column(String(100), nullable=False)
    trade_count: Mapped[int] = mapped_column(nullable=False)
    ambiguous_trade_count: Mapped[int] = mapped_column(nullable=False)
    gross_pnl: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    commission_cost: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    financing_cost: Mapped[Decimal | None] = mapped_column(Numeric(24, 10), nullable=True)
    modeled_net_pnl: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    ending_balance: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    ending_equity: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    net_return: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    max_drawdown_amount: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    max_drawdown_percent: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    financing_disclosure: Mapped[str] = mapped_column(String(100), nullable=False)
    completed_market_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    output_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    sharpe_ratio: Mapped[Decimal | None] = mapped_column(Numeric(24, 10), nullable=True)
    profit_factor: Mapped[Decimal | None] = mapped_column(Numeric(24, 10), nullable=True)
    win_rate: Mapped[Decimal | None] = mapped_column(Numeric(24, 10), nullable=True)
    expectancy_net_pnl: Mapped[Decimal | None] = mapped_column(Numeric(24, 10), nullable=True)
    metric_states: Mapped[dict[str, str]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{\"sharpe_ratio\": \"LEGACY_UNCOMPUTED\", \"profit_factor\": \"LEGACY_UNCOMPUTED\", \"win_rate\": \"LEGACY_UNCOMPUTED\", \"expectancy_net_pnl\": \"LEGACY_UNCOMPUTED\"}'::jsonb"),
    )
    metric_schema_version: Mapped[str] = mapped_column(
        String(100), nullable=False, server_default=text("'LEGACY_UNCOMPUTED'")
    )
