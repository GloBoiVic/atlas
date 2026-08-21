"""Phase 4 historical execution persistence contract."""

# fmt: off
# ruff: noqa: E501

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006_phase_4_persistence"
down_revision = "0005_phase_3_failure_persistence"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
NUMERIC = sa.Numeric(24, 10)
PRICE = sa.Numeric(20, 10)
TS = sa.DateTime(timezone=True)


def _fk(column: str, target: str, ondelete: str = "RESTRICT") -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint([column], [target], ondelete=ondelete)


def upgrade() -> None:
    op.drop_constraint("valid_status", "experiments", type_="check")
    op.drop_constraint("status_completion_consistency", "experiments", type_="check")
    op.create_check_constraint("valid_status", "experiments", "status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED')")
    op.create_check_constraint("status_completion_consistency", "experiments", "(status IN ('PENDING', 'RUNNING') AND completed_at IS NULL) OR (status IN ('COMPLETED', 'FAILED') AND completed_at IS NOT NULL)")
    op.alter_column("experiments", "status", server_default=sa.text("'PENDING'"))

    op.add_column("risk_decisions", sa.Column("actual_risk", NUMERIC, nullable=True))
    op.create_check_constraint("phase_4_actual_risk", "risk_decisions", "actual_risk IS NULL OR (actual_risk >= 0 AND actual_risk <> 'NaN'::numeric)")

    op.add_column("orders", sa.Column("parent_entry_order_id", UUID, nullable=True))
    op.create_foreign_key("fk_orders_parent_entry_order_id_orders", "orders", "orders", ["parent_entry_order_id"], ["id"], ondelete="RESTRICT")
    op.create_unique_constraint("uq_orders_parent_purpose", "orders", ["parent_entry_order_id", "purpose"])

    op.add_column("fills", sa.Column("source_market_bar_id", UUID, nullable=True))
    op.add_column("fills", sa.Column("price_basis", sa.String(20), nullable=True))
    op.add_column("fills", sa.Column("executable_reference_price", PRICE, nullable=True))
    op.add_column("fills", sa.Column("slippage_per_unit", PRICE, nullable=True))
    op.add_column("fills", sa.Column("slippage_cost", NUMERIC, nullable=True))
    op.create_foreign_key("fk_fills_source_market_bar_id_market_bars", "fills", "market_bars", ["source_market_bar_id"], ["id"], ondelete="RESTRICT")
    op.create_check_constraint("phase_4_price_basis", "fills", "price_basis IS NULL OR price_basis IN ('OPEN', 'OPEN_GAP', 'INTRABAR_STOP', 'INTRABAR_TARGET', 'END_CLOSE')")

    op.drop_constraint("completed_trade_facts", "trades", type_="check")
    op.create_check_constraint("completed_trade_facts", "trades", "status = 'OPEN' OR (exit_price IS NOT NULL AND closed_at IS NOT NULL AND gross_pnl IS NOT NULL)")
    for name, column in (("initial_risk", NUMERIC), ("commission_cost", NUMERIC), ("financing_cost", NUMERIC), ("net_pnl", NUMERIC), ("r_multiple", NUMERIC)):
        op.add_column("trades", sa.Column(name, column, nullable=True))
    op.add_column("trades", sa.Column("intrabar_ambiguous", sa.Boolean, server_default=sa.text("false"), nullable=False))
    op.add_column("trades", sa.Column("ambiguity_policy", sa.String(80), nullable=True))
    op.add_column("trades", sa.Column("ambiguity_observed_at", TS, nullable=True))
    op.add_column("trades", sa.Column("ambiguity_source_market_bar_id", UUID, nullable=True))
    op.create_foreign_key("fk_trades_ambiguity_source_market_bar_id_market_bars", "trades", "market_bars", ["ambiguity_source_market_bar_id"], ["id"], ondelete="RESTRICT")
    op.create_check_constraint("phase_4_exit_reason", "trades", "exit_reason IS NULL OR exit_reason IN ('TAKE_PROFIT', 'STOP_LOSS', 'END_OF_EXPERIMENT')")
    op.create_check_constraint("phase_4_financing_excluded", "trades", "financing_cost IS NULL OR financing_cost = 0")

    op.create_table(
        "order_events",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("order_id", UUID, nullable=False), sa.Column("sequence_number", sa.Integer, nullable=False),
        sa.Column("event_type", sa.String(30), nullable=False), sa.Column("occurred_at", TS, nullable=False),
        sa.Column("source_market_bar_id", UUID, nullable=True), sa.Column("details", postgresql.JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.CheckConstraint("sequence_number > 0", name="positive_sequence"),
        sa.CheckConstraint("event_type IN ('ORDER_CREATED', 'ORDER_SUBMITTED', 'ORDER_FILLED', 'ORDER_CANCELED')", name="valid_event_type"),
        _fk("order_id", "orders.id"), _fk("source_market_bar_id", "market_bars.id"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("order_id", "sequence_number", name="uq_order_events_order_sequence"),
    )
    op.create_table(
        "experiment_equity_points",
        sa.Column("experiment_id", UUID, nullable=False), sa.Column("sequence_number", sa.Integer, nullable=False),
        sa.Column("observed_at", TS, nullable=False), sa.Column("balance", NUMERIC, nullable=False),
        sa.Column("realized_pnl", NUMERIC, nullable=False), sa.Column("unrealized_pnl", NUMERIC, nullable=False),
        sa.Column("equity", NUMERIC, nullable=False), sa.Column("running_peak", NUMERIC, nullable=False),
        sa.Column("drawdown_amount", NUMERIC, nullable=False), sa.Column("drawdown_percent", NUMERIC, nullable=False),
        sa.Column("valuation_bid", PRICE), sa.Column("valuation_ask", PRICE),
        sa.Column("source_bid_market_bar_id", UUID), sa.Column("source_ask_market_bar_id", UUID),
        _fk("experiment_id", "experiments.id"), _fk("source_bid_market_bar_id", "market_bars.id"), _fk("source_ask_market_bar_id", "market_bars.id"),
        sa.PrimaryKeyConstraint("experiment_id", "sequence_number"), sa.UniqueConstraint("experiment_id", "observed_at", name="uq_equity_points_experiment_time"),
    )
    op.create_table(
        "experiment_results",
        sa.Column("experiment_id", UUID, nullable=False), sa.Column("result_schema_version", sa.String(100), nullable=False),
        sa.Column("trade_count", sa.Integer, nullable=False), sa.Column("ambiguous_trade_count", sa.Integer, nullable=False),
        sa.Column("gross_pnl", NUMERIC, nullable=False), sa.Column("commission_cost", NUMERIC, nullable=False),
        sa.Column("financing_cost", NUMERIC), sa.Column("modeled_net_pnl", NUMERIC, nullable=False),
        sa.Column("ending_balance", NUMERIC, nullable=False), sa.Column("ending_equity", NUMERIC, nullable=False),
        sa.Column("net_return", NUMERIC, nullable=False), sa.Column("max_drawdown_amount", NUMERIC, nullable=False),
        sa.Column("max_drawdown_percent", NUMERIC, nullable=False), sa.Column("financing_disclosure", sa.String(100), nullable=False),
        sa.Column("completed_market_time", TS, nullable=False), sa.Column("output_fingerprint", sa.String(64), nullable=False),
        _fk("experiment_id", "experiments.id"), sa.PrimaryKeyConstraint("experiment_id"),
        sa.CheckConstraint("output_fingerprint ~ '^[0-9a-f]{64}$'", name="sha256_output_fingerprint"),
        sa.CheckConstraint("financing_cost IS NULL OR financing_cost = 0", name="financing_excluded"),
    )

    # Legacy Phase 3 inserts omitted status and are intentionally retained as RUNNING.
    op.execute("""CREATE OR REPLACE FUNCTION phase_4_experiment_insert_compat() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.model_version <> 'PHASE4_HISTORICAL_EXECUTION_V1' AND NEW.status = 'PENDING' THEN NEW.status := 'RUNNING'; END IF; RETURN NEW; END; $$""")
    op.execute("CREATE TRIGGER experiments_phase_4_insert_compat BEFORE INSERT ON experiments FOR EACH ROW EXECUTE FUNCTION phase_4_experiment_insert_compat()")
    op.execute("DROP TRIGGER experiments_immutable_config ON experiments")
    op.execute("DROP FUNCTION prevent_experiment_config_mutation()")
    op.execute("""CREATE FUNCTION prevent_experiment_config_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'experiments are immutable'; END IF; IF OLD.status IN ('COMPLETED','FAILED') AND (to_jsonb(OLD) - ARRAY['status','completed_at']) IS DISTINCT FROM (to_jsonb(NEW) - ARRAY['status','completed_at']) THEN RAISE EXCEPTION 'terminal experiment is immutable'; END IF; IF (to_jsonb(OLD) - ARRAY['status','completed_at','failure_category','failure_code','failure_detail']) IS DISTINCT FROM (to_jsonb(NEW) - ARRAY['status','completed_at','failure_category','failure_code','failure_detail']) THEN RAISE EXCEPTION 'experiment configuration is immutable'; END IF; RETURN NEW; END; $$""")
    op.execute("CREATE TRIGGER experiments_immutable_config BEFORE UPDATE OR DELETE ON experiments FOR EACH ROW EXECUTE FUNCTION prevent_experiment_config_mutation()")

    # Facts and derived rows are append-only and cannot outlive a terminal Experiment.
    op.execute("""CREATE FUNCTION phase_4_append_only_guard() RETURNS trigger LANGUAGE plpgsql AS $$ DECLARE experiment UUID; BEGIN IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'historical facts are immutable'; END IF; IF TG_TABLE_NAME = 'order_events' THEN SELECT o.experiment_id INTO experiment FROM orders o WHERE o.id = NEW.order_id; ELSIF TG_TABLE_NAME = 'experiment_equity_points' OR TG_TABLE_NAME = 'experiment_results' THEN experiment := NEW.experiment_id; ELSIF TG_TABLE_NAME = 'fills' THEN SELECT o.experiment_id INTO experiment FROM orders o WHERE o.id = NEW.order_id; ELSIF TG_TABLE_NAME = 'trade_intents' THEN experiment := NEW.experiment_id; ELSE SELECT ti.experiment_id INTO experiment FROM trade_intents ti WHERE ti.id = NEW.trade_intent_id; END IF; IF EXISTS (SELECT 1 FROM experiments WHERE id = experiment AND status IN ('COMPLETED','FAILED')) THEN RAISE EXCEPTION 'terminal experiment graph is immutable'; END IF; RETURN NEW; END; $$""")
    for table in ("order_events", "fills", "trade_intents", "risk_decisions", "experiment_equity_points", "experiment_results"):
        op.execute(f"CREATE TRIGGER {table}_phase_4_guard BEFORE INSERT OR UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION phase_4_append_only_guard()")
    op.execute("""CREATE FUNCTION phase_4_order_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF TG_OP <> 'UPDATE' OR OLD.current_status IN ('FILLED','CANCELED','REJECTED','EXPIRED','UNKNOWN') THEN RAISE EXCEPTION 'terminal order is immutable'; END IF; IF (to_jsonb(OLD) - ARRAY['current_status','submitted_at']) IS DISTINCT FROM (to_jsonb(NEW) - ARRAY['current_status','submitted_at']) THEN RAISE EXCEPTION 'order facts are immutable'; END IF; RETURN NEW; END; $$""")
    op.execute("CREATE TRIGGER orders_phase_4_guard BEFORE UPDATE OR DELETE ON orders FOR EACH ROW EXECUTE FUNCTION phase_4_order_guard()")
    op.execute("""CREATE FUNCTION phase_4_order_parent_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.purpose IN ('STOP_LOSS','TAKE_PROFIT') AND EXISTS (SELECT 1 FROM experiments WHERE id = NEW.experiment_id AND model_version = 'PHASE4_HISTORICAL_EXECUTION_V1') AND NEW.parent_entry_order_id IS NULL THEN RAISE EXCEPTION 'Phase 4 protection order requires parent entry order'; END IF; RETURN NEW; END; $$""")
    op.execute("CREATE TRIGGER orders_phase_4_parent_guard BEFORE INSERT ON orders FOR EACH ROW EXECUTE FUNCTION phase_4_order_parent_guard()")
    op.execute("""CREATE FUNCTION phase_4_terminal_projection_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF EXISTS (SELECT 1 FROM experiments WHERE id = OLD.experiment_id AND status IN ('COMPLETED','FAILED')) THEN RAISE EXCEPTION 'terminal experiment projection is immutable'; END IF; RETURN NEW; END; $$""")
    for table in ("positions", "experiment_accounts", "trades"):
        op.execute(f"CREATE TRIGGER {table}_phase_4_guard BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION phase_4_terminal_projection_guard()")


def downgrade() -> None:
    for table in ("positions", "experiment_accounts", "trades"):
        op.execute(f"DROP TRIGGER {table}_phase_4_guard ON {table}")
    op.execute("DROP FUNCTION phase_4_terminal_projection_guard()")
    op.execute("DROP TRIGGER orders_phase_4_guard ON orders")
    op.execute("DROP FUNCTION phase_4_order_guard()")
    op.execute("DROP TRIGGER orders_phase_4_parent_guard ON orders")
    op.execute("DROP FUNCTION phase_4_order_parent_guard()")
    for table in ("order_events", "fills", "trade_intents", "risk_decisions", "experiment_equity_points", "experiment_results"):
        op.execute(f"DROP TRIGGER {table}_phase_4_guard ON {table}")
    op.execute("DROP FUNCTION phase_4_append_only_guard()")
    op.execute("DROP TRIGGER experiments_immutable_config ON experiments")
    op.execute("DROP FUNCTION prevent_experiment_config_mutation()")
    op.execute("DROP TRIGGER experiments_phase_4_insert_compat ON experiments")
    op.execute("DROP FUNCTION phase_4_experiment_insert_compat()")
    op.execute("""CREATE FUNCTION prevent_experiment_config_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'experiments are immutable'; END IF; IF (to_jsonb(OLD) - ARRAY['status','completed_at','failure_category','failure_code','failure_detail']) IS DISTINCT FROM (to_jsonb(NEW) - ARRAY['status','completed_at','failure_category','failure_code','failure_detail']) THEN RAISE EXCEPTION 'experiment configuration is immutable'; END IF; IF OLD.status IN ('COMPLETED','FAILED') AND (to_jsonb(OLD) - ARRAY['status','completed_at']) IS DISTINCT FROM (to_jsonb(NEW) - ARRAY['status','completed_at']) THEN RAISE EXCEPTION 'terminal experiment is immutable'; END IF; RETURN NEW; END; $$""")
    op.execute("CREATE TRIGGER experiments_immutable_config BEFORE UPDATE OR DELETE ON experiments FOR EACH ROW EXECUTE FUNCTION prevent_experiment_config_mutation()")
    op.drop_table("experiment_results")
    op.drop_table("experiment_equity_points")
    op.drop_table("order_events")
    op.drop_constraint("phase_4_financing_excluded", "trades", type_="check")
    op.drop_constraint("phase_4_exit_reason", "trades", type_="check")
    op.drop_constraint("fk_trades_ambiguity_source_market_bar_id_market_bars", "trades", type_="foreignkey")
    for name in ("ambiguity_source_market_bar_id", "ambiguity_observed_at", "ambiguity_policy", "intrabar_ambiguous", "r_multiple", "net_pnl", "financing_cost", "commission_cost", "initial_risk"):
        op.drop_column("trades", name)
    op.drop_constraint("phase_4_price_basis", "fills", type_="check")
    op.drop_constraint("fk_fills_source_market_bar_id_market_bars", "fills", type_="foreignkey")
    for name in ("slippage_cost", "slippage_per_unit", "executable_reference_price", "price_basis", "source_market_bar_id"):
        op.drop_column("fills", name)
    op.drop_constraint("uq_orders_parent_purpose", "orders", type_="unique")
    op.drop_constraint("fk_orders_parent_entry_order_id_orders", "orders", type_="foreignkey")
    op.drop_column("orders", "parent_entry_order_id")
    op.drop_constraint("phase_4_actual_risk", "risk_decisions", type_="check")
    op.drop_column("risk_decisions", "actual_risk")
    op.drop_constraint("status_completion_consistency", "experiments", type_="check")
    op.drop_constraint("valid_status", "experiments", type_="check")
    op.create_check_constraint("valid_status", "experiments", "status IN ('RUNNING', 'COMPLETED', 'FAILED')")
    op.create_check_constraint("status_completion_consistency", "experiments", "(status = 'RUNNING' AND completed_at IS NULL) OR (status IN ('COMPLETED', 'FAILED') AND completed_at IS NOT NULL)")
    op.alter_column("experiments", "status", server_default=sa.text("'RUNNING'"))
