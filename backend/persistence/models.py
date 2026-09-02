"""SQLAlchemy persistence models for Atlas durable domain facts."""

# fmt: off
# ruff: noqa: E501

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
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
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym
from sqlalchemy.sql.naming import conv

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
    required_historical_context_bars: Mapped[int] = mapped_column(nullable=False)
    # Transitional read alias for older runtime callers; the database column
    # and canonical persistence contract use required_historical_context_bars.
    warm_up_bars = synonym("required_historical_context_bars")
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
        CheckConstraint("resolution IN ('M1', 'M15')", name="supported_resolution"),
        CheckConstraint("price_component IN ('ASK', 'BID', 'MID')", name="valid_component"),
        CheckConstraint("start_time = date_trunc('minute', start_time) AND (resolution = 'M1' OR extract(minute from start_time)::integer % 15 = 0)", name="native_aligned_start"),
        CheckConstraint("(resolution = 'M1' AND end_time = start_time + interval '1 minute') OR (resolution = 'M15' AND end_time = start_time + interval '15 minutes')", name="exact_native_interval"),
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
        CheckConstraint("(snapshot_schema = 'ATLAS_HISTORICAL_SNAPSHOT_V1' AND base_resolution = 'M1') OR (snapshot_schema = 'ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2' AND base_resolution = 'M15')", name="snapshot_resolution_by_schema"),
        CheckConstraint("(snapshot_schema = 'ATLAS_HISTORICAL_SNAPSHOT_V1' AND components = '[\"ASK\",\"BID\",\"MID\"]'::jsonb) OR (snapshot_schema = 'ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2' AND components = '[\"MID\"]'::jsonb)", name="components_by_schema"),
        CheckConstraint("alignment_convention = 'UTC_HALF_OPEN_V1'", name="alignment_v1"),
        CheckConstraint("session_policy IN ('OANDA_FX_NY_V1', 'OANDA_FX_NY_V2')", name="session_policy_v1"),
        CheckConstraint("(snapshot_schema = 'ATLAS_HISTORICAL_SNAPSHOT_V1' AND fingerprint_schema = 'ATLAS_DATASET_SHA256_V1') OR (snapshot_schema = 'ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2' AND fingerprint_schema = 'ATLAS_DATASET_SHA256_V2')", name="fingerprint_schema_by_snapshot"),
        CheckConstraint("coverage_start = date_trunc('minute', coverage_start) AND coverage_end = date_trunc('minute', coverage_end) AND coverage_end > coverage_start", name="valid_coverage_range"),
        CheckConstraint("fingerprint ~ '^[0-9a-f]{64}$'", name="sha256_fingerprint"),
        CheckConstraint("jsonb_typeof(integrity_summary) = 'object' AND integrity_summary->>'status' = 'VALID' AND ((snapshot_schema = 'ATLAS_HISTORICAL_SNAPSHOT_V1' AND integrity_summary ?& ARRAY['expected_open_minutes','expected_closure_minutes','member_minutes','bar_count','unexpected_gap_count','unexpected_observation_count','session_policy'] AND integrity_summary->>'session_policy' IN ('OANDA_FX_NY_V1', 'OANDA_FX_NY_V2')) OR (snapshot_schema = 'ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2' AND integrity_summary->>'policy_version' = 'ATLAS_HISTORICAL_GAP_POLICY_V1'))", name="valid_integrity_summary"),
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
    snapshot_schema: Mapped[str] = mapped_column(String(100), nullable=False, server_default=text("'ATLAS_HISTORICAL_SNAPSHOT_V1'"))
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


class DatasetSnapshotAnalyticalBarModel(Base):
    __tablename__ = "dataset_snapshot_analytical_bars"
    __table_args__ = (
        PrimaryKeyConstraint("dataset_snapshot_id", "sequence"),
        UniqueConstraint("dataset_snapshot_id", "start_time", "content_fingerprint"),
        CheckConstraint(
            "sequence > 0 AND resolution = 'M15' AND price_component = 'MID' "
            "AND complete IS TRUE AND end_time = start_time + interval '15 minutes' "
            "AND content_fingerprint ~ '^[0-9a-f]{64}$'",
            name="valid_analytical_member",
        ),
    )
    dataset_snapshot_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("dataset_snapshots.id", ondelete="RESTRICT"), nullable=False)
    sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolution: Mapped[str] = mapped_column(String(3), nullable=False, server_default=text("'M15'"))
    price_component: Mapped[str] = mapped_column(String(3), nullable=False, server_default=text("'MID'"))
    open_price: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    high_price: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    low_price: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    close_price: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    volume: Mapped[Decimal | None] = mapped_column(Numeric(20, 10))
    complete: Mapped[bool] = mapped_column(nullable=False)
    source_request_id: Mapped[str | None] = mapped_column(String(200))
    content_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DatasetSnapshotExecutionObservationModel(Base):
    __tablename__ = "dataset_snapshot_execution_observations"
    __table_args__ = (
        PrimaryKeyConstraint("dataset_snapshot_id", "sequence"),
        UniqueConstraint("dataset_snapshot_id", "market_bar_id"),
        CheckConstraint(
            "sequence > 0 AND price_component IN ('BID','ASK') "
            "AND end_time = start_time + interval '1 minute' "
            "AND observation_fingerprint ~ '^[0-9a-f]{64}$'",
            name=conv(
                "ck_dataset_snapshot_execution_observations_valid_execut_5670"
            ),
        ),
    )
    dataset_snapshot_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("dataset_snapshots.id", ondelete="RESTRICT"), nullable=False)
    sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    market_bar_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("market_bars.id", ondelete="RESTRICT"), nullable=False)
    price_component: Mapped[str] = mapped_column(String(3), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    observation_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)


