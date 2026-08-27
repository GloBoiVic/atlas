"""Persist state and reason for every headline metric."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql.elements import conv


revision = "0014_result_metric_state_details"
down_revision = "0008_proposal_constraints"
branch_labels = None
depends_on = None


_LEGACY = (
    "jsonb_build_object(",
    "'net_return', jsonb_build_object('state', 'LEGACY_UNCOMPUTED', 'reason', 'LEGACY_RESULT'),",
    "'max_drawdown_amount', jsonb_build_object('state', 'LEGACY_UNCOMPUTED', 'reason', 'LEGACY_RESULT'),",
    "'max_drawdown_percent', jsonb_build_object('state', 'LEGACY_UNCOMPUTED', 'reason', 'LEGACY_RESULT'),",
    "'sharpe_ratio', jsonb_build_object('state', metric_states->>'sharpe_ratio', 'reason', 'LEGACY_RESULT'),",
    "'profit_factor', jsonb_build_object('state', metric_states->>'profit_factor', 'reason', 'LEGACY_RESULT'),",
    "'win_rate', jsonb_build_object('state', metric_states->>'win_rate', 'reason', 'LEGACY_RESULT'),",
    "'expectancy_net_pnl', jsonb_build_object('state', metric_states->>'expectancy_net_pnl', 'reason', 'LEGACY_RESULT')",
    ")",
)

# The repository metadata naming convention expands explicit check names to
# ``ck_<table>_<constraint_name>`` when Alembic attaches them to the table.
# Keep the physical names here so both directions address the constraints that
# PostgreSQL actually stores.
_METRIC_STATE_KEYS_CONSTRAINT = "ck_experiment_results_result_metric_state_keys"
_METRIC_STATE_CONSISTENCY_CONSTRAINT = (
    "ck_experiment_results_result_metric_state_consistency"
)
_METRIC_STATE_KEYS_LOGICAL_NAME = "result_metric_state_keys"
_METRIC_STATE_CONSISTENCY_LOGICAL_NAME = "result_metric_state_consistency"


def upgrade() -> None:
    op.drop_constraint(
        conv(_METRIC_STATE_CONSISTENCY_CONSTRAINT), "experiment_results", type_="check"
    )
    op.drop_constraint(
        conv(_METRIC_STATE_KEYS_CONSTRAINT), "experiment_results", type_="check"
    )
    op.execute(
        "UPDATE experiment_results SET metric_states = "
        + " ".join(_LEGACY)
        + " WHERE jsonb_typeof(metric_states->'sharpe_ratio') = 'string'"
    )
    op.create_check_constraint(
        _METRIC_STATE_KEYS_LOGICAL_NAME,
        "experiment_results",
        "jsonb_typeof(metric_states) = 'object' AND metric_states ?& ARRAY['net_return', 'max_drawdown_amount', 'max_drawdown_percent', 'sharpe_ratio', 'profit_factor', 'win_rate', 'expectancy_net_pnl'] AND (metric_states->'net_return'->>'state') IN ('VALUE', 'INFINITE', 'UNAVAILABLE', 'LEGACY_UNCOMPUTED') AND (metric_states->'max_drawdown_amount'->>'state') IN ('VALUE', 'INFINITE', 'UNAVAILABLE', 'LEGACY_UNCOMPUTED') AND (metric_states->'max_drawdown_percent'->>'state') IN ('VALUE', 'INFINITE', 'UNAVAILABLE', 'LEGACY_UNCOMPUTED') AND (metric_states->'sharpe_ratio'->>'state') IN ('VALUE', 'INFINITE', 'UNAVAILABLE', 'LEGACY_UNCOMPUTED') AND (metric_states->'profit_factor'->>'state') IN ('VALUE', 'INFINITE', 'UNAVAILABLE', 'LEGACY_UNCOMPUTED') AND (metric_states->'win_rate'->>'state') IN ('VALUE', 'INFINITE', 'UNAVAILABLE', 'LEGACY_UNCOMPUTED') AND (metric_states->'expectancy_net_pnl'->>'state') IN ('VALUE', 'INFINITE', 'UNAVAILABLE', 'LEGACY_UNCOMPUTED')",
    )
    op.create_check_constraint(
        _METRIC_STATE_CONSISTENCY_LOGICAL_NAME,
        "experiment_results",
        "(metric_states->'profit_factor'->>'state' = 'INFINITE' AND profit_factor IS NULL) OR (metric_states->'profit_factor'->>'state' <> 'INFINITE')",
    )


def downgrade() -> None:
    op.drop_constraint(
        conv(_METRIC_STATE_CONSISTENCY_CONSTRAINT), "experiment_results", type_="check"
    )
    op.drop_constraint(
        conv(_METRIC_STATE_KEYS_CONSTRAINT), "experiment_results", type_="check"
    )
    op.execute("UPDATE experiment_results SET metric_states = jsonb_build_object('sharpe_ratio', metric_states->'sharpe_ratio'->>'state', 'profit_factor', metric_states->'profit_factor'->>'state', 'win_rate', metric_states->'win_rate'->>'state', 'expectancy_net_pnl', metric_states->'expectancy_net_pnl'->>'state')")
    op.create_check_constraint(
        _METRIC_STATE_KEYS_LOGICAL_NAME,
        "experiment_results",
        "jsonb_typeof(metric_states) = 'object' AND metric_states ?& ARRAY['sharpe_ratio', 'profit_factor', 'win_rate', 'expectancy_net_pnl'] AND (metric_states->>'sharpe_ratio') IN ('VALUE', 'INFINITE', 'UNAVAILABLE', 'LEGACY_UNCOMPUTED') AND (metric_states->>'profit_factor') IN ('VALUE', 'INFINITE', 'UNAVAILABLE', 'LEGACY_UNCOMPUTED') AND (metric_states->>'win_rate') IN ('VALUE', 'INFINITE', 'UNAVAILABLE', 'LEGACY_UNCOMPUTED') AND (metric_states->>'expectancy_net_pnl') IN ('VALUE', 'INFINITE', 'UNAVAILABLE', 'LEGACY_UNCOMPUTED')",
    )
    op.create_check_constraint(
        _METRIC_STATE_CONSISTENCY_LOGICAL_NAME,
        "experiment_results",
        "(metric_states->>'profit_factor' = 'INFINITE' AND profit_factor IS NULL) OR (metric_states->>'profit_factor' <> 'INFINITE')",
    )
