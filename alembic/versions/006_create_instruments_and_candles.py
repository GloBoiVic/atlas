"""create provider-aware instruments and candles tables

Revision ID: 006
Revises: 005
Create Date: 2026-08-02

Creates ``instruments`` and ``candles`` with native PostgreSQL ``UUID`` primary
keys, provider-scoped uniqueness, explicit volume fields, ``price_basis``, and
the ``idx_candles_lookup`` index for time-range queries.

Requires PostgreSQL; SQLite cannot execute this migration.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "instruments",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("symbol", sa.String(50), nullable=False),
        sa.Column("asset_type", sa.String(20), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("base_currency", sa.String(10), nullable=True),
        sa.Column("quote_currency", sa.String(10), nullable=True),
        sa.Column("price_precision", sa.Integer(), nullable=False),
        sa.Column("quantity_precision", sa.Integer(), nullable=False),
        sa.Column(
            "constraints",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("symbol", "provider"),
    )

    op.create_table(
        "candles",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("instrument_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("timeframe", sa.String(10), nullable=False),
        sa.Column("open_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("close_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "price_basis",
            sa.String(10),
            nullable=False,
            server_default="trade",
        ),
        sa.Column("open", sa.Numeric(20, 8), nullable=False),
        sa.Column("high", sa.Numeric(20, 8), nullable=False),
        sa.Column("low", sa.Numeric(20, 8), nullable=False),
        sa.Column("close", sa.Numeric(20, 8), nullable=False),
        sa.Column(
            "base_volume",
            sa.Numeric(20, 8),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("quote_volume", sa.Numeric(20, 8), nullable=True),
        sa.Column("trade_count", sa.Integer(), nullable=True),
        sa.Column("taker_buy_base_volume", sa.Numeric(20, 8), nullable=True),
        sa.Column("taker_buy_quote_volume", sa.Numeric(20, 8), nullable=True),
        sa.Column("tick_volume", sa.BigInteger(), nullable=True),
        sa.Column(
            "is_complete",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"]),
        sa.UniqueConstraint(
            "instrument_id", "provider", "timeframe", "open_time", "price_basis"
        ),
    )

    op.create_index(
        "idx_candles_lookup",
        "candles",
        ["instrument_id", "provider", "timeframe", "open_time"],
    )


def downgrade() -> None:
    op.drop_index("idx_candles_lookup", table_name="candles")
    op.drop_table("candles")
    op.drop_table("instruments")
