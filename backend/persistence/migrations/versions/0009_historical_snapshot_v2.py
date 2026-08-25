"""Version the historical DatasetSnapshot contract and add V2 memberships."""
# Migration declarations intentionally mirror the SQL contract verbatim.
# ruff: noqa: E501

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0009_historical_snapshot_v2"
down_revision = "0008_historical_load"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
TS = sa.DateTime(timezone=True)
PRICE = sa.Numeric(20, 10)


def upgrade() -> None:
    op.add_column("dataset_snapshots", sa.Column("snapshot_schema", sa.String(100), server_default=sa.text("'ATLAS_HISTORICAL_SNAPSHOT_V1'"), nullable=False))
    for name in ("base_resolution_m1", "fixed_components", "alignment_v1", "session_policy_v1", "fingerprint_schema_v1", "valid_integrity_summary"):
        op.drop_constraint(name, "dataset_snapshots", type_="check")
    op.create_check_constraint("snapshot_resolution_by_schema", "dataset_snapshots", "(snapshot_schema = 'ATLAS_HISTORICAL_SNAPSHOT_V1' AND base_resolution = 'M1') OR (snapshot_schema = 'ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2' AND base_resolution = 'M15')")
    op.create_check_constraint("components_by_schema", "dataset_snapshots", "(snapshot_schema = 'ATLAS_HISTORICAL_SNAPSHOT_V1' AND components = '[\"ASK\",\"BID\",\"MID\"]'::jsonb) OR (snapshot_schema = 'ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2' AND components = '[\"MID\"]'::jsonb)")
    op.create_check_constraint("alignment_v1", "dataset_snapshots", "alignment_convention = 'UTC_HALF_OPEN_V1'")
    op.create_check_constraint("session_policy_v1", "dataset_snapshots", "session_policy = 'OANDA_FX_NY_V1'")
    op.create_check_constraint("fingerprint_schema_by_snapshot", "dataset_snapshots", "(snapshot_schema = 'ATLAS_HISTORICAL_SNAPSHOT_V1' AND fingerprint_schema = 'ATLAS_DATASET_SHA256_V1') OR (snapshot_schema = 'ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2' AND fingerprint_schema = 'ATLAS_DATASET_SHA256_V2')")
    op.create_check_constraint("valid_integrity_summary", "dataset_snapshots", "jsonb_typeof(integrity_summary) = 'object' AND integrity_summary->>'status' = 'VALID' AND ((snapshot_schema = 'ATLAS_HISTORICAL_SNAPSHOT_V1' AND integrity_summary ?& ARRAY['expected_open_minutes','expected_closure_minutes','member_minutes','bar_count','unexpected_gap_count','unexpected_observation_count','session_policy'] AND integrity_summary->>'session_policy' = 'OANDA_FX_NY_V1') OR (snapshot_schema = 'ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2' AND integrity_summary->>'policy_version' = 'ATLAS_HISTORICAL_GAP_POLICY_V1'))")

    op.create_table("dataset_snapshot_analytical_bars",
        sa.Column("dataset_snapshot_id", UUID, nullable=False), sa.Column("sequence", sa.BigInteger, nullable=False),
        sa.Column("start_time", TS, nullable=False), sa.Column("end_time", TS, nullable=False),
        sa.Column("resolution", sa.String(3), server_default=sa.text("'M15'"), nullable=False), sa.Column("price_component", sa.String(3), server_default=sa.text("'MID'"), nullable=False),
        sa.Column("open_price", PRICE, nullable=False), sa.Column("high_price", PRICE, nullable=False), sa.Column("low_price", PRICE, nullable=False), sa.Column("close_price", PRICE, nullable=False), sa.Column("volume", PRICE),
        sa.Column("complete", sa.Boolean, nullable=False), sa.Column("source_request_id", sa.String(200)), sa.Column("content_fingerprint", sa.String(64), nullable=False), sa.Column("retrieved_at", TS, nullable=False),
        sa.ForeignKeyConstraint(["dataset_snapshot_id"], ["dataset_snapshots.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("dataset_snapshot_id", "sequence"), sa.UniqueConstraint("dataset_snapshot_id", "start_time", "content_fingerprint"),
        sa.CheckConstraint("sequence > 0 AND resolution = 'M15' AND price_component = 'MID' AND complete IS TRUE AND end_time = start_time + interval '15 minutes' AND content_fingerprint ~ '^[0-9a-f]{64}$'", name="valid_analytical_member"))
    op.create_table("dataset_snapshot_execution_observations",
        sa.Column("dataset_snapshot_id", UUID, nullable=False), sa.Column("sequence", sa.BigInteger, nullable=False), sa.Column("market_bar_id", UUID, nullable=False), sa.Column("price_component", sa.String(3), nullable=False), sa.Column("start_time", TS, nullable=False), sa.Column("end_time", TS, nullable=False), sa.Column("observation_fingerprint", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(["dataset_snapshot_id"], ["dataset_snapshots.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["market_bar_id"], ["market_bars.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("dataset_snapshot_id", "sequence"), sa.UniqueConstraint("dataset_snapshot_id", "market_bar_id"),
        sa.CheckConstraint("sequence > 0 AND price_component IN ('BID','ASK') AND end_time = start_time + interval '1 minute' AND observation_fingerprint ~ '^[0-9a-f]{64}$'", name="valid_execution_member"))
    op.create_table("dataset_snapshot_gaps",
        sa.Column("dataset_snapshot_id", UUID, nullable=False), sa.Column("sequence", sa.BigInteger, nullable=False), sa.Column("start_time", TS, nullable=False), sa.Column("end_time", TS, nullable=False), sa.Column("price_component", sa.String(3)), sa.Column("resolution", sa.String(3), nullable=False), sa.Column("source", sa.String(100), nullable=False), sa.Column("reason", sa.String(200), nullable=False), sa.Column("classification", sa.String(30), nullable=False), sa.Column("affected_state", sa.String(100)), sa.Column("affected_event", sa.String(100)), sa.Column("policy_version", sa.String(100), nullable=False), sa.Column("blocked", sa.Boolean, nullable=False),
        sa.ForeignKeyConstraint(["dataset_snapshot_id"], ["dataset_snapshots.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("dataset_snapshot_id", "sequence"), sa.CheckConstraint("sequence > 0 AND end_time > start_time AND resolution IN ('M1','M15') AND classification IN ('NON_BLOCKING','RESOLVABLE','BLOCKING','EXTENDED_OUTAGE') AND policy_version = 'ATLAS_HISTORICAL_GAP_POLICY_V1'", name="valid_snapshot_gap"))

    op.execute("""CREATE FUNCTION snapshot_v2_append_only_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'dataset snapshot memberships are immutable'; END IF; IF NOT EXISTS (SELECT 1 FROM dataset_snapshots WHERE id = NEW.dataset_snapshot_id AND snapshot_schema = 'ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2') THEN RAISE EXCEPTION 'V2 membership requires a V2 snapshot'; END IF; IF TG_TABLE_NAME = 'dataset_snapshot_execution_observations' AND NOT EXISTS (SELECT 1 FROM market_bars WHERE id = NEW.market_bar_id AND resolution = 'M1' AND price_component = NEW.price_component AND complete IS TRUE) THEN RAISE EXCEPTION 'execution membership must reference a completed matching M1 observation'; END IF; RETURN NEW; END; $$""")
    for table in ("dataset_snapshot_analytical_bars", "dataset_snapshot_execution_observations", "dataset_snapshot_gaps"):
        op.execute(f"CREATE TRIGGER {table}_append_only BEFORE INSERT OR UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION snapshot_v2_append_only_guard()")


def downgrade() -> None:
    for table in ("dataset_snapshot_gaps", "dataset_snapshot_execution_observations", "dataset_snapshot_analytical_bars"):
        op.execute(f"DROP TRIGGER {table}_append_only ON {table}")
        op.drop_table(table)
    op.execute("DROP FUNCTION snapshot_v2_append_only_guard()")
    for name in ("valid_integrity_summary", "fingerprint_schema_by_snapshot", "session_policy_v1", "alignment_v1", "components_by_schema", "snapshot_resolution_by_schema"):
        op.drop_constraint(name, "dataset_snapshots", type_="check")
    op.create_check_constraint("base_resolution_m1", "dataset_snapshots", "base_resolution = 'M1'")
    op.create_check_constraint("fixed_components", "dataset_snapshots", "components = '[\"ASK\",\"BID\",\"MID\"]'::jsonb")
    op.create_check_constraint("alignment_v1", "dataset_snapshots", "alignment_convention = 'UTC_HALF_OPEN_V1'")
    op.create_check_constraint("session_policy_v1", "dataset_snapshots", "session_policy = 'OANDA_FX_NY_V1'")
    op.create_check_constraint("fingerprint_schema_v1", "dataset_snapshots", "fingerprint_schema = 'ATLAS_DATASET_SHA256_V1'")
    op.create_check_constraint("valid_integrity_summary", "dataset_snapshots", "jsonb_typeof(integrity_summary) = 'object' AND integrity_summary ?& ARRAY['status','expected_open_minutes','expected_closure_minutes','member_minutes','bar_count','unexpected_gap_count','unexpected_observation_count','session_policy'] AND integrity_summary->>'status' = 'VALID' AND integrity_summary->>'session_policy' = 'OANDA_FX_NY_V1'")
    op.drop_column("dataset_snapshots", "snapshot_schema")
