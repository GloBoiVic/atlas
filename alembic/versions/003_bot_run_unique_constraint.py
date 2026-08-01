"""add one bot run per bot constraint

Revision ID: 003
Revises: 002
Create Date: 2026-08-01
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import context, op

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONSTRAINT_NAME = "uq_bot_runs_bot_id"


def _constraint_exists(offline_default: bool) -> bool:
    if context.is_offline_mode():
        return offline_default
    bind = op.get_bind()
    return any(
        constraint.get("name") == CONSTRAINT_NAME
        for constraint in sa.inspect(bind).get_unique_constraints("bot_runs")
    )


def upgrade() -> None:
    if not _constraint_exists(False):
        op.create_unique_constraint(CONSTRAINT_NAME, "bot_runs", ["bot_id"])


def downgrade() -> None:
    if _constraint_exists(True):
        op.drop_constraint(CONSTRAINT_NAME, "bot_runs", type_="unique")
