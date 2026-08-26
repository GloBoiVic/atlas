"""Persist generic Strategy proposal watch facts."""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007_proposal_watch"
down_revision = "0013_result_quality_degraded"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("trade_intents", sa.Column("entry_policy", sa.String(20), nullable=False, server_default=sa.text("'IMMEDIATE'")))
    op.add_column("trade_intents", sa.Column("trigger_price", sa.Numeric(20, 10), nullable=True))
    op.add_column("trade_intents", sa.Column("trigger_price_basis", sa.String(3), nullable=True))
    op.add_column("trade_intents", sa.Column("expiry_time", sa.DateTime(timezone=True), nullable=True))
    op.add_column("trade_intents", sa.Column("expiry_bars", sa.Integer(), nullable=True))
    op.add_column("trade_intents", sa.Column("proposal_status", sa.String(20), nullable=False, server_default=sa.text("'PENDING'")))
    op.add_column("trade_intents", sa.Column("diagnostics", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.create_check_constraint("valid_entry_policy", "trade_intents", "entry_policy IN ('IMMEDIATE','PRICE_TRIGGERED')")
    op.create_check_constraint("valid_trigger_price", "trade_intents", "trigger_price IS NULL OR (trigger_price > 0 AND trigger_price <> 'NaN'::numeric)")
    op.create_check_constraint("valid_proposal_status", "trade_intents", "proposal_status IN ('PENDING','FILLED','EXPIRED','REJECTED')")
    op.create_check_constraint("entry_policy_shape", "trade_intents", "(entry_policy = 'IMMEDIATE' AND trigger_price IS NULL AND expiry_time IS NULL) OR (entry_policy = 'PRICE_TRIGGERED' AND trigger_price IS NOT NULL AND expiry_time IS NOT NULL)")
    op.create_table("experiment_proposal_diagnostics",
        sa.Column("experiment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("trade_intent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("details", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("experiment_id", "sequence"),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["trade_intent_id"], ["trade_intents.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("sequence > 0 AND event_type IN ('FILLED','EXPIRED','REJECTED','EXECUTION_DATA_UNAVAILABLE')", name="valid_proposal_event"),
        sa.CheckConstraint("jsonb_typeof(details) = 'object'", name="proposal_details_object"),
    )

def downgrade() -> None:
    op.drop_table("experiment_proposal_diagnostics")
    for name in ("entry_policy_shape", "valid_proposal_status", "valid_trigger_price", "valid_entry_policy"):
        op.drop_constraint(name, "trade_intents", type_="check")
    for name in ("diagnostics", "proposal_status", "expiry_bars", "expiry_time", "trigger_price_basis", "trigger_price", "entry_policy"):
        op.drop_column("trade_intents", name)
