"""Add the bounded, durable historical data load command."""
# Migration declarations intentionally mirror the SQL contract verbatim.
# ruff: noqa: E501, E701, E702
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008_historical_load"
down_revision = "0007_phase_5_metric_contract"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute(sa.text("""
        CREATE FUNCTION atlas_historical_ranges_valid(value jsonb)
        RETURNS boolean LANGUAGE plpgsql IMMUTABLE AS $function$
        DECLARE
            item jsonb;
            current_start timestamptz;
            current_end timestamptz;
            previous_end timestamptz := NULL;
        BEGIN
            IF jsonb_typeof(value) <> 'array' OR jsonb_array_length(value) > 40 THEN
                RETURN false;
            END IF;
            FOR item IN SELECT jsonb_array_elements(value) LOOP
                IF jsonb_typeof(item) <> 'object'
                   OR NOT (item ? 'start') OR NOT (item ? 'end')
                   OR jsonb_typeof(item->'start') <> 'string'
                   OR jsonb_typeof(item->'end') <> 'string'
                   OR (item - 'start' - 'end') <> '{}'::jsonb
                   OR (item->>'start') !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\\.[0-9]{1,6})?Z$'
                   OR (item->>'end') !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\\.[0-9]{1,6})?Z$' THEN
                    RETURN false;
                END IF;
                current_start := item->>'start';
                current_end := item->>'end';
                IF current_end <= current_start OR (previous_end IS NOT NULL AND current_start < previous_end) THEN
                    RETURN false;
                END IF;
                previous_end := current_end;
            END LOOP;
            RETURN true;
        EXCEPTION WHEN others THEN
            RETURN false;
        END;
        $function$;
    """))
    op.create_table(
        "historical_data_load_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("operation", sa.String(30), server_default=sa.text("'LOAD_MISSING'"), nullable=False),
        sa.Column("status", sa.String(20), server_default=sa.text("'PENDING'"), nullable=False),
        sa.Column("strategy_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("strategy_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("trading_start", sa.DateTime(timezone=True), nullable=False), sa.Column("trading_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("load_start", sa.DateTime(timezone=True), nullable=False), sa.Column("load_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fetched_ranges", postgresql.JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("committed_ranges", postgresql.JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("inserted", sa.BigInteger, server_default=sa.text("0"), nullable=False), sa.Column("reactivated", sa.BigInteger, server_default=sa.text("0"), nullable=False), sa.Column("unchanged", sa.BigInteger, server_default=sa.text("0"), nullable=False), sa.Column("incomplete_minute_count", sa.BigInteger, server_default=sa.text("0"), nullable=False),
        sa.Column("coverage_summary", postgresql.JSONB), sa.Column("experiment_validation", postgresql.JSONB),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("dataset_snapshots.id", ondelete="RESTRICT")),
        sa.Column("failure_category", sa.String(20)), sa.Column("failure_code", sa.String(80)), sa.Column("failure_detail", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)), sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    checks = {
        "load_operation": "operation = 'LOAD_MISSING'",
        "load_status": "status IN ('PENDING','RUNNING','COMPLETED','FAILED')",
        "load_order": "trading_end > trading_start AND load_start <= trading_start AND load_end = trading_end",
        "trading_alignment": "extract(epoch from trading_start)::bigint % 900 = 0 AND extract(epoch from trading_end)::bigint % 900 = 0",
        "load_alignment": "extract(epoch from load_start)::bigint % 60 = 0 AND extract(epoch from load_end)::bigint % 60 = 0",
        "load_maximum": "load_end - load_start <= interval '90 days'",
        "progress_arrays": "atlas_historical_ranges_valid(fetched_ranges) AND atlas_historical_ranges_valid(committed_ranges)",
        "coverage_object": "coverage_summary IS NULL OR jsonb_typeof(coverage_summary) = 'object'",
        "validation_object": "experiment_validation IS NULL OR jsonb_typeof(experiment_validation) = 'object'",
        "nonnegative_counters": "inserted >= 0 AND reactivated >= 0 AND unchanged >= 0 AND incomplete_minute_count >= 0",
        "load_failure_category": "failure_category IS NULL OR failure_category IN ('VALIDATION','MARKET_DATA','PERSISTENCE','RUNTIME')",
        "load_failure_code": "failure_code IS NULL OR failure_code ~ '^[A-Z0-9_]+$'",
        "load_failure_detail": "failure_detail IS NULL OR (length(failure_detail) BETWEEN 1 AND 500 AND failure_detail !~ '[[:cntrl:]]')",
        "load_state_consistency": "(status = 'PENDING' AND started_at IS NULL AND finished_at IS NULL AND failure_category IS NULL AND failure_code IS NULL AND failure_detail IS NULL AND snapshot_id IS NULL AND coverage_summary IS NULL AND experiment_validation IS NULL) OR (status = 'RUNNING' AND started_at IS NOT NULL AND finished_at IS NULL AND failure_category IS NULL AND failure_code IS NULL AND failure_detail IS NULL) OR (status = 'COMPLETED' AND started_at IS NOT NULL AND finished_at IS NOT NULL AND snapshot_id IS NOT NULL AND coverage_summary->>'valid' = 'true' AND experiment_validation->>'valid' = 'true' AND failure_category IS NULL AND failure_code IS NULL AND failure_detail IS NULL) OR (status = 'FAILED' AND finished_at IS NOT NULL AND failure_category IS NOT NULL AND failure_code IS NOT NULL AND failure_detail IS NOT NULL)"
    }
    for name, condition in checks.items(): op.create_check_constraint(name, "historical_data_load_requests", condition)
    op.create_index("uq_historical_data_load_requests_active", "historical_data_load_requests", [sa.text("(1)")], unique=True, postgresql_where=sa.text("status IN ('PENDING','RUNNING')"))
    op.create_index("ix_historical_data_load_requests_status", "historical_data_load_requests", ["status"])
    op.create_index("ix_historical_data_load_requests_created_at_id_desc", "historical_data_load_requests", [sa.text("created_at DESC"), sa.text("id DESC")])

def downgrade() -> None:
    op.drop_index("ix_historical_data_load_requests_created_at_id_desc", table_name="historical_data_load_requests")
    op.drop_index("ix_historical_data_load_requests_status", table_name="historical_data_load_requests")
    op.drop_index("uq_historical_data_load_requests_active", table_name="historical_data_load_requests")
    op.drop_table("historical_data_load_requests")
    op.execute(sa.text("DROP FUNCTION IF EXISTS atlas_historical_ranges_valid(jsonb)"))
