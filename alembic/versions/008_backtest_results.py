"""Persist isolated backtest runs and completed trade projections."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "backtest_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("strategy_name", sa.String(255), nullable=False),
        sa.Column("strategy_version", sa.String(50), nullable=False),
        sa.Column("strategy_commit_sha", sa.String(64), nullable=False),
        sa.Column("strategy_parameters", postgresql.JSONB, nullable=False),
        sa.Column("instrument_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("symbol", sa.String(50), nullable=False),
        sa.Column("timeframe", sa.String(10), nullable=False),
        sa.Column("data_source", sa.String(255), nullable=False),
        sa.Column("dataset_id", sa.String(255), nullable=False),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("risk_config", postgresql.JSONB, nullable=False),
        sa.Column("execution_config", postgresql.JSONB, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("fill_model", sa.String(100), nullable=False, server_default="next_candle_open"),
        sa.Column("total_return", sa.Numeric(28, 12)),
        sa.Column("total_pnl", sa.Numeric(28, 12)),
        sa.Column("starting_equity", sa.Numeric(28, 12)),
        sa.Column("ending_equity", sa.Numeric(28, 12)),
        sa.Column("win_rate", sa.Float()),
        sa.Column("sharpe_ratio", sa.Float()),
        sa.Column("max_drawdown", sa.Numeric(28, 12)),
        sa.Column("profit_factor", sa.Float()),
        sa.Column("total_trades", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("winning_trades", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("losing_trades", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text()),
        sa.Column("last_processed_timestamp", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_backtest_status", "backtest_runs", ["status"])
    op.create_table(
        "backtest_trades",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("backtest_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("instrument_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("symbol", sa.String(50), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("entry_price", sa.Numeric(28, 12), nullable=False),
        sa.Column("exit_price", sa.Numeric(28, 12)),
        sa.Column("quantity", sa.Numeric(28, 12), nullable=False),
        sa.Column("pnl", sa.Numeric(28, 12)),
        sa.Column("entry_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exit_time", sa.DateTime(timezone=True)),
        sa.Column("signal_metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["backtest_run_id"], ["backtest_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_backtest_trades_run", "backtest_trades", ["backtest_run_id"])


def downgrade() -> None:
    op.drop_index("idx_backtest_trades_run", table_name="backtest_trades")
    op.drop_table("backtest_trades")
    op.drop_index("idx_backtest_status", table_name="backtest_runs")
    op.drop_table("backtest_runs")
