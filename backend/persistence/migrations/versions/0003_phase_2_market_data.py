"""Phase 2 immutable market data and dataset snapshot persistence."""

# fmt: off
# ruff: noqa: E501

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_phase_2_market_data"
down_revision = "0002_phase_1_strategy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "instruments",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("base_currency", sa.String(3), nullable=False),
        sa.Column("quote_currency", sa.String(3), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("code = 'EUR/USD'", name="phase_2_code"),
        sa.CheckConstraint("base_currency = 'EUR'", name="phase_2_base_currency"),
        sa.CheckConstraint("quote_currency = 'USD'", name="phase_2_quote_currency"),
        sa.PrimaryKeyConstraint("id", name="pk_instruments"),
        sa.UniqueConstraint("code", name="uq_instruments_code"),
    )
    op.create_table(
        "venue_instruments",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("instrument_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("provider_symbol", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("provider = 'OANDA'", name="phase_2_provider"),
        sa.CheckConstraint("provider_symbol = 'EUR_USD'", name="phase_2_provider_symbol"),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"], name="fk_venue_instruments_instrument_id_instruments", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_venue_instruments"),
        sa.UniqueConstraint("provider", "provider_symbol", name="uq_venue_instruments_provider"),
        sa.UniqueConstraint("instrument_id", "provider", name="uq_venue_instruments_instrument_id"),
    )
    op.create_table(
        "market_bars",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("venue_instrument_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resolution", sa.String(3), nullable=False),
        sa.Column("price_component", sa.String(3), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open_price", sa.Numeric(20, 10), nullable=False),
        sa.Column("high_price", sa.Numeric(20, 10), nullable=False),
        sa.Column("low_price", sa.Numeric(20, 10), nullable=False),
        sa.Column("close_price", sa.Numeric(20, 10), nullable=False),
        sa.Column("volume", sa.Numeric(20, 10), nullable=True),
        sa.Column("complete", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("content_fingerprint", sa.String(64), nullable=False),
        sa.Column("source_request_id", sa.String(200), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_current", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.CheckConstraint("resolution = 'M1'", name="m1_only"),
        sa.CheckConstraint("price_component IN ('ASK', 'BID', 'MID')", name="valid_component"),
        sa.CheckConstraint("start_time = date_trunc('minute', start_time)", name="minute_aligned_start"),
        sa.CheckConstraint("end_time = start_time + interval '1 minute'", name="exact_one_minute"),
        sa.CheckConstraint("complete IS TRUE", name="completed_only"),
        sa.CheckConstraint("open_price > 0 AND high_price > 0 AND low_price > 0 AND close_price > 0", name="positive_prices"),
        sa.CheckConstraint("open_price <> 'NaN'::numeric AND high_price <> 'NaN'::numeric AND low_price <> 'NaN'::numeric AND close_price <> 'NaN'::numeric", name="finite_prices"),
        sa.CheckConstraint("low_price <= open_price AND low_price <= close_price AND high_price >= open_price AND high_price >= close_price", name="ohlc_containment"),
        sa.CheckConstraint("volume IS NULL OR (volume >= 0 AND volume <> 'NaN'::numeric)", name="non_negative_volume"),
        sa.CheckConstraint("content_fingerprint ~ '^[0-9a-f]{64}$'", name="sha256_fingerprint"),
        sa.CheckConstraint("source_request_id IS NULL OR source_request_id !~ '[[:cntrl:]]'", name="sanitized_request_id"),
        sa.ForeignKeyConstraint(["venue_instrument_id"], ["venue_instruments.id"], name="fk_market_bars_venue_instrument_id_venue_instruments", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_market_bars"),
        sa.UniqueConstraint("venue_instrument_id", "resolution", "price_component", "start_time", "content_fingerprint", name="uq_market_bars_venue_instrument_id"),
    )
    op.create_index("uq_market_bars_current", "market_bars", ["venue_instrument_id", "resolution", "price_component", "start_time"], unique=True, postgresql_where=sa.text("is_current"))
    op.create_index("ix_market_bars_current_range", "market_bars", ["venue_instrument_id", "resolution", "price_component", "start_time"], postgresql_where=sa.text("is_current"))

    op.create_table(
        "dataset_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("venue_instrument_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("base_resolution", sa.String(3), nullable=False),
        sa.Column("components", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("coverage_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("coverage_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("alignment_convention", sa.String(30), nullable=False),
        sa.Column("session_policy", sa.String(30), nullable=False),
        sa.Column("fingerprint_schema", sa.String(40), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("integrity_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("base_resolution = 'M1'", name="base_resolution_m1"),
        sa.CheckConstraint("components = '[\"ASK\",\"BID\",\"MID\"]'::jsonb", name="fixed_components"),
        sa.CheckConstraint("alignment_convention = 'UTC_HALF_OPEN_V1'", name="alignment_v1"),
        sa.CheckConstraint("session_policy = 'OANDA_FX_NY_V1'", name="session_policy_v1"),
        sa.CheckConstraint("fingerprint_schema = 'ATLAS_DATASET_SHA256_V1'", name="fingerprint_schema_v1"),
        sa.CheckConstraint("coverage_start = date_trunc('minute', coverage_start) AND coverage_end = date_trunc('minute', coverage_end) AND coverage_end > coverage_start", name="valid_coverage_range"),
        sa.CheckConstraint("fingerprint ~ '^[0-9a-f]{64}$'", name="sha256_fingerprint"),
        sa.CheckConstraint("jsonb_typeof(integrity_summary) = 'object' AND integrity_summary ?& ARRAY['status','expected_open_minutes','expected_closure_minutes','member_minutes','bar_count','unexpected_gap_count','unexpected_observation_count','session_policy'] AND integrity_summary->>'status' = 'VALID' AND integrity_summary->>'session_policy' = 'OANDA_FX_NY_V1'", name="valid_integrity_summary"),
        sa.ForeignKeyConstraint(["venue_instrument_id"], ["venue_instruments.id"], name="fk_dataset_snapshots_venue_instrument_id_venue_instruments", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_dataset_snapshots"),
        sa.UniqueConstraint("fingerprint", name="uq_dataset_snapshots_fingerprint"),
    )
    op.create_table(
        "dataset_snapshot_bars",
        sa.Column("dataset_snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("market_bar_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["dataset_snapshot_id"], ["dataset_snapshots.id"], name="fk_dataset_snapshot_bars_dataset_snapshot_id_dataset_snapshots", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["market_bar_id"], ["market_bars.id"], name="fk_dataset_snapshot_bars_market_bar_id_market_bars", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("dataset_snapshot_id", "market_bar_id", name="pk_dataset_snapshot_bars"),
    )

    op.execute("""
        CREATE FUNCTION prevent_market_bar_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'market_bars are immutable'; END IF;
            IF (to_jsonb(OLD) - 'is_current') IS DISTINCT FROM (to_jsonb(NEW) - 'is_current') THEN
                RAISE EXCEPTION 'market_bars content is immutable';
            END IF;
            RETURN NEW;
        END; $$
    """)
    op.execute("CREATE TRIGGER market_bars_append_only BEFORE UPDATE OR DELETE ON market_bars FOR EACH ROW EXECUTE FUNCTION prevent_market_bar_mutation()")
    op.execute("""
        CREATE FUNCTION prevent_dataset_snapshot_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'dataset_snapshots are immutable'; END; $$
    """)
    op.execute("CREATE TRIGGER dataset_snapshots_append_only BEFORE UPDATE OR DELETE ON dataset_snapshots FOR EACH ROW EXECUTE FUNCTION prevent_dataset_snapshot_mutation()")
    op.execute("""
        CREATE FUNCTION prevent_dataset_snapshot_bar_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'dataset_snapshot_bars are immutable'; END; $$
    """)
    op.execute("CREATE TRIGGER dataset_snapshot_bars_append_only BEFORE UPDATE OR DELETE ON dataset_snapshot_bars FOR EACH ROW EXECUTE FUNCTION prevent_dataset_snapshot_bar_mutation()")


def downgrade() -> None:
    op.execute("DROP TRIGGER dataset_snapshot_bars_append_only ON dataset_snapshot_bars")
    op.execute("DROP FUNCTION prevent_dataset_snapshot_bar_mutation()")
    op.execute("DROP TRIGGER dataset_snapshots_append_only ON dataset_snapshots")
    op.execute("DROP FUNCTION prevent_dataset_snapshot_mutation()")
    op.execute("DROP TRIGGER market_bars_append_only ON market_bars")
    op.execute("DROP FUNCTION prevent_market_bar_mutation()")
    op.drop_table("dataset_snapshot_bars")
    op.drop_table("dataset_snapshots")
    op.drop_index("ix_market_bars_current_range", table_name="market_bars")
    op.drop_index("uq_market_bars_current", table_name="market_bars")
    op.drop_table("market_bars")
    op.drop_table("venue_instruments")
    op.drop_table("instruments")
