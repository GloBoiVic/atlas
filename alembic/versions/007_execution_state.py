"""create durable execution orders, fills, positions, and trades"""

from collections.abc import Sequence
from typing import TYPE_CHECKING, cast

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

if TYPE_CHECKING:
    from sqlalchemy.types import TypeEngine

revision: str = "007"
down_revision: str | None = "006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NUMERIC = sa.Numeric(28, 12)


def _uuid(name: str, *, primary_key: bool = False) -> sa.Column[object]:
    return sa.Column(
        name,
        cast("TypeEngine[object]", sa.Uuid()),
        primary_key=primary_key,
        nullable=False,
        server_default=sa.text("gen_random_uuid()") if primary_key else None,
    )


def upgrade() -> None:
    op.create_table(
        "orders",
        _uuid("id", primary_key=True),
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("bot_id", sa.Uuid(), sa.ForeignKey("bots.id")),
        sa.Column("strategy_version_id", sa.Uuid(), sa.ForeignKey("strategy_versions.id")),
        sa.Column("instrument_id", sa.Uuid(), sa.ForeignKey("instruments.id"), nullable=False),
        sa.Column("client_order_id", sa.String(255), nullable=False),
        sa.Column("broker_order_id", sa.String(255)),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("quantity", NUMERIC, nullable=False),
        sa.Column("order_type", sa.String(20), nullable=False),
        sa.Column("stop_loss", NUMERIC, nullable=False, server_default="0"),
        sa.Column("take_profit", NUMERIC, nullable=False, server_default="0"),
        sa.Column("reduce_only", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("leverage", sa.Numeric(12, 6), nullable=False, server_default="1"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("filled_quantity", NUMERIC, nullable=False, server_default="0"),
        sa.Column("average_fill_price", NUMERIC),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("client_order_id"),
        sa.UniqueConstraint("broker_order_id"),
    )
    op.create_index("idx_orders_status", "orders", ["status"])

    op.create_table(
        "fills",
        _uuid("id", primary_key=True),
        sa.Column("order_id", sa.Uuid(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column(
            "instrument_id", sa.Uuid(), sa.ForeignKey("instruments.id"), nullable=False
        ),
        sa.Column("broker_fill_id", sa.String(255)),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("quantity", NUMERIC, nullable=False),
        sa.Column("price", NUMERIC, nullable=False),
        sa.Column("fee", NUMERIC, nullable=False, server_default="0"),
        sa.Column("filled_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "idx_fills_broker_execution",
        "fills",
        ["broker_fill_id"],
        unique=True,
        postgresql_where=sa.text("broker_fill_id IS NOT NULL"),
        sqlite_where=sa.text("broker_fill_id IS NOT NULL"),
    )

    op.create_table(
        "positions",
        _uuid("id", primary_key=True),
        sa.Column(
            "account_id", sa.Uuid(), sa.ForeignKey("accounts.id"), nullable=False
        ),
        sa.Column("bot_id", sa.Uuid(), sa.ForeignKey("bots.id")),
        sa.Column("strategy_version_id", sa.Uuid(), sa.ForeignKey("strategy_versions.id")),
        sa.Column(
            "instrument_id", sa.Uuid(), sa.ForeignKey("instruments.id"), nullable=False
        ),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("quantity", NUMERIC, nullable=False),
        sa.Column("entry_price", NUMERIC, nullable=False),
        sa.Column("current_price", NUMERIC),
        sa.Column("stop_loss", NUMERIC),
        sa.Column("take_profit", NUMERIC),
        sa.Column("unrealized_pnl", NUMERIC, nullable=False, server_default="0"),
        sa.Column("realized_pnl", NUMERIC, nullable=False, server_default="0"),
        sa.Column("leverage", sa.Numeric(12, 6), nullable=False, server_default="1"),
        sa.Column("isolated_margin", NUMERIC, nullable=False, server_default="0"),
        sa.Column("maintenance_margin", NUMERIC, nullable=False, server_default="0"),
        sa.Column("liquidation_price", NUMERIC),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column(
            "opened_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "idx_one_active_net_position",
        "positions",
        ["account_id", "instrument_id", "mode"],
        unique=True,
        postgresql_where=sa.text("status IN ('open', 'reducing')"),
        sqlite_where=sa.text("status IN ('open', 'reducing')"),
    )

    op.create_table(
        "trades",
        _uuid("id", primary_key=True),
        sa.Column(
            "account_id", sa.Uuid(), sa.ForeignKey("accounts.id"), nullable=False
        ),
        sa.Column("bot_id", sa.Uuid(), sa.ForeignKey("bots.id")),
        sa.Column(
            "strategy_version_id", sa.Uuid(), sa.ForeignKey("strategy_versions.id")
        ),
        sa.Column(
            "position_id", sa.Uuid(), sa.ForeignKey("positions.id"), nullable=False
        ),
        sa.Column(
            "instrument_id", sa.Uuid(), sa.ForeignKey("instruments.id"), nullable=False
        ),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("entry_price", NUMERIC, nullable=False),
        sa.Column("exit_price", NUMERIC),
        sa.Column("quantity", NUMERIC, nullable=False),
        sa.Column("gross_pnl", NUMERIC),
        sa.Column("net_pnl", NUMERIC),
        sa.Column("total_fees", NUMERIC, nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="entered"),
        sa.Column(
            "signal_metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "market_context",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("entry_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exit_time", sa.DateTime(timezone=True)),
    )
    op.create_index("idx_trades_status", "trades", ["status"])


def downgrade() -> None:
    op.drop_index("idx_trades_status", table_name="trades")
    op.drop_table("trades")
    op.drop_index("idx_one_active_net_position", table_name="positions")
    op.drop_table("positions")
    op.drop_index("idx_fills_broker_execution", table_name="fills")
    op.drop_table("fills")
    op.drop_index("idx_orders_status", table_name="orders")
    op.drop_table("orders")
