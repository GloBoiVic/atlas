"""make identical bot creates idempotent

Revision ID: 012
Revises: 011
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "012"
down_revision: str | None = "011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bots = sa.table(
        "bots",
        *[
            sa.column(name, type_)
            for name, type_ in (
                ("account_id", sa.Uuid()),
                ("mode", sa.String()),
                ("name", sa.String()),
                ("strategy_version_id", sa.Uuid()),
                ("broker", sa.String()),
                ("instrument", sa.String()),
                ("timeframe", sa.String()),
                ("config", sa.JSON()),
            )
        ],
    )
    identity_columns = list(bots.c)
    duplicate = op.get_bind().execute(
        sa.select(*identity_columns)
        .group_by(*identity_columns)
        .having(sa.func.count() > 1)
        .limit(1)
    ).first()
    if duplicate is not None:
        raise RuntimeError(
            "migration 012 found duplicate bot identities; stop affected bots and merge or "
            "remove duplicates with an operator-approved procedure before retrying"
        )
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


def downgrade() -> None:
    op.drop_constraint("uq_bots_create_idempotency", "bots", type_="unique")