class DatasetSnapshotGapModel(Base):
    __tablename__ = "dataset_snapshot_gaps"
    __table_args__ = (
        PrimaryKeyConstraint("dataset_snapshot_id", "sequence"),
        CheckConstraint(
            "sequence > 0 AND end_time > start_time AND resolution IN ('M1','M15') "
            "AND classification IN ('NON_BLOCKING','RESOLVABLE','BLOCKING','EXTENDED_OUTAGE') "
            "AND policy_version = 'ATLAS_HISTORICAL_GAP_POLICY_V1'",
            name="valid_snapshot_gap",
        ),
    )
    dataset_snapshot_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("dataset_snapshots.id", ondelete="RESTRICT"), nullable=False)
    sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    price_component: Mapped[str | None] = mapped_column(String(3))
    resolution: Mapped[str] = mapped_column(String(3), nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    reason: Mapped[str] = mapped_column(String(200), nullable=False)
    classification: Mapped[str] = mapped_column(String(30), nullable=False)
    affected_state: Mapped[str | None] = mapped_column(String(100))
    affected_event: Mapped[str | None] = mapped_column(String(100))
    policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    blocked: Mapped[bool] = mapped_column(nullable=False)


class HistoricalAcquisitionWindowModel(Base):
    """Durable provider coverage, independent of returned observations."""
    __tablename__ = "historical_acquisition_windows"
    __table_args__ = (
        PrimaryKeyConstraint("venue_instrument_id", "resolution", "components", "start_time", "end_time"),
        CheckConstraint("resolution IN ('M1','M15')", name="acquisition_resolution"),
        CheckConstraint("outcome IN ('SUCCESS_EMPTY_OR_SPARSE','PROVIDER_FAILURE','UNKNOWN_OUTCOME')", name="acquisition_outcome"),
        CheckConstraint("end_time > start_time", name="acquisition_range"),
    )
    venue_instrument_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("venue_instruments.id", ondelete="RESTRICT"), nullable=False)
    resolution: Mapped[str] = mapped_column(String(3), nullable=False)
    components: Mapped[str] = mapped_column(String(20), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    outcome: Mapped[str] = mapped_column(String(30), nullable=False)
    request_identity: Mapped[str] = mapped_column(String(64), nullable=False)
    returned_count: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class HistoricalDataLoadRequestModel(Base):
    __tablename__ = "historical_data_load_requests"
    __table_args__ = (
        CheckConstraint("operation = 'LOAD_MISSING'", name="load_operation"),
        CheckConstraint("status IN ('PENDING','RUNNING','COMPLETED','FAILED')", name="load_status"),
        CheckConstraint("trading_end > trading_start AND load_start <= trading_start AND load_end = trading_end", name="load_order"),
        CheckConstraint("extract(epoch from trading_start)::bigint % 900 = 0 AND extract(epoch from trading_end)::bigint % 900 = 0", name="trading_alignment"),
        CheckConstraint("extract(epoch from load_start)::bigint % 60 = 0 AND extract(epoch from load_end)::bigint % 60 = 0", name="load_alignment"),
        CheckConstraint("atlas_historical_ranges_valid(fetched_ranges) AND atlas_historical_ranges_valid(committed_ranges)", name="progress_arrays"),
        CheckConstraint("jsonb_typeof(coverage_summary) = 'object' OR coverage_summary IS NULL", name="coverage_object"),
        CheckConstraint("jsonb_typeof(experiment_validation) = 'object' OR experiment_validation IS NULL", name="validation_object"),
        CheckConstraint("inserted >= 0 AND reactivated >= 0 AND unchanged >= 0 AND incomplete_minute_count >= 0", name="nonnegative_counters"),
        CheckConstraint("failure_category IS NULL OR failure_category IN ('VALIDATION','MARKET_DATA','PERSISTENCE','RUNTIME')", name="load_failure_category"),
        CheckConstraint("failure_code IS NULL OR failure_code ~ '^[A-Z0-9_]+$'", name="load_failure_code"),
        CheckConstraint("failure_detail IS NULL OR (length(failure_detail) BETWEEN 1 AND 500 AND failure_detail !~ '[[:cntrl:]]')", name="load_failure_detail"),
        CheckConstraint("(status = 'PENDING' AND started_at IS NULL AND finished_at IS NULL AND failure_category IS NULL AND failure_code IS NULL AND failure_detail IS NULL AND snapshot_id IS NULL AND coverage_summary IS NULL AND experiment_validation IS NULL) OR (status = 'RUNNING' AND started_at IS NOT NULL AND finished_at IS NULL AND failure_category IS NULL AND failure_code IS NULL AND failure_detail IS NULL) OR (status = 'COMPLETED' AND started_at IS NOT NULL AND finished_at IS NOT NULL AND snapshot_id IS NOT NULL AND coverage_summary->>'valid' = 'true' AND experiment_validation->>'valid' = 'true' AND failure_category IS NULL AND failure_code IS NULL AND failure_detail IS NULL) OR (status = 'FAILED' AND finished_at IS NOT NULL AND failure_category IS NOT NULL AND failure_code IS NOT NULL AND failure_detail IS NOT NULL)", name="load_state_consistency"),
        Index("uq_historical_data_load_requests_active", text("(1)"), unique=True, postgresql_where=text("status IN ('PENDING','RUNNING')")),
        Index("ix_historical_data_load_requests_status", "status"),
        Index("ix_historical_data_load_requests_created_at_id_desc", text("created_at DESC"), text("id DESC")),
    )
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    operation: Mapped[str] = mapped_column(String(30), nullable=False, server_default=text("'LOAD_MISSING'"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'PENDING'"))
    strategy_version_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("strategy_versions.id", ondelete="RESTRICT"), nullable=False)
    trading_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    trading_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    load_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    load_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fetched_ranges: Mapped[list[dict[str, str]]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    committed_ranges: Mapped[list[dict[str, str]]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    inserted: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    reactivated: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    unchanged: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    incomplete_minute_count: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    coverage_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    experiment_validation: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    snapshot_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("dataset_snapshots.id", ondelete="RESTRICT"), nullable=True)
    failure_category: Mapped[str | None] = mapped_column(String(20), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    failure_detail: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


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


class ExperimentDeletionReceiptModel(Base):
    """Append-only identity receipt for a permanent Experiment deletion."""

    __tablename__ = "experiment_deletion_receipts"
    __table_args__ = (
        UniqueConstraint("deleted_experiment_id"),
        CheckConstraint(
            "strategy_source_fingerprint ~ '^[0-9a-f]{64}$'",
            name=conv(
                "ck_experiment_deletion_receipts_sha256_strategy_source__74ef"
            ),
        ),
        CheckConstraint(
            "pre_delete_status IN ('PENDING', 'FAILED', 'COMPLETED')",
            name="deletable_pre_delete_status",
        ),
        CheckConstraint(
            "confirmation_schema_version <> ''",
            name=conv(
                "ck_experiment_deletion_receipts_confirmation_schema_ver_1fd5"
            ),
        ),
    )

    receipt_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    deleted_experiment_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    pre_delete_status: Mapped[str] = mapped_column(String(20), nullable=False)
    strategy_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    strategy_version_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    strategy_source_fingerprint: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    instrument: Mapped[str] = mapped_column(String(20), nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    trading_period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    trading_period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    deleted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    dataset_snapshot_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    snapshot_deleted: Mapped[bool] = mapped_column(nullable=False)
    confirmation_schema_version: Mapped[str] = mapped_column(
        String(100), nullable=False
    )


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
        CheckConstraint("entry_policy IN ('IMMEDIATE','PRICE_TRIGGERED')", name="valid_entry_policy"),
        CheckConstraint("(action IN ('OPEN_LONG','OPEN_SHORT') AND ((entry_policy = 'IMMEDIATE' AND trigger_price IS NULL AND trigger_price_basis IS NULL AND expiry_time IS NULL AND expiry_bars IS NULL) OR (entry_policy = 'PRICE_TRIGGERED' AND trigger_price IS NOT NULL AND trigger_price_basis IN ('ASK','BID') AND expiry_time IS NULL AND expiry_bars > 0))) OR (action NOT IN ('OPEN_LONG','OPEN_SHORT') AND entry_policy = 'IMMEDIATE' AND trigger_price IS NULL AND trigger_price_basis IS NULL AND expiry_time IS NULL AND expiry_bars IS NULL)", name="valid_action_entry_policy"),
        CheckConstraint("trigger_price_basis IS NULL OR trigger_price_basis IN ('ASK','BID')", name="valid_trigger_price_basis"),
        CheckConstraint("trigger_price IS NULL OR (trigger_price > 0 AND trigger_price <> 'NaN'::numeric)", name="valid_trigger_price"),
        CheckConstraint("proposal_status IN ('PENDING','FILLED','EXPIRED','REJECTED')", name="valid_proposal_status"),
        CheckConstraint("(entry_policy = 'IMMEDIATE' AND trigger_price IS NULL AND expiry_time IS NULL) OR (entry_policy = 'PRICE_TRIGGERED' AND trigger_price IS NOT NULL AND expiry_time IS NULL)", name="entry_policy_shape"),
        CheckConstraint("expiry_bars IS NULL OR expiry_bars > 0", name="positive_expiry_bars"),
        CheckConstraint("expiry_time IS NULL OR expiry_time > decision_frontier", name="expiry_after_decision"),
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
    entry_policy: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'IMMEDIATE'"))
    trigger_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    trigger_price_basis: Mapped[str | None] = mapped_column(String(3), nullable=True)
    # Retained immutable proposal compatibility columns; no migration or
    # removal is authorized while historical intents remain readable.
    expiry_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expiry_bars: Mapped[int | None] = mapped_column(nullable=True)
    proposal_status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'PENDING'"))
    diagnostics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class ExperimentProposalDiagnosticModel(Base):
    __tablename__ = "experiment_proposal_diagnostics"
    __table_args__ = (
        PrimaryKeyConstraint("experiment_id", "sequence"),
        CheckConstraint("sequence > 0 AND event_type IN ('FILLED','EXPIRED','REJECTED','EXECUTION_DATA_UNAVAILABLE')", name="valid_proposal_event"),
        CheckConstraint("jsonb_typeof(details) = 'object'", name="proposal_details_object"),
    )
    experiment_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("experiments.id", ondelete="RESTRICT"), nullable=False)
    sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    trade_intent_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("trade_intents.id", ondelete="RESTRICT"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


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
         CheckConstraint("jsonb_typeof(metric_states) = 'object' AND metric_states ?& ARRAY['net_return', 'max_drawdown_amount', 'max_drawdown_percent', 'sharpe_ratio', 'profit_factor', 'win_rate', 'expectancy_net_pnl'] AND (metric_states->'net_return'->>'state') IN ('VALUE', 'INFINITE', 'UNAVAILABLE', 'LEGACY_UNCOMPUTED') AND (metric_states->'max_drawdown_amount'->>'state') IN ('VALUE', 'INFINITE', 'UNAVAILABLE', 'LEGACY_UNCOMPUTED') AND (metric_states->'max_drawdown_percent'->>'state') IN ('VALUE', 'INFINITE', 'UNAVAILABLE', 'LEGACY_UNCOMPUTED') AND (metric_states->'sharpe_ratio'->>'state') IN ('VALUE', 'INFINITE', 'UNAVAILABLE', 'LEGACY_UNCOMPUTED') AND (metric_states->'profit_factor'->>'state') IN ('VALUE', 'INFINITE', 'UNAVAILABLE', 'LEGACY_UNCOMPUTED') AND (metric_states->'win_rate'->>'state') IN ('VALUE', 'INFINITE', 'UNAVAILABLE', 'LEGACY_UNCOMPUTED') AND (metric_states->'expectancy_net_pnl'->>'state') IN ('VALUE', 'INFINITE', 'UNAVAILABLE', 'LEGACY_UNCOMPUTED')", name="result_metric_state_keys"),
         CheckConstraint("(metric_states->'profit_factor'->>'state' = 'INFINITE' AND profit_factor IS NULL) OR (metric_states->'profit_factor'->>'state' <> 'INFINITE')", name="result_metric_state_consistency"),
        CheckConstraint("result_schema_version NOT LIKE 'PHASE5_%' OR metric_schema_version <> 'LEGACY_UNCOMPUTED'", name="result_phase5_metric_schema"),
        CheckConstraint("profit_factor IS NULL OR profit_factor >= 0", name="result_profit_factor_nonnegative"),
        CheckConstraint("win_rate IS NULL OR (win_rate >= 0 AND win_rate <= 1)", name="result_win_rate_range"),
        CheckConstraint("jsonb_typeof(result_quality) = 'object' AND result_quality->>'schema' = 'ATLAS_RESULT_QUALITY_V1' AND result_quality->>'value' IN ('DETERMINED','DEGRADED','DETERMINED_WITH_GAPS','CONSERVATIVE_AMBIGUITY_RESOLVED')", name="result_quality_values"),
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
    metric_states: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{\"net_return\": {\"state\": \"LEGACY_UNCOMPUTED\", \"reason\": \"LEGACY_RESULT\"}, \"max_drawdown_amount\": {\"state\": \"LEGACY_UNCOMPUTED\", \"reason\": \"LEGACY_RESULT\"}, \"max_drawdown_percent\": {\"state\": \"LEGACY_UNCOMPUTED\", \"reason\": \"LEGACY_RESULT\"}, \"sharpe_ratio\": {\"state\": \"LEGACY_UNCOMPUTED\", \"reason\": \"LEGACY_RESULT\"}, \"profit_factor\": {\"state\": \"LEGACY_UNCOMPUTED\", \"reason\": \"LEGACY_RESULT\"}, \"win_rate\": {\"state\": \"LEGACY_UNCOMPUTED\", \"reason\": \"LEGACY_RESULT\"}, \"expectancy_net_pnl\": {\"state\": \"LEGACY_UNCOMPUTED\", \"reason\": \"LEGACY_RESULT\"}}'::jsonb"),
    )
    metric_schema_version: Mapped[str] = mapped_column(
        String(100), nullable=False, server_default=text("'LEGACY_UNCOMPUTED'")
    )
    result_quality: Mapped[dict[str, str]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{\"schema\": \"ATLAS_RESULT_QUALITY_V1\", \"value\": \"DETERMINED\"}'::jsonb"),
    )


class ExperimentGapDecisionModel(Base):
    __tablename__ = "experiment_gap_decisions"
    __table_args__ = (
        PrimaryKeyConstraint("experiment_id", "sequence"),
        CheckConstraint("sequence > 0 AND end_time > start_time", name="gap_decision_interval"),
        CheckConstraint("resolution IN ('M1','M15') AND (price_component IS NULL OR price_component IN ('BID','ASK','MID'))", name="gap_decision_market_shape"),
        CheckConstraint("classification IN ('NON_BLOCKING','RESOLVABLE','BLOCKING','EXTENDED_OUTAGE')", name="gap_decision_classification"),
        CheckConstraint("policy_version = 'ATLAS_HISTORICAL_GAP_POLICY_V1' AND rule_version <> ''", name="gap_decision_policy_version"),
        CheckConstraint("jsonb_typeof(details) = 'object'", name="gap_decision_details_object"),
    )
    experiment_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("experiments.id", ondelete="RESTRICT"), nullable=False)
    sequence: Mapped[int] = mapped_column(nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolution: Mapped[str] = mapped_column(String(3), nullable=False)
    price_component: Mapped[str | None] = mapped_column(String(3))
    classification: Mapped[str] = mapped_column(String(30), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(100), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    affected_state: Mapped[str | None] = mapped_column(String(100))
    affected_event: Mapped[str | None] = mapped_column(String(100))
    blocked: Mapped[bool] = mapped_column(nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class PaperExecutionAttemptModel(Base):
    """PAPER broker-attempt evidence, separate from historical Experiments."""

    __tablename__ = "paper_execution_attempts"
    __table_args__ = (
        CheckConstraint("provider = 'OANDA'", name="paper_provider"),
        CheckConstraint("environment = 'PRACTICE'", name="paper_environment"),
        CheckConstraint("base_currency = 'USD'", name="paper_base_currency"),
        CheckConstraint("instrument = 'EUR_USD'", name="paper_instrument"),
        CheckConstraint("direction IN ('LONG', 'SHORT')", name="paper_direction"),
        CheckConstraint("strategy_version_number > 0", name="paper_version_positive"),
        CheckConstraint(
            "source_fingerprint ~ '^[0-9a-f]{64}$'", name="paper_source_fingerprint"
        ),
        CheckConstraint(
            "requested_quantity > 0 AND requested_quantity <> 'NaN'::numeric "
            "AND requested_quantity <> 'Infinity'::numeric "
            "AND requested_quantity <> '-Infinity'::numeric",
            name="paper_quantity_positive_finite",
        ),
        CheckConstraint(
            "approved_entry_price > 0 AND approved_entry_price <> 'NaN'::numeric "
            "AND approved_entry_price <> 'Infinity'::numeric "
            "AND approved_entry_price <> '-Infinity'::numeric",
            name="paper_entry_price_positive_finite",
        ),
        CheckConstraint(
            "stop_price > 0 AND stop_price <> 'NaN'::numeric "
            "AND stop_price <> 'Infinity'::numeric "
            "AND stop_price <> '-Infinity'::numeric",
            name="paper_stop_price_positive_finite",
        ),
        CheckConstraint(
            "display_precision >= 0 AND trade_units_precision >= 0",
            name="paper_precision_nonnegative",
        ),
        CheckConstraint(
            "(fill_broker_order_id IS NULL AND fill_transaction_id IS NULL "
            "AND fill_trade_id IS NULL AND fill_signed_units IS NULL "
            "AND fill_price IS NULL AND fill_executed_at IS NULL "
            "AND fill_actual_initial_risk IS NULL) OR "
             "(fill_broker_order_id IS NOT NULL AND fill_transaction_id IS NOT NULL "
             "AND fill_trade_id IS NOT NULL AND fill_signed_units IS NOT NULL "
             "AND fill_signed_units <> 0 AND fill_signed_units <> 'NaN'::numeric "
             "AND fill_signed_units <> 'Infinity'::numeric "
             "AND fill_signed_units <> '-Infinity'::numeric "
             "AND fill_price IS NOT NULL AND fill_price > 0 "
             "AND fill_price <> 'NaN'::numeric "
             "AND fill_price <> 'Infinity'::numeric "
             "AND fill_price <> '-Infinity'::numeric "
             "AND fill_executed_at IS NOT NULL "
             "AND fill_actual_initial_risk IS NOT NULL "
             "AND fill_actual_initial_risk >= 0 "
             "AND fill_actual_initial_risk <> 'NaN'::numeric "
             "AND fill_actual_initial_risk <> 'Infinity'::numeric "
             "AND fill_actual_initial_risk <> '-Infinity'::numeric)",
            name="paper_fill_all_or_none",
        ),
        CheckConstraint(
            "stop_loss_status IN ('CONFIRMED', 'REJECTED', 'UNKNOWN', 'NOT_ATTEMPTED')",
            name="paper_stop_status",
        ),
        CheckConstraint(
            "take_profit_status IN ('CONFIRMED', 'REJECTED', 'UNKNOWN', 'NOT_ATTEMPTED')",
            name="paper_take_profit_status",
        ),
        CheckConstraint(
            "execution_outcome IS NULL OR execution_outcome IN "
            "('FILLED_PROTECTED', 'FILLED_PROTECTION_INCOMPLETE', 'REJECTED', 'CANCELLED', 'UNKNOWN')",
            name="paper_execution_outcome",
        ),
        CheckConstraint(
            "execution_outcome NOT IN ('FILLED_PROTECTED', 'FILLED_PROTECTION_INCOMPLETE') "
            "OR fill_broker_order_id IS NOT NULL",
            name="paper_filled_outcome_requires_fill",
        ),
        CheckConstraint(
            "execution_outcome NOT IN ('REJECTED', 'CANCELLED', 'UNKNOWN') "
            "OR fill_broker_order_id IS NULL",
            name="paper_no_fill_outcome",
        ),
        CheckConstraint(
            "execution_outcome <> 'FILLED_PROTECTED' OR "
            "(stop_loss_status = 'CONFIRMED' AND take_profit_status = 'CONFIRMED' "
            "AND actual_target_price IS NOT NULL)",
            name="paper_protected_outcome",
        ),
        CheckConstraint(
            "actual_target_price IS NULL OR (actual_target_price > 0 "
            "AND actual_target_price <> 'NaN'::numeric "
            "AND actual_target_price <> 'Infinity'::numeric "
            "AND actual_target_price <> '-Infinity'::numeric)",
            name="paper_actual_target_positive_finite",
        ),
        CheckConstraint(
            "reconciliation_status IN ('NOT_RUN', 'CONSISTENT', 'UNRESOLVED', 'CONFLICT', 'LIFECYCLE_ADVANCED')",
            name="paper_reconciliation_status",
        ),
        CheckConstraint("projection_version >= 0", name="paper_projection_version"),
        UniqueConstraint("client_order_id", name="uq_paper_attempts_client_order"),
        UniqueConstraint("client_trade_id", name="uq_paper_attempts_client_trade"),
        UniqueConstraint("client_stop_loss_order_id", name="uq_paper_attempts_client_stop"),
        UniqueConstraint("client_take_profit_order_id", name="uq_paper_attempts_client_take_profit"),
        Index("ix_paper_execution_attempts_outcome", "execution_outcome"),
        Index("ix_paper_execution_attempts_reconciliation", "reconciliation_status"),
    )

    attempt_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True
    )
    strategy_version_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("strategy_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    strategy_key: Mapped[str] = mapped_column(String(200), nullable=False)
    strategy_version_number: Mapped[int] = mapped_column(nullable=False)
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    implementation_key: Mapped[str] = mapped_column(String(200), nullable=False)
    validated_parameter_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    strategy_evaluation_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    risk_authority_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    strategy_decision: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    pre_flight_risk_decision: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    pre_submission_risk_decision: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    environment: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_account_id: Mapped[str] = mapped_column(String(128), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    instrument: Mapped[str] = mapped_column(String(20), nullable=False)
    direction: Mapped[str] = mapped_column(String(5), nullable=False)
    requested_quantity: Mapped[Decimal] = mapped_column(Numeric(30, 10), nullable=False)
    approved_entry_price: Mapped[Decimal] = mapped_column(Numeric(30, 10), nullable=False)
    stop_price: Mapped[Decimal] = mapped_column(Numeric(30, 10), nullable=False)
    decision_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    pricing_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    account_transaction_id: Mapped[str] = mapped_column(String(64), nullable=False)
    instrument_transaction_id: Mapped[str] = mapped_column(String(64), nullable=False)
    display_precision: Mapped[int] = mapped_column(nullable=False)
    trade_units_precision: Mapped[int] = mapped_column(nullable=False)
    client_order_id: Mapped[str] = mapped_column(String(128), nullable=False)
    client_trade_id: Mapped[str] = mapped_column(String(128), nullable=False)
    client_stop_loss_order_id: Mapped[str] = mapped_column(String(128), nullable=False)
    client_take_profit_order_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    fill_broker_order_id: Mapped[str | None] = mapped_column(String(128))
    fill_transaction_id: Mapped[str | None] = mapped_column(String(64))
    fill_trade_id: Mapped[str | None] = mapped_column(String(128))
    fill_signed_units: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    fill_price: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    fill_executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fill_actual_initial_risk: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    actual_target_price: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    stop_loss_status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'NOT_ATTEMPTED'"))
    stop_loss_broker_order_id: Mapped[str | None] = mapped_column(String(128))
    stop_loss_client_order_id: Mapped[str | None] = mapped_column(String(128))
    stop_loss_price: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    stop_loss_provider_state: Mapped[str | None] = mapped_column(String(64))
    take_profit_status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'NOT_ATTEMPTED'"))
    take_profit_broker_order_id: Mapped[str | None] = mapped_column(String(128))
    take_profit_client_order_id: Mapped[str | None] = mapped_column(String(128))
    take_profit_price: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    take_profit_provider_state: Mapped[str | None] = mapped_column(String(64))
    execution_outcome: Mapped[str | None] = mapped_column(String(40))
    rejection_code: Mapped[str | None] = mapped_column(String(64))
    rejection_broker_order_id: Mapped[str | None] = mapped_column(String(128))
    rejection_transaction_id: Mapped[str | None] = mapped_column(String(64))
    uncertainty_code: Mapped[str | None] = mapped_column(String(64))
    reconciliation_status: Mapped[str] = mapped_column(String(24), nullable=False, server_default=text("'NOT_RUN'"))
    reconciliation_block_code: Mapped[str | None] = mapped_column(String(64))
    last_reconciliation_run_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "paper_reconciliation_runs.run_id",
            ondelete="RESTRICT",
            use_alter=True,
            name="fk_paper_execution_attempts_last_reconciliation_run",
        ),
    )
    last_reconciled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_applied_transaction_id: Mapped[str | None] = mapped_column(String(64))
    projection_version: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class PaperMutationClaimModel(Base):
    """Append-only possible-mutation barrier for one PAPER attempt."""

    __tablename__ = "paper_mutation_claims"
    __table_args__ = (
        CheckConstraint("phase IN ('ENTRY', 'TAKE_PROFIT')", name="paper_claim_phase"),
        CheckConstraint(
            "normalized_request_fingerprint ~ '^[0-9a-f]{64}$'",
            name="paper_claim_request_fingerprint",
        ),
        UniqueConstraint("attempt_id", "phase", name="uq_paper_claims_attempt_phase"),
        Index("ix_paper_mutation_claims_attempt", "attempt_id"),
    )

    claim_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    attempt_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("paper_execution_attempts.attempt_id", ondelete="RESTRICT"),
        nullable=False,
    )
    phase: Mapped[str] = mapped_column(String(20), nullable=False)
    claimed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    provider_endpoint_key: Mapped[str] = mapped_column(String(128), nullable=False)
    normalized_request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)


class PaperBrokerObservationModel(Base):
    """Append-only normalized provider observation; never an Atlas conclusion."""

    __tablename__ = "paper_broker_observations"
    __table_args__ = (
        CheckConstraint("observation_sequence > 0", name="paper_observation_sequence"),
        CheckConstraint(
            "read_kind IN ('ENTRY_MUTATION_RESPONSE', 'TAKE_PROFIT_MUTATION_RESPONSE', 'ORDER_DETAIL', 'TRANSACTION_DETAIL', 'TRANSACTION_RANGE', 'TRADE_DETAIL', 'ACCOUNT_DETAILS')",
            name="paper_observation_read_kind",
        ),
        CheckConstraint(
            "object_kind IN ('ORDER', 'TRANSACTION', 'TRADE', 'ACCOUNT', 'MUTATION_RESULT')",
            name="paper_observation_object_kind",
        ),
        CheckConstraint("provider = 'OANDA' AND environment = 'PRACTICE'", name="paper_observation_scope"),
        CheckConstraint("instrument IS NULL OR instrument = 'EUR_USD'", name="paper_observation_instrument"),
        CheckConstraint("jsonb_typeof(normalized_facts) = 'object'", name="paper_observation_facts_object"),
        CheckConstraint("jsonb_typeof(related_transaction_ids) = 'array' AND jsonb_array_length(related_transaction_ids) <= 64", name="paper_observation_related_ids"),
        CheckConstraint("normalized_schema_version <> ''", name="paper_observation_schema_version"),
        UniqueConstraint("attempt_id", "normalized_facts_fingerprint", name="uq_paper_observations_fact"),
        UniqueConstraint("attempt_id", "observation_sequence", name="uq_paper_observations_sequence"),
        Index("ix_paper_broker_observations_attempt_kind", "attempt_id", "read_kind"),
    )

    observation_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    attempt_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("paper_execution_attempts.attempt_id", ondelete="RESTRICT"), nullable=False
    )
    mutation_claim_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("paper_mutation_claims.claim_id", ondelete="RESTRICT")
    )
    reconciliation_run_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("paper_reconciliation_runs.run_id", ondelete="RESTRICT")
    )
    observation_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    read_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    object_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    environment: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_account_id: Mapped[str] = mapped_column(String(128), nullable=False)
    instrument: Mapped[str | None] = mapped_column(String(20))
    provider_order_id: Mapped[str | None] = mapped_column(String(128))
    provider_transaction_id: Mapped[str | None] = mapped_column(String(64))
    provider_trade_id: Mapped[str | None] = mapped_column(String(128))
    client_order_id: Mapped[str | None] = mapped_column(String(128))
    client_trade_id: Mapped[str | None] = mapped_column(String(128))
    client_protection_order_id: Mapped[str | None] = mapped_column(String(128))
    provider_type: Mapped[str | None] = mapped_column(String(64))
    provider_state: Mapped[str | None] = mapped_column(String(64))
    signed_units: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    price: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    request_id: Mapped[str | None] = mapped_column(String(256))
    batch_id: Mapped[str | None] = mapped_column(String(128))
    related_transaction_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    last_transaction_id: Mapped[str | None] = mapped_column(String(64))
    provider_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    atlas_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    normalized_schema_version: Mapped[str] = mapped_column(String(100), nullable=False)
    normalized_facts: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    normalized_facts_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)


