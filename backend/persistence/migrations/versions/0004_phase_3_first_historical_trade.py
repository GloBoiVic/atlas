"""Phase 3 Experiment and first historical trade persistence."""

# fmt: off
# ruff: noqa: E501

from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004_phase_3_first_trade"
down_revision = "0003_phase_2_market_data"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
NUMERIC = sa.Numeric(24, 10)
PRICE = sa.Numeric(20, 10)
TS = sa.DateTime(timezone=True)


def _id() -> sa.Column[Any]:
    return sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False)


def _fk(column: str, target: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint([column], [target], ondelete="RESTRICT")


def upgrade() -> None:
    op.create_table(
        "experiments", _id(),
        sa.Column("strategy_version_id", UUID, nullable=False),
        sa.Column("dataset_snapshot_id", UUID, nullable=False),
        sa.Column("venue_instrument_id", UUID, nullable=False),
        sa.Column("status", sa.String(20), server_default=sa.text("'RUNNING'"), nullable=False),
        sa.Column("trading_start", TS, nullable=False), sa.Column("trading_end", TS, nullable=False),
        sa.Column("starting_capital", NUMERIC, nullable=False), sa.Column("risk_per_trade", sa.Numeric(12, 10), nullable=False),
        sa.Column("parameter_snapshot", postgresql.JSONB, nullable=False), sa.Column("risk_config", postgresql.JSONB, nullable=False),
        sa.Column("simulation_config", postgresql.JSONB, nullable=False), sa.Column("model_version", sa.String(100), nullable=False),
         sa.Column("created_at", TS, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False), sa.Column("completed_at", TS),
        sa.CheckConstraint("status IN ('RUNNING', 'COMPLETED', 'FAILED')", name="valid_status"),
        sa.CheckConstraint("trading_end > trading_start", name="valid_trading_range"),
        sa.CheckConstraint("starting_capital > 0 AND starting_capital <> 'NaN'::numeric", name="positive_starting_capital"),
        sa.CheckConstraint("risk_per_trade > 0 AND risk_per_trade < 1 AND risk_per_trade <> 'NaN'::numeric", name="valid_risk_per_trade"),
        sa.CheckConstraint("(status = 'RUNNING' AND completed_at IS NULL) OR (status IN ('COMPLETED', 'FAILED') AND completed_at IS NOT NULL)", name="status_completion_consistency"),
        _fk("strategy_version_id", "strategy_versions.id"), _fk("dataset_snapshot_id", "dataset_snapshots.id"), _fk("venue_instrument_id", "venue_instruments.id"),
        sa.PrimaryKeyConstraint("id", name="pk_experiments"),
    )
    op.create_table(
        "experiment_accounts", sa.Column("experiment_id", UUID, nullable=False), sa.Column("base_currency", sa.String(3), server_default=sa.text("'USD'"), nullable=False),
        sa.Column("starting_capital", NUMERIC, nullable=False), sa.Column("realized_pnl", NUMERIC, server_default=sa.text("0"), nullable=False),
        sa.Column("unrealized_pnl", NUMERIC, server_default=sa.text("0"), nullable=False), sa.Column("equity", NUMERIC, nullable=False),
        sa.Column("updated_at", TS, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("base_currency = 'USD'", name="phase_3_base_currency"), sa.CheckConstraint("starting_capital > 0 AND starting_capital <> 'NaN'::numeric", name="positive_starting_capital"),
        sa.CheckConstraint("realized_pnl <> 'NaN'::numeric AND unrealized_pnl <> 'NaN'::numeric AND equity <> 'NaN'::numeric", name="finite_account_values"),
        _fk("experiment_id", "experiments.id"), sa.PrimaryKeyConstraint("experiment_id", name="pk_experiment_accounts"),
    )
    op.create_table(
        "trade_intents", _id(), sa.Column("experiment_id", UUID, nullable=False), sa.Column("strategy_version_id", UUID, nullable=False), sa.Column("venue_instrument_id", UUID, nullable=False),
        sa.Column("decision_frontier", TS, nullable=False), sa.Column("action", sa.String(30), nullable=False), sa.Column("direction", sa.String(5)), sa.Column("proposed_stop", PRICE), sa.Column("target_multiple", sa.Numeric(12, 10)), sa.Column("rationale", postgresql.JSONB, nullable=False), sa.Column("created_at", TS, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("action IN ('OPEN_LONG', 'OPEN_SHORT', 'CLOSE_POSITION', 'UPDATE_PROTECTION')", name="valid_action"), sa.CheckConstraint("direction IS NULL OR direction IN ('LONG', 'SHORT')", name="valid_direction"), sa.CheckConstraint("proposed_stop IS NULL OR (proposed_stop > 0 AND proposed_stop <> 'NaN'::numeric)", name="positive_stop"),
        _fk("experiment_id", "experiments.id"), _fk("strategy_version_id", "strategy_versions.id"), _fk("venue_instrument_id", "venue_instruments.id"), sa.PrimaryKeyConstraint("id", name="pk_trade_intents"), sa.UniqueConstraint("experiment_id", "decision_frontier", name="uq_trade_intents_experiment_frontier"),
    )
    op.create_table(
        "risk_decisions", _id(), sa.Column("trade_intent_id", UUID, nullable=False), sa.Column("phase", sa.String(20), nullable=False), sa.Column("outcome", sa.String(10), nullable=False), sa.Column("quantity", NUMERIC), sa.Column("entry_price", PRICE), sa.Column("stop_price", PRICE), sa.Column("target_price", PRICE), sa.Column("risk_budget", NUMERIC), sa.Column("quote_bid", PRICE), sa.Column("quote_ask", PRICE), sa.Column("rejection_code", sa.String(80)), sa.Column("evaluated_at", TS, nullable=False),
        sa.CheckConstraint("phase IN ('PRE_FLIGHT', 'PRE_SUBMISSION')", name="valid_phase"), sa.CheckConstraint("outcome IN ('APPROVED', 'REJECTED')", name="valid_outcome"), sa.CheckConstraint("quantity IS NULL OR (quantity > 0 AND quantity <> 'NaN'::numeric)", name="positive_quantity"), _fk("trade_intent_id", "trade_intents.id"), sa.PrimaryKeyConstraint("id", name="pk_risk_decisions"), sa.UniqueConstraint("trade_intent_id", "phase", name="uq_risk_decisions_intent_phase"),
    )
    op.create_table(
        "orders", _id(), sa.Column("experiment_id", UUID, nullable=False), sa.Column("trade_intent_id", UUID, nullable=False), sa.Column("risk_decision_id", UUID, nullable=False), sa.Column("order_type", sa.String(10), nullable=False), sa.Column("purpose", sa.String(25), nullable=False), sa.Column("direction", sa.String(5), nullable=False), sa.Column("quantity", NUMERIC, nullable=False), sa.Column("requested_price", PRICE), sa.Column("current_status", sa.String(25), server_default=sa.text("'PENDING_SUBMISSION'"), nullable=False), sa.Column("client_correlation_id", sa.String(100), nullable=False), sa.Column("created_at", TS, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False), sa.Column("submitted_at", TS),
        sa.CheckConstraint("order_type IN ('MARKET', 'STOP', 'LIMIT')", name="valid_order_type"), sa.CheckConstraint("purpose IN ('ENTRY', 'EXIT', 'STOP_LOSS', 'TAKE_PROFIT', 'PROTECTION_UPDATE')", name="valid_purpose"), sa.CheckConstraint("current_status IN ('PENDING_SUBMISSION', 'SUBMITTED', 'FILLED', 'CANCELED', 'REJECTED', 'EXPIRED', 'UNKNOWN')", name="valid_status"), sa.CheckConstraint("quantity > 0 AND quantity <> 'NaN'::numeric", name="positive_quantity"), _fk("experiment_id", "experiments.id"), _fk("trade_intent_id", "trade_intents.id"), _fk("risk_decision_id", "risk_decisions.id"), sa.PrimaryKeyConstraint("id", name="pk_orders"), sa.UniqueConstraint("client_correlation_id", name="uq_orders_client_correlation_id"),
    )
    op.create_table(
        "fills", _id(), sa.Column("order_id", UUID, nullable=False), sa.Column("sequence_number", sa.Integer, nullable=False), sa.Column("quantity", NUMERIC, nullable=False), sa.Column("execution_price", PRICE, nullable=False), sa.Column("executed_at", TS, nullable=False), sa.Column("external_execution_id", sa.String(200)), sa.Column("fee", NUMERIC, server_default=sa.text("0"), nullable=False),
        sa.CheckConstraint("sequence_number > 0", name="positive_sequence"), sa.CheckConstraint("quantity > 0 AND quantity <> 'NaN'::numeric AND execution_price > 0 AND execution_price <> 'NaN'::numeric", name="positive_financials"), _fk("order_id", "orders.id"), sa.PrimaryKeyConstraint("id", name="pk_fills"), sa.UniqueConstraint("order_id", "sequence_number", name="uq_fills_order_sequence"), sa.UniqueConstraint("external_execution_id", name="uq_fills_external_execution_id"),
    )
    op.create_table(
        "positions", _id(), sa.Column("experiment_id", UUID, nullable=False), sa.Column("venue_instrument_id", UUID, nullable=False), sa.Column("state", sa.String(5), server_default=sa.text("'FLAT'"), nullable=False), sa.Column("quantity", NUMERIC), sa.Column("entry_price", PRICE), sa.Column("opened_at", TS), sa.Column("updated_at", TS, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("state IN ('FLAT', 'LONG', 'SHORT')", name="valid_state"), sa.CheckConstraint("(state = 'FLAT' AND quantity IS NULL AND entry_price IS NULL AND opened_at IS NULL) OR (state IN ('LONG', 'SHORT') AND quantity > 0 AND entry_price > 0 AND opened_at IS NOT NULL)", name="state_exposure_consistency"), _fk("experiment_id", "experiments.id"), _fk("venue_instrument_id", "venue_instruments.id"), sa.PrimaryKeyConstraint("id", name="pk_positions"), sa.UniqueConstraint("experiment_id", "venue_instrument_id", name="uq_positions_experiment_instrument"),
    )
    op.create_table(
        "trades", _id(), sa.Column("experiment_id", UUID, nullable=False), sa.Column("trade_intent_id", UUID, nullable=False), sa.Column("entry_order_id", UUID, nullable=False), sa.Column("exit_order_id", UUID), sa.Column("sequence_number", sa.Integer, server_default=sa.text("1"), nullable=False), sa.Column("direction", sa.String(5), nullable=False), sa.Column("status", sa.String(10), server_default=sa.text("'OPEN'"), nullable=False), sa.Column("quantity", NUMERIC, nullable=False), sa.Column("entry_price", PRICE, nullable=False), sa.Column("exit_price", PRICE), sa.Column("opened_at", TS, nullable=False), sa.Column("closed_at", TS), sa.Column("gross_pnl", NUMERIC), sa.Column("exit_reason", sa.String(30)),
        sa.CheckConstraint("direction IN ('LONG', 'SHORT')", name="valid_direction"), sa.CheckConstraint("status IN ('OPEN', 'COMPLETED')", name="valid_status"), sa.CheckConstraint("quantity > 0 AND quantity <> 'NaN'::numeric AND entry_price > 0 AND entry_price <> 'NaN'::numeric", name="positive_entry_financials"), sa.CheckConstraint("status = 'OPEN' OR (exit_price IS NOT NULL AND closed_at IS NOT NULL AND gross_pnl IS NOT NULL)", name="completed_trade_facts"), _fk("experiment_id", "experiments.id"), _fk("trade_intent_id", "trade_intents.id"), _fk("entry_order_id", "orders.id"), _fk("exit_order_id", "orders.id"), sa.PrimaryKeyConstraint("id", name="pk_trades"), sa.UniqueConstraint("experiment_id", "sequence_number", name="uq_trades_experiment_sequence"),
    )

    op.execute("""CREATE FUNCTION prevent_experiment_config_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'experiments are immutable'; END IF; IF (to_jsonb(OLD) - ARRAY['status','completed_at']) IS DISTINCT FROM (to_jsonb(NEW) - ARRAY['status','completed_at']) THEN RAISE EXCEPTION 'experiment configuration is immutable'; END IF; IF OLD.status IN ('COMPLETED','FAILED') AND (OLD.status, OLD.completed_at) IS DISTINCT FROM (NEW.status, NEW.completed_at) THEN RAISE EXCEPTION 'terminal experiment is immutable'; END IF; RETURN NEW; END; $$""")
    op.execute("CREATE TRIGGER experiments_immutable_config BEFORE UPDATE OR DELETE ON experiments FOR EACH ROW EXECUTE FUNCTION prevent_experiment_config_mutation()")
    op.execute("""CREATE FUNCTION prevent_completed_trade_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF TG_OP = 'DELETE' OR OLD.status = 'COMPLETED' THEN RAISE EXCEPTION 'completed trades are immutable'; END IF; RETURN NEW; END; $$""")
    op.execute("CREATE TRIGGER trades_terminal_guard BEFORE UPDATE OR DELETE ON trades FOR EACH ROW EXECUTE FUNCTION prevent_completed_trade_mutation()")
    op.execute("""CREATE FUNCTION prevent_order_fact_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF TG_OP = 'DELETE' OR (to_jsonb(OLD) - ARRAY['current_status','submitted_at']) IS DISTINCT FROM (to_jsonb(NEW) - ARRAY['current_status','submitted_at']) THEN RAISE EXCEPTION 'order facts are immutable'; END IF; RETURN NEW; END; $$""")
    op.execute("CREATE TRIGGER orders_fact_guard BEFORE UPDATE OR DELETE ON orders FOR EACH ROW EXECUTE FUNCTION prevent_order_fact_mutation()")
    op.execute("""CREATE FUNCTION prevent_fact_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'historical facts are immutable'; END; $$""")
    for table in ("trade_intents", "risk_decisions", "fills"):
        op.execute(f"CREATE TRIGGER {table}_append_only BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION prevent_fact_mutation()")


def downgrade() -> None:
    for table in ("trades", "positions", "fills", "orders", "risk_decisions", "trade_intents"):
        op.execute(f"DROP TRIGGER {table}_append_only ON {table}") if table in ("fills", "risk_decisions", "trade_intents") else None
    op.execute("DROP TRIGGER trades_terminal_guard ON trades")
    op.execute("DROP FUNCTION prevent_completed_trade_mutation()")
    op.execute("DROP TRIGGER orders_fact_guard ON orders")
    op.execute("DROP FUNCTION prevent_order_fact_mutation()")
    op.execute("DROP TRIGGER experiments_immutable_config ON experiments")
    op.execute("DROP FUNCTION prevent_experiment_config_mutation()")
    op.execute("DROP FUNCTION prevent_fact_mutation()")
    for table in ("trades", "positions", "fills", "orders", "risk_decisions", "trade_intents", "experiment_accounts", "experiments"):
        op.drop_table(table)
