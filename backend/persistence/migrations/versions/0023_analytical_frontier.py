"""Make evaluated Strategy state and the analytical frontier one identity."""

# ruff: noqa: E501

import sqlalchemy as sa
from alembic import op

revision = "0023_analytical_frontier"
down_revision = "0022_paper_persistence_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PAPER has never been activation-authorized. Refuse to invent fingerprints
    # if an out-of-band database nevertheless contains an advanced frontier.
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM strategy_states WHERE last_evaluated_bar_end IS NOT NULL
          ) OR EXISTS (
            SELECT 1 FROM deployment_frontiers WHERE completed_m15_frontier IS NOT NULL
          ) THEN
            RAISE EXCEPTION 'cannot infer analytical bar fingerprints for existing PAPER state';
          END IF;
        END $$
        """
    )
    op.add_column(
        "strategy_states",
        sa.Column("analytical_bar_fingerprint", sa.String(64), nullable=True),
    )
    op.add_column(
        "deployment_frontiers",
        sa.Column("completed_m15_fingerprint", sa.String(64), nullable=True),
    )
    op.create_check_constraint(
        "analytical_frontier_fingerprint_pair",
        "strategy_states",
        "(last_evaluated_bar_end IS NULL) = (analytical_bar_fingerprint IS NULL)",
    )
    op.create_check_constraint(
        "valid_analytical_bar_fingerprint",
        "strategy_states",
        "analytical_bar_fingerprint IS NULL OR analytical_bar_fingerprint ~ '^[0-9a-f]{64}$'",
    )
    op.create_unique_constraint(
        "uq_strategy_states_deployment_frontier",
        "strategy_states",
        ["deployment_id", "last_evaluated_bar_end"],
    )
    op.create_check_constraint(
        "completed_m15_fingerprint_pair",
        "deployment_frontiers",
        "(completed_m15_frontier IS NULL) = (completed_m15_fingerprint IS NULL)",
    )
    op.create_check_constraint(
        "valid_completed_m15_fingerprint",
        "deployment_frontiers",
        "completed_m15_fingerprint IS NULL OR completed_m15_fingerprint ~ '^[0-9a-f]{64}$'",
    )
    op.execute(
        """
        CREATE FUNCTION atlas_validate_analytical_frontier() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          IF NEW.completed_m15_frontier IS NOT NULL AND NOT EXISTS (
            SELECT 1
            FROM strategy_states AS state
            WHERE state.deployment_id = NEW.deployment_id
              AND state.last_evaluated_bar_end = NEW.completed_m15_frontier
              AND state.analytical_bar_fingerprint = NEW.completed_m15_fingerprint
          ) THEN
            RAISE EXCEPTION 'analytical frontier requires matching persisted Strategy state';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER deployment_frontiers_strategy_state_guard
        BEFORE INSERT OR UPDATE OF completed_m15_frontier, completed_m15_fingerprint
        ON deployment_frontiers
        FOR EACH ROW EXECUTE FUNCTION atlas_validate_analytical_frontier()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS deployment_frontiers_strategy_state_guard ON deployment_frontiers"
    )
    op.execute("DROP FUNCTION IF EXISTS atlas_validate_analytical_frontier()")
    op.drop_constraint(
        "valid_completed_m15_fingerprint",
        "deployment_frontiers",
        type_="check",
    )
    op.drop_constraint(
        "completed_m15_fingerprint_pair",
        "deployment_frontiers",
        type_="check",
    )
    op.drop_constraint(
        "uq_strategy_states_deployment_frontier",
        "strategy_states",
        type_="unique",
    )
    op.drop_constraint(
        "valid_analytical_bar_fingerprint", "strategy_states", type_="check"
    )
    op.drop_constraint(
        "analytical_frontier_fingerprint_pair", "strategy_states", type_="check"
    )
    op.drop_column("deployment_frontiers", "completed_m15_fingerprint")
    op.drop_column("strategy_states", "analytical_bar_fingerprint")
