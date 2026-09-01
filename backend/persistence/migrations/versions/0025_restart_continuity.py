"""Enforce Deployment and StrategyVersion continuity for PAPER state."""

from alembic import op

revision = "0025_restart_continuity"
down_revision = "0024_authorization_fence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_deployments_id_strategy_version",
        "deployments",
        ["id", "strategy_version_id"],
    )
    op.create_index(
        "ix_strategy_states_deployment_strategy_version",
        "strategy_states",
        ["deployment_id", "strategy_version_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_strategy_states_deployment_strategy_version",
        "strategy_states",
        "deployments",
        ["deployment_id", "strategy_version_id"],
        ["id", "strategy_version_id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_strategy_states_deployment_strategy_version",
        "strategy_states",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_strategy_states_deployment_strategy_version",
        table_name="strategy_states",
    )
    op.drop_constraint(
        "uq_deployments_id_strategy_version",
        "deployments",
        type_="unique",
    )
