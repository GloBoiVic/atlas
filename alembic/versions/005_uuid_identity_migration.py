"""convert String(36) identity columns to native PostgreSQL UUID

Revision ID: 005
Revises: 004
Create Date: 2026-08-02

Converts existing ``String(36)`` primary-key and foreign-key columns to native
PostgreSQL ``UUID`` across ``accounts``, ``strategies``, ``strategy_versions``,
``bots``, and ``reconciliation_runs``.

* Each FK constraint is dropped before its column type is changed and recreated
  afterwards to avoid type-mismatch errors.
* ``ALTER COLUMN ... TYPE UUID USING <col>::UUID`` is the minimal safe cast for
  well-formed UUID strings.  If any row contains a non-UUID string the migration
  will fail with a clear PostgreSQL error.
* ``psql`` / Codespace PostgreSQL validation is required — SQLite cannot execute
  this migration.
"""

from collections.abc import Sequence
from typing import Final

from alembic import op

revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Tables whose id column must be converted.
_PK_TABLES: Final[tuple[str, ...]] = (
    "accounts",
    "strategies",
    "strategy_versions",
    "bots",
    "reconciliation_runs",
)

#: FK columns to convert (table, column) pairs that are NOT the PK id column.
_FK_COLUMNS: Final[tuple[tuple[str, str], ...]] = (
    # Use the actual constraint-qualified FK column references from the schema.
    ("strategy_versions", "strategy_id"),
    ("bots", "account_id"),
    ("bots", "strategy_id"),
    ("bots", "strategy_version_id"),
    ("reconciliation_runs", "account_id"),
    ("reconciliation_runs", "bot_id"),
)


def upgrade() -> None:
    # 1. Drop all FK constraints
    _drop_foreign_keys()

    # 2. Convert all PK id columns
    for table in _PK_TABLES:
        op.execute(f'ALTER TABLE {table} ALTER COLUMN id TYPE UUID USING id::UUID')

    # 3. Convert FK columns
    for table, column in _FK_COLUMNS:
        op.execute(f'ALTER TABLE {table} ALTER COLUMN {column} TYPE UUID USING {column}::UUID')

    # 4. Recreate FK constraints
    _create_foreign_keys()


def downgrade() -> None:
    # 1. Drop FK constraints
    _drop_foreign_keys()

    # 2. Convert FK columns back to String(36)
    for table, column in _FK_COLUMNS:
        op.execute(f'ALTER TABLE {table} ALTER COLUMN {column} TYPE VARCHAR(36)')

    # 3. Convert PK columns back to String(36)
    for table in reversed(_PK_TABLES):
        op.execute(f'ALTER TABLE {table} ALTER COLUMN id TYPE VARCHAR(36)')

    # 4. Recreate FK constraints
    _create_foreign_keys()


def _drop_foreign_keys() -> None:
    op.drop_constraint(
        "strategy_versions_strategy_id_fkey", "strategy_versions", type_="foreignkey"
    )
    op.drop_constraint("bots_account_id_fkey", "bots", type_="foreignkey")
    op.drop_constraint("bots_strategy_id_fkey", "bots", type_="foreignkey")
    op.drop_constraint("bots_strategy_version_id_fkey", "bots", type_="foreignkey")
    op.drop_constraint(
        "reconciliation_runs_account_id_fkey", "reconciliation_runs", type_="foreignkey"
    )
    op.drop_constraint(
        "reconciliation_runs_bot_id_fkey", "reconciliation_runs", type_="foreignkey"
    )


def _create_foreign_keys() -> None:
    op.create_foreign_key(
        "strategy_versions_strategy_id_fkey",
        "strategy_versions",
        "strategies",
        ["strategy_id"],
        ["id"],
    )
    op.create_foreign_key(
        "bots_account_id_fkey",
        "bots",
        "accounts",
        ["account_id"],
        ["id"],
    )
    op.create_foreign_key(
        "bots_strategy_id_fkey",
        "bots",
        "strategies",
        ["strategy_id"],
        ["id"],
    )
    op.create_foreign_key(
        "bots_strategy_version_id_fkey",
        "bots",
        "strategy_versions",
        ["strategy_version_id"],
        ["id"],
    )
    op.create_foreign_key(
        "reconciliation_runs_account_id_fkey",
        "reconciliation_runs",
        "accounts",
        ["account_id"],
        ["id"],
    )
    op.create_foreign_key(
        "reconciliation_runs_bot_id_fkey",
        "reconciliation_runs",
        "bots",
        ["bot_id"],
        ["id"],
    )
