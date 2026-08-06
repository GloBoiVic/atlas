"""Create enriched journal projections for completed trades.

Revision ID: 010_journal_entries
Revises: 009_funding_adjustments
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "010"
down_revision: str | None = "009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "journal_entries",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("bot_id", sa.Uuid()),
        sa.Column("strategy_version_id", sa.Uuid()),
        sa.Column("trade_id", sa.Uuid(), nullable=False),
        sa.Column("instrument_id", sa.Uuid()),
        sa.Column("symbol", sa.String(50), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("entry_price", sa.Numeric(28, 12), nullable=False),
        sa.Column("exit_price", sa.Numeric(28, 12)),
        sa.Column("quantity", sa.Numeric(28, 12), nullable=False),
        sa.Column("pnl", sa.Numeric(28, 12)),
        sa.Column("strategy_name", sa.String(255), nullable=False),
        sa.Column(
            "signal",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "market_conditions",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("notes", sa.Text()),
        sa.Column(
            "risk_metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["bot_id"], ["bots.id"]),
        sa.ForeignKeyConstraint(["strategy_version_id"], ["strategy_versions.id"]),
        sa.ForeignKeyConstraint(["trade_id"], ["trades.id"]),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("trade_id", name="uq_journal_entries_trade_id"),
    )
    op.create_index("idx_journal_strategy", "journal_entries", ["strategy_name"])


def downgrade() -> None:
    op.drop_index("idx_journal_strategy", table_name="journal_entries")
    op.drop_table("journal_entries")