class PaperReconciliationRunModel(Base):
    """Append-only summary of one finite, read-only reconciliation request."""

    __tablename__ = "paper_reconciliation_runs"
    __table_args__ = (
        CheckConstraint("run_sequence > 0", name="paper_run_sequence"),
        CheckConstraint("status IN ('PROVEN', 'UNRESOLVED', 'CONFLICT', 'LIFECYCLE_ADVANCED', 'FAILED')", name="paper_run_status"),
        CheckConstraint("projection_version_observed >= 0", name="paper_run_observed_version"),
        CheckConstraint("projection_version_applied IS NULL OR projection_version_applied >= 0", name="paper_run_applied_version"),
        CheckConstraint("read_count >= 0 AND read_budget > 0 AND read_count <= read_budget", name="paper_run_budget"),
        CheckConstraint("jsonb_typeof(finding_codes) = 'array' AND jsonb_array_length(finding_codes) <= 64", name="paper_run_findings"),
        CheckConstraint("prior_execution_outcome IS NULL OR prior_execution_outcome IN ('FILLED_PROTECTED', 'FILLED_PROTECTION_INCOMPLETE', 'REJECTED', 'CANCELLED', 'UNKNOWN')", name="paper_run_prior_outcome"),
        CheckConstraint("resulting_execution_outcome IS NULL OR resulting_execution_outcome IN ('FILLED_PROTECTED', 'FILLED_PROTECTION_INCOMPLETE', 'REJECTED', 'CANCELLED', 'UNKNOWN')", name="paper_run_resulting_outcome"),
        UniqueConstraint("attempt_id", "run_sequence", name="uq_paper_runs_attempt_sequence"),
        Index("ix_paper_reconciliation_runs_attempt_created", "attempt_id", "created_at"),
    )

    run_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    attempt_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("paper_execution_attempts.attempt_id", ondelete="RESTRICT"), nullable=False
    )
    run_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    read_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    projection_version_observed: Mapped[int] = mapped_column(BigInteger, nullable=False)
    projection_version_applied: Mapped[int | None] = mapped_column(BigInteger)
    read_count: Mapped[int] = mapped_column(nullable=False)
    read_budget: Mapped[int] = mapped_column(nullable=False)
    frontier_before: Mapped[str | None] = mapped_column(String(64))
    frontier_observed: Mapped[str | None] = mapped_column(String(64))
    frontier_applied: Mapped[str | None] = mapped_column(String(64))
    non_atomic_read_set: Mapped[bool] = mapped_column(nullable=False, server_default=text("true"))
    prior_execution_outcome: Mapped[str | None] = mapped_column(String(40))
    resulting_execution_outcome: Mapped[str | None] = mapped_column(String(40))
    finding_codes: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    diagnostic_summary: Mapped[str] = mapped_column(String(500), nullable=False, server_default=text("''"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
