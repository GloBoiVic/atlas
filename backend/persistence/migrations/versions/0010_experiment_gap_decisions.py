"""Persist deterministic result quality and experiment gap decisions."""

# fmt: off
# ruff: noqa: E501
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.elements import conv

revision = "0010_experiment_gap_decisions"
down_revision = "0009_historical_snapshot_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("experiment_results", sa.Column("result_quality", postgresql.JSONB, server_default=sa.text("'{\"schema\": \"ATLAS_RESULT_QUALITY_V1\", \"value\": \"DETERMINED\"}'::jsonb"), nullable=False))
    op.create_check_constraint("result_quality_values", "experiment_results", "jsonb_typeof(result_quality) = 'object' AND result_quality->>'schema' = 'ATLAS_RESULT_QUALITY_V1' AND result_quality->>'value' IN ('DETERMINED','DETERMINED_WITH_GAPS','CONSERVATIVE_AMBIGUITY_RESOLVED')")
    op.create_table(
        "experiment_gap_decisions",
        sa.Column("experiment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Integer, nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolution", sa.String(3), nullable=False),
        sa.Column("price_component", sa.String(3)),
        sa.Column("classification", sa.String(30), nullable=False),
        sa.Column("rule_version", sa.String(100), nullable=False),
        sa.Column("policy_version", sa.String(100), nullable=False),
        sa.Column("affected_state", sa.String(100)),
        sa.Column("affected_event", sa.String(100)),
        sa.Column("blocked", sa.Boolean, nullable=False),
        sa.Column("details", postgresql.JSONB, nullable=False),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("experiment_id", "sequence"),
        sa.CheckConstraint("sequence > 0 AND end_time > start_time", name="gap_decision_interval"),
        sa.CheckConstraint("resolution IN ('M1','M15') AND (price_component IS NULL OR price_component IN ('BID','ASK','MID'))", name="gap_decision_market_shape"),
        sa.CheckConstraint("classification IN ('NON_BLOCKING','RESOLVABLE','BLOCKING','EXTENDED_OUTAGE')", name="gap_decision_classification"),
        sa.CheckConstraint("policy_version = 'ATLAS_HISTORICAL_GAP_POLICY_V1' AND rule_version <> ''", name="gap_decision_policy_version"),
        sa.CheckConstraint("jsonb_typeof(details) = 'object'", name="gap_decision_details_object"),
    )
    op.execute("""CREATE FUNCTION experiment_gap_decision_append_only() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'experiment gap decisions are immutable'; END IF; RETURN NEW; END; $$""")
    op.execute("CREATE TRIGGER experiment_gap_decisions_append_only BEFORE INSERT OR UPDATE OR DELETE ON experiment_gap_decisions FOR EACH ROW EXECUTE FUNCTION experiment_gap_decision_append_only()")


def downgrade() -> None:
    op.execute("DROP TRIGGER experiment_gap_decisions_append_only ON experiment_gap_decisions")
    op.execute("DROP FUNCTION experiment_gap_decision_append_only()")
    op.drop_table("experiment_gap_decisions")
    op.drop_constraint(conv("ck_experiment_results_result_quality_values"), "experiment_results", type_="check")
    op.drop_column("experiment_results", "result_quality")
