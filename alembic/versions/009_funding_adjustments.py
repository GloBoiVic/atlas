"""Add idempotent paper Futures funding settlements.

Revision ID: 009_funding_adjustments
Revises: 008_backtest_results
"""

import sqlalchemy as sa

from alembic import op

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "funding_adjustments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("instrument_id", sa.Uuid(), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("amount", sa.Numeric(precision=28, scale=12), nullable=False),
        sa.Column("funding_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "account_id", "instrument_id", "mode", "funding_timestamp",
            name="uq_funding_adjustment_scope_timestamp",
        ),
    )


def downgrade() -> None:
    op.drop_table("funding_adjustments")
