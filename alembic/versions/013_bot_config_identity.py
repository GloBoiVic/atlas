"""store canonical bot configuration identity separately from runtime config

Revision ID: 013
Revises: 012
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "013"
down_revision: str | None = "012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "bots",
        sa.Column("config_identity", postgresql.JSONB(), nullable=True),
    )
    op.drop_constraint("uq_bots_create_idempotency", "bots", type_="unique")
    op.create_unique_constraint(
        "uq_bots_create_idempotency",
        "bots",
        [
            "account_id",
            "mode",
            "name",
            "strategy_version_id",
            "broker",
            "instrument",
            "timeframe",
            "config_identity",
        ],
    )


def downgrade() -> None:
    op.drop_constraint("uq_bots_create_idempotency", "bots", type_="unique")
    op.drop_column("bots", "config_identity")
    op.create_unique_constraint(
        "uq_bots_create_idempotency",
        "bots",
        [
            "account_id",
            "mode",
            "name",
            "strategy_version_id",
            "broker",
            "instrument",
            "timeframe",
            "config",
        ],
    )
