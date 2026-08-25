"""Rename the StrategyVersion context requirement to its canonical name."""

# ruff: noqa: I001
from alembic import op


revision = "0012_required_historical_context"
down_revision = "0011_fix_v2_snapshot_trigger"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "strategy_versions",
        "warm_up_bars",
        new_column_name="required_historical_context_bars",
    )


def downgrade() -> None:
    op.alter_column(
        "strategy_versions",
        "required_historical_context_bars",
        new_column_name="warm_up_bars",
    )
