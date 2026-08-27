"""Harden proposal policy and expiry invariants."""

# ruff: noqa: E501, F401
import sqlalchemy as sa
from alembic import op

revision = "0008_proposal_constraints"
down_revision = "0007_proposal_watch"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_check_constraint("valid_action_entry_policy", "trade_intents", "(action IN ('OPEN_LONG','OPEN_SHORT') AND ((entry_policy = 'IMMEDIATE' AND trigger_price IS NULL AND trigger_price_basis IS NULL AND expiry_time IS NULL AND expiry_bars IS NULL) OR (entry_policy = 'PRICE_TRIGGERED' AND trigger_price IS NOT NULL AND trigger_price_basis IN ('ASK','BID') AND expiry_time IS NULL AND expiry_bars > 0))) OR (action NOT IN ('OPEN_LONG','OPEN_SHORT') AND entry_policy = 'IMMEDIATE' AND trigger_price IS NULL AND trigger_price_basis IS NULL AND expiry_time IS NULL AND expiry_bars IS NULL)")
    op.create_check_constraint("valid_trigger_price_basis", "trade_intents", "trigger_price_basis IS NULL OR trigger_price_basis IN ('ASK','BID')")
    op.create_check_constraint("positive_expiry_bars", "trade_intents", "expiry_bars IS NULL OR expiry_bars > 0")
    op.create_check_constraint("expiry_after_decision", "trade_intents", "expiry_time IS NULL OR expiry_time > decision_frontier")

def downgrade() -> None:
    for name in ("expiry_after_decision", "positive_expiry_bars", "valid_trigger_price_basis", "valid_action_entry_policy"):
        op.drop_constraint(name, "trade_intents", type_="check")
