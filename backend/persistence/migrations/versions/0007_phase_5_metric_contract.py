"""Add the Phase 5 result metric contract without changing historical facts."""

# fmt: off
# ruff: noqa: E501

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007_phase_5_metric_contract"
down_revision = "0006_phase_4_persistence"
branch_labels = None
depends_on = None

NUMERIC = sa.Numeric(24, 10)
LEGACY_STATES = "'{\"sharpe_ratio\": \"LEGACY_UNCOMPUTED\", \"profit_factor\": \"LEGACY_UNCOMPUTED\", \"win_rate\": \"LEGACY_UNCOMPUTED\", \"expectancy_net_pnl\": \"LEGACY_UNCOMPUTED\"}'::jsonb"


def upgrade() -> None:
    op.add_column("experiment_results", sa.Column("sharpe_ratio", NUMERIC, nullable=True))
    op.add_column("experiment_results", sa.Column("profit_factor", NUMERIC, nullable=True))
    op.add_column("experiment_results", sa.Column("win_rate", NUMERIC, nullable=True))
    op.add_column("experiment_results", sa.Column("expectancy_net_pnl", NUMERIC, nullable=True))
    op.add_column(
        "experiment_results",
        sa.Column("metric_states", postgresql.JSONB, server_default=sa.text(LEGACY_STATES), nullable=False),
    )
    op.add_column(
        "experiment_results",
        sa.Column("metric_schema_version", sa.String(100), server_default=sa.text("'LEGACY_UNCOMPUTED'"), nullable=False),
    )
    op.create_check_constraint(
        "result_metric_state_keys",
        "experiment_results",
        "jsonb_typeof(metric_states) = 'object' AND metric_states ?& ARRAY['sharpe_ratio', 'profit_factor', 'win_rate', 'expectancy_net_pnl'] AND (metric_states->>'sharpe_ratio') IN ('VALUE', 'INFINITE', 'UNAVAILABLE', 'LEGACY_UNCOMPUTED') AND (metric_states->>'profit_factor') IN ('VALUE', 'INFINITE', 'UNAVAILABLE', 'LEGACY_UNCOMPUTED') AND (metric_states->>'win_rate') IN ('VALUE', 'INFINITE', 'UNAVAILABLE', 'LEGACY_UNCOMPUTED') AND (metric_states->>'expectancy_net_pnl') IN ('VALUE', 'INFINITE', 'UNAVAILABLE', 'LEGACY_UNCOMPUTED')",
    )
    for column in ("sharpe_ratio", "profit_factor", "win_rate", "expectancy_net_pnl"):
        op.create_check_constraint(
            f"result_{column}_finite",
            "experiment_results",
            f"{column} IS NULL OR ({column} <> 'NaN'::numeric AND {column} <> 'Infinity'::numeric AND {column} <> '-Infinity'::numeric)",
        )
    op.create_check_constraint("result_profit_factor_nonnegative", "experiment_results", "profit_factor IS NULL OR profit_factor >= 0")
    op.create_check_constraint("result_win_rate_range", "experiment_results", "win_rate IS NULL OR (win_rate >= 0 AND win_rate <= 1)")
    op.create_check_constraint(
        "result_metric_state_consistency",
        "experiment_results",
        "(metric_states->>'profit_factor' = 'INFINITE' AND profit_factor IS NULL) OR (metric_states->>'profit_factor' <> 'INFINITE')",
    )
    op.create_check_constraint(
        "result_phase5_metric_schema",
        "experiment_results",
        "result_schema_version NOT LIKE 'PHASE5_%' OR metric_schema_version <> 'LEGACY_UNCOMPUTED'",
    )
    op.create_index("ix_experiments_created_at_id_desc", "experiments", [sa.text("created_at DESC"), sa.text("id DESC")])


def downgrade() -> None:
    op.drop_index("ix_experiments_created_at_id_desc", table_name="experiments")
    for name in (
        "result_phase5_metric_schema",
        "result_metric_state_consistency",
        "result_win_rate_range",
        "result_profit_factor_nonnegative",
        "result_expectancy_net_pnl_finite",
        "result_win_rate_finite",
        "result_profit_factor_finite",
        "result_sharpe_ratio_finite",
        "result_metric_state_keys",
    ):
        op.drop_constraint(name, "experiment_results", type_="check")
    op.drop_column("experiment_results", "metric_schema_version")
    op.drop_column("experiment_results", "metric_states")
    for name in ("expectancy_net_pnl", "win_rate", "profit_factor", "sharpe_ratio"):
        op.drop_column("experiment_results", name)
