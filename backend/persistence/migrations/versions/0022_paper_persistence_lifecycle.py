"""Add the bounded PAPER persistence and lifecycle facts."""

# fmt: off
# ruff: noqa: E501

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0022_paper_persistence_lifecycle"
down_revision = "0021_experiment_deletion"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
TS = sa.DateTime(timezone=True)
NUMERIC = sa.Numeric(24, 10)
PRICE = sa.Numeric(20, 10)
JSONB = postgresql.JSONB


def _fk(column: str, target: str, ondelete: str = "RESTRICT") -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint([column], [target], ondelete=ondelete)


def upgrade() -> None:
    op.drop_constraint("valid_event_type", "order_events", type_="check")
    op.create_check_constraint("valid_event_type", "order_events", "event_type IN ('ORDER_CREATED', 'ORDER_SUBMITTED', 'ORDER_FILLED', 'ORDER_CANCELED', 'ORDER_REJECTED', 'ORDER_EXPIRED', 'ORDER_UNKNOWN', 'ORDER_PARTIAL', 'ORDER_REISSUED', 'PROTECTION_CONFIRMED', 'PROTECTION_FAILED')")
    op.create_table(
        "trading_accounts",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("broker", sa.String(20), server_default=sa.text("'OANDA'"), nullable=False),
        sa.Column("environment", sa.String(20), server_default=sa.text("'Practice'"), nullable=False),
        sa.Column("external_account_id", sa.String(80), nullable=False),
        sa.Column("mode", sa.String(10), server_default=sa.text("'PAPER'"), nullable=False),
        sa.Column("base_currency", sa.String(3), server_default=sa.text("'USD'"), nullable=False),
        sa.Column("mt4_association_status", sa.String(20), server_default=sa.text("'UNKNOWN'"), nullable=False),
        sa.Column("capabilities", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("connection_status", sa.String(20), server_default=sa.text("'UNKNOWN'"), nullable=False),
        sa.Column("provenance", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("last_validated_at", TS, nullable=True),
        sa.Column("created_at", TS, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_account_id", name="uq_trading_accounts_external_id"),
        sa.CheckConstraint("broker = 'OANDA'", name="paper_broker"),
        sa.CheckConstraint("environment = 'Practice'", name="paper_environment"),
        sa.CheckConstraint("mode = 'PAPER'", name="paper_mode"),
        sa.CheckConstraint("base_currency = 'USD'", name="paper_base_currency"),
        sa.CheckConstraint("mt4_association_status IN ('UNKNOWN', 'NOT_ASSOCIATED', 'ASSOCIATED')", name="valid_mt4_association_status"),
        sa.CheckConstraint("connection_status IN ('UNKNOWN', 'VALID', 'STALE', 'DISCONNECTED', 'REJECTED')", name="valid_connection_status"),
    )
    op.create_table(
        "deployments",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("trading_account_id", UUID, nullable=False),
        sa.Column("strategy_version_id", UUID, nullable=False),
        sa.Column("venue_instrument_id", UUID, nullable=False),
        sa.Column("mode", sa.String(10), server_default=sa.text("'PAPER'"), nullable=False),
        sa.Column("parameter_snapshot", JSONB, nullable=False),
        sa.Column("risk_snapshot", JSONB, nullable=False),
        sa.Column("execution_provenance", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("desired_state", sa.String(30), server_default=sa.text("'DRAFT'"), nullable=False),
        sa.Column("actual_state", sa.String(30), server_default=sa.text("'DRAFT'"), nullable=False),
        sa.Column("safety_reason", sa.String(500), nullable=True),
        sa.Column("first_trade_at", TS, nullable=True),
        sa.Column("created_at", TS, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        _fk("trading_account_id", "trading_accounts.id"),
        _fk("strategy_version_id", "strategy_versions.id"),
        _fk("venue_instrument_id", "venue_instruments.id"),
        sa.CheckConstraint("mode = 'PAPER'", name="paper_mode"),
        sa.CheckConstraint("desired_state IN ('DRAFT', 'RUNNING', 'PAUSED', 'STOPPED', 'ARCHIVED')", name="valid_desired_state"),
        sa.CheckConstraint("actual_state IN ('DRAFT', 'STARTING', 'RUNNING', 'PAUSED', 'STOPPED', 'FAILED', 'RECONCILIATION_REQUIRED', 'ARCHIVED')", name="valid_actual_state"),
        sa.CheckConstraint("safety_reason IS NULL OR (length(safety_reason) BETWEEN 1 AND 500 AND safety_reason !~ '[[:cntrl:]]')", name="sanitized_safety_reason"),
    )
    op.create_index("uq_deployments_active_account_instrument", "deployments", ["trading_account_id", "venue_instrument_id"], unique=True, postgresql_where=sa.text("actual_state <> 'ARCHIVED'"))

    for table, column in (("trade_intents", "experiment_id"), ("orders", "experiment_id"), ("positions", "experiment_id"), ("trades", "experiment_id")):
        op.alter_column(table, column, existing_type=UUID, nullable=True)
    for table in ("trade_intents", "orders", "positions", "trades"):
        op.add_column(table, sa.Column("deployment_id", UUID, nullable=True))
        op.create_foreign_key(f"fk_{table}_deployment_id_deployments", table, "deployments", ["deployment_id"], ["id"], ondelete="RESTRICT")
        op.create_check_constraint(f"{table}_exactly_one_root", table, "(experiment_id IS NOT NULL) <> (deployment_id IS NOT NULL)")
    op.create_unique_constraint("uq_positions_deployment_instrument", "positions", ["deployment_id", "venue_instrument_id"])
    op.create_unique_constraint("uq_trades_deployment_sequence", "trades", ["deployment_id", "sequence_number"])

    op.add_column("trade_intents", sa.Column("target_methodology", sa.String(80), nullable=True))
    op.create_index("uq_trade_intents_deployment_frontier", "trade_intents", ["deployment_id", "decision_frontier"], unique=True, postgresql_where=sa.text("deployment_id IS NOT NULL"))
    for name, column in (
        ("target_methodology", sa.String(80)),
        ("target_multiple", sa.Numeric(12, 10)),
        ("quote_observed_at", TS),
        ("price_bound", PRICE),
    ):
        op.add_column("risk_decisions", sa.Column(name, column, nullable=True))
    op.add_column("risk_decisions", sa.Column("evidence", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False))
    for name, column in (
        ("time_in_force", sa.String(3)),
        ("price_bound", PRICE),
        ("external_order_id", sa.String(100)),
        ("provider_request_id", sa.String(200)),
    ):
        op.add_column("orders", sa.Column(name, column, nullable=True))
    op.create_unique_constraint("uq_orders_external_order_id", "orders", ["external_order_id"])
    op.add_column("orders", sa.Column("external_trade_ids", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False))
    op.add_column("orders", sa.Column("related_transaction_ids", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False))
    op.add_column("orders", sa.Column("request_provenance", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.add_column("fills", sa.Column("external_transaction_id", sa.String(200), nullable=True))
    op.add_column("fills", sa.Column("external_trade_id", sa.String(100), nullable=True))
    op.add_column("fills", sa.Column("related_transaction_ids", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False))
    op.create_unique_constraint("uq_fills_external_transaction_id", "fills", ["external_transaction_id"])

    op.create_table(
        "strategy_states",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("deployment_id", UUID, nullable=False),
        sa.Column("strategy_version_id", UUID, nullable=False),
        sa.Column("state_version", sa.BigInteger, nullable=False),
        sa.Column("state_envelope", JSONB, nullable=False),
        sa.Column("last_evaluated_bar_end", TS, nullable=True),
        sa.Column("created_at", TS, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        _fk("deployment_id", "deployments.id"), _fk("strategy_version_id", "strategy_versions.id"),
        sa.UniqueConstraint("deployment_id", "state_version", name="uq_strategy_states_deployment_version"),
        sa.CheckConstraint("state_version > 0", name="positive_state_version"),
        sa.CheckConstraint("jsonb_typeof(state_envelope) = 'object'", name="state_envelope_object"),
    )
    op.create_table(
        "deployment_frontiers",
        sa.Column("deployment_id", UUID, nullable=False),
        sa.Column("completed_m15_frontier", TS, nullable=True),
        sa.Column("last_execution_observation_at", TS, nullable=True),
        sa.Column("data_status", sa.String(25), server_default=sa.text("'UNKNOWN'"), nullable=False),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("deployment_id"), _fk("deployment_id", "deployments.id"),
        sa.CheckConstraint("data_status IN ('HEALTHY', 'STALE', 'DISCONNECTED', 'EXPECTED_CLOSURE', 'BLOCKED', 'UNKNOWN')", name="valid_data_status"),
    )
    op.create_table(
        "pending_entry_handoffs",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("deployment_id", UUID, nullable=False),
        sa.Column("trade_intent_id", UUID, nullable=False),
        sa.Column("status", sa.String(20), server_default=sa.text("'PENDING'"), nullable=False),
        sa.Column("safety_reason", sa.String(500), nullable=True),
        sa.Column("created_at", TS, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("resolved_at", TS, nullable=True),
        sa.PrimaryKeyConstraint("id"), _fk("deployment_id", "deployments.id"), _fk("trade_intent_id", "trade_intents.id"),
        sa.UniqueConstraint("trade_intent_id", name="uq_pending_entry_handoffs_intent"),
        sa.CheckConstraint("status IN ('PENDING', 'FILLED', 'EXPIRED', 'REJECTED', 'BLOCKED')", name="valid_handoff_status"),
        sa.CheckConstraint("safety_reason IS NULL OR (length(safety_reason) BETWEEN 1 AND 500 AND safety_reason !~ '[[:cntrl:]]')", name="sanitized_safety_reason"),
    )
    op.create_index("uq_pending_entry_handoffs_active", "pending_entry_handoffs", ["deployment_id"], unique=True, postgresql_where=sa.text("status = 'PENDING'"))

    op.create_table(
        "trading_account_snapshots",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("trading_account_id", UUID, nullable=False),
        sa.Column("balance", NUMERIC, nullable=True), sa.Column("nav", NUMERIC, nullable=True),
        sa.Column("equity", NUMERIC, nullable=True), sa.Column("margin_available", NUMERIC, nullable=True), sa.Column("margin_used", NUMERIC, nullable=True),
        sa.Column("facts", JSONB, nullable=False), sa.Column("observed_at", TS, nullable=False),
        sa.Column("freshness", sa.String(10), nullable=False), sa.Column("source", sa.String(100), nullable=False),
        sa.Column("created_at", TS, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"), _fk("trading_account_id", "trading_accounts.id"),
        sa.CheckConstraint("freshness IN ('FRESH', 'STALE', 'UNKNOWN')", name="valid_account_freshness"),
        sa.CheckConstraint("jsonb_typeof(facts) = 'object'", name="account_facts_object"),
    )
    op.create_table(
        "runtime_ownership",
        sa.Column("deployment_id", UUID, nullable=False), sa.Column("owner_id", sa.String(120), nullable=False),
        sa.Column("lock_key", sa.BigInteger, nullable=False), sa.Column("acquired_at", TS, nullable=False),
        sa.Column("last_heartbeat_at", TS, nullable=False), sa.Column("lock_held", sa.Boolean, nullable=False),
        sa.Column("db_connected", sa.Boolean, nullable=False), sa.Column("health_status", sa.String(30), nullable=False),
        sa.Column("released_at", TS, nullable=True), sa.PrimaryKeyConstraint("deployment_id"), _fk("deployment_id", "deployments.id"),
    )
    op.create_table(
        "runtime_heartbeats",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False), sa.Column("deployment_id", UUID, nullable=False),
        sa.Column("owner_id", sa.String(120), nullable=False), sa.Column("observed_at", TS, nullable=False),
        sa.Column("lock_held", sa.Boolean, nullable=False), sa.Column("db_connected", sa.Boolean, nullable=False),
        sa.Column("health_status", sa.String(30), nullable=False), sa.Column("details", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.PrimaryKeyConstraint("id"), _fk("deployment_id", "deployments.id"),
    )
    op.create_table(
        "system_events",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False), sa.Column("deployment_id", UUID, nullable=True),
        sa.Column("severity", sa.String(10), nullable=False), sa.Column("code", sa.String(80), nullable=False),
        sa.Column("detail", sa.String(500), nullable=False), sa.Column("details", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("occurred_at", TS, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"), _fk("deployment_id", "deployments.id"),
        sa.CheckConstraint("severity IN ('INFO', 'WARNING', 'CRITICAL')", name="valid_severity"),
        sa.CheckConstraint("length(code) BETWEEN 1 AND 80 AND code ~ '^[A-Z0-9_]+$'", name="sanitized_event_code"),
        sa.CheckConstraint("length(detail) BETWEEN 1 AND 500 AND detail !~ '[[:cntrl:]]'", name="sanitized_event_detail"),
    )
    op.create_table(
        "reconciliation_records",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False), sa.Column("deployment_id", UUID, nullable=False),
        sa.Column("trigger", sa.String(40), nullable=False), sa.Column("outcome", sa.String(30), nullable=False),
        sa.Column("started_at", TS, nullable=False), sa.Column("finished_at", TS, nullable=False), sa.Column("summary", JSONB, nullable=False),
        sa.Column("created_at", TS, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False), sa.PrimaryKeyConstraint("id"), _fk("deployment_id", "deployments.id"),
        sa.CheckConstraint("outcome IN ('MATCHED', 'REPAIRED', 'RECONCILIATION_REQUIRED')", name="valid_reconciliation_outcome"),
        sa.CheckConstraint("jsonb_typeof(summary) = 'object'", name="reconciliation_summary_object"),
    )
    op.create_table(
        "account_transaction_cursors",
        sa.Column("trading_account_id", UUID, nullable=False), sa.Column("last_transaction_id", sa.String(80), nullable=False),
        sa.Column("observed_at", TS, nullable=False), sa.Column("source", sa.String(100), nullable=False),
        sa.PrimaryKeyConstraint("trading_account_id"), _fk("trading_account_id", "trading_accounts.id"),
        sa.CheckConstraint("last_transaction_id ~ '^[0-9]+$'", name="numeric_transaction_cursor"),
    )

    op.execute("""CREATE FUNCTION atlas_validate_canonical_ownership() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE ti_experiment UUID; ti_deployment UUID; entry_experiment UUID; entry_deployment UUID; exit_experiment UUID; exit_deployment UUID; parent_experiment UUID; parent_deployment UUID; decision_intent UUID;
    BEGIN
      IF TG_TABLE_NAME IN ('trade_intents','orders','positions','trades') AND ((NEW.experiment_id IS NULL) = (NEW.deployment_id IS NULL)) THEN RAISE EXCEPTION 'canonical fact must have exactly one root owner'; END IF;
      IF TG_TABLE_NAME = 'trade_intents' THEN RETURN NEW; END IF;
      IF TG_TABLE_NAME = 'risk_decisions' THEN
        SELECT experiment_id, deployment_id INTO ti_experiment, ti_deployment FROM trade_intents WHERE id = NEW.trade_intent_id;
        IF NOT FOUND THEN RAISE EXCEPTION 'RiskDecision requires an existing TradeIntent'; END IF;
        IF ti_deployment IS NOT NULL AND NEW.phase = 'PRE_SUBMISSION' AND NEW.target_price IS NOT NULL THEN RAISE EXCEPTION 'PAPER PRE_SUBMISSION target must be NULL'; END IF;
        IF ti_deployment IS NOT NULL AND (NEW.target_methodology IS DISTINCT FROM (SELECT target_methodology FROM trade_intents WHERE id = NEW.trade_intent_id) OR NEW.target_multiple IS DISTINCT FROM (SELECT target_multiple FROM trade_intents WHERE id = NEW.trade_intent_id)) THEN RAISE EXCEPTION 'RiskDecision target methodology does not match TradeIntent'; END IF;
        RETURN NEW;
      END IF;
      IF TG_TABLE_NAME = 'orders' THEN
        SELECT experiment_id, deployment_id INTO ti_experiment, ti_deployment FROM trade_intents WHERE id = NEW.trade_intent_id;
        SELECT trade_intent_id INTO decision_intent FROM risk_decisions WHERE id = NEW.risk_decision_id;
        IF ti_experiment IS DISTINCT FROM NEW.experiment_id OR ti_deployment IS DISTINCT FROM NEW.deployment_id OR decision_intent IS DISTINCT FROM NEW.trade_intent_id THEN RAISE EXCEPTION 'Order graph crosses canonical root or intent'; END IF;
        IF NEW.parent_entry_order_id IS NOT NULL THEN SELECT experiment_id, deployment_id INTO parent_experiment, parent_deployment FROM orders WHERE id = NEW.parent_entry_order_id; IF parent_experiment IS DISTINCT FROM NEW.experiment_id OR parent_deployment IS DISTINCT FROM NEW.deployment_id THEN RAISE EXCEPTION 'Order parent crosses canonical root'; END IF; END IF;
        IF NEW.deployment_id IS NOT NULL AND NEW.purpose = 'ENTRY' AND (NEW.order_type <> 'MARKET' OR NEW.time_in_force <> 'FOK') THEN RAISE EXCEPTION 'PAPER entry must be MARKET/FOK'; END IF;
        RETURN NEW;
      END IF;
      IF TG_TABLE_NAME = 'fills' THEN
        SELECT experiment_id, deployment_id INTO entry_experiment, entry_deployment FROM orders WHERE id = NEW.order_id;
        IF NOT FOUND THEN RAISE EXCEPTION 'Fill requires an existing Order'; END IF;
        RETURN NEW;
      END IF;
      IF TG_TABLE_NAME = 'trades' THEN
        SELECT experiment_id, deployment_id INTO ti_experiment, ti_deployment FROM trade_intents WHERE id = NEW.trade_intent_id;
        SELECT experiment_id, deployment_id INTO entry_experiment, entry_deployment FROM orders WHERE id = NEW.entry_order_id;
        IF ti_experiment IS DISTINCT FROM entry_experiment OR ti_deployment IS DISTINCT FROM entry_deployment OR NEW.experiment_id IS DISTINCT FROM ti_experiment OR NEW.deployment_id IS DISTINCT FROM ti_deployment THEN RAISE EXCEPTION 'Trade graph crosses canonical root'; END IF;
        IF NEW.exit_order_id IS NOT NULL THEN SELECT experiment_id, deployment_id INTO exit_experiment, exit_deployment FROM orders WHERE id = NEW.exit_order_id; IF exit_experiment IS DISTINCT FROM ti_experiment OR exit_deployment IS DISTINCT FROM ti_deployment THEN RAISE EXCEPTION 'Trade exit Order crosses canonical root'; END IF; END IF;
      END IF;
      RETURN NEW;
    END; $$""")
    for table in ("trade_intents", "risk_decisions", "orders", "fills", "positions", "trades"):
        op.execute(f"CREATE TRIGGER {table}_paper_ownership BEFORE INSERT OR UPDATE ON {table} FOR EACH ROW EXECUTE FUNCTION atlas_validate_canonical_ownership()")
    op.execute("""CREATE FUNCTION paper_pending_entry_guard() RETURNS trigger LANGUAGE plpgsql AS $$ DECLARE intent_deployment UUID; intent_experiment UUID; BEGIN
      IF TG_OP = 'UPDATE' AND (OLD.deployment_id IS DISTINCT FROM NEW.deployment_id OR OLD.trade_intent_id IS DISTINCT FROM NEW.trade_intent_id) THEN RAISE EXCEPTION 'pending handoff ownership is immutable'; END IF;
      SELECT deployment_id, experiment_id INTO intent_deployment, intent_experiment FROM trade_intents WHERE id = NEW.trade_intent_id;
      IF NOT FOUND OR intent_deployment IS DISTINCT FROM NEW.deployment_id OR intent_experiment IS NOT NULL THEN RAISE EXCEPTION 'pending handoff crosses canonical root'; END IF;
      RETURN NEW;
    END; $$""")
    op.execute("CREATE TRIGGER pending_entry_handoffs_owner_guard BEFORE INSERT OR UPDATE ON pending_entry_handoffs FOR EACH ROW EXECUTE FUNCTION paper_pending_entry_guard()")

    op.execute("""CREATE FUNCTION paper_deployment_config_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
      IF OLD.first_trade_at IS NOT NULL AND (to_jsonb(OLD) - ARRAY['desired_state','actual_state','safety_reason','updated_at','first_trade_at']) IS DISTINCT FROM (to_jsonb(NEW) - ARRAY['desired_state','actual_state','safety_reason','updated_at','first_trade_at']) THEN RAISE EXCEPTION 'traded Deployment configuration is immutable'; END IF;
      RETURN NEW;
    END; $$""")
    op.execute("CREATE TRIGGER deployments_config_guard BEFORE UPDATE ON deployments FOR EACH ROW EXECUTE FUNCTION paper_deployment_config_guard()")
    op.execute("""CREATE FUNCTION paper_append_only_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'PAPER lifecycle facts are append-only'; END IF; RETURN NEW; END; $$""")
    for table in ("strategy_states", "runtime_heartbeats", "system_events", "reconciliation_records", "trading_account_snapshots"):
        op.execute(f"CREATE TRIGGER {table}_append_only BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION paper_append_only_guard()")


def downgrade() -> None:
    op.drop_constraint("valid_event_type", "order_events", type_="check")
    op.create_check_constraint("valid_event_type", "order_events", "event_type IN ('ORDER_CREATED', 'ORDER_SUBMITTED', 'ORDER_FILLED', 'ORDER_CANCELED')")
    for table in ("strategy_states", "runtime_heartbeats", "system_events", "reconciliation_records", "trading_account_snapshots"):
        op.execute(f"DROP TRIGGER {table}_append_only ON {table}")
    op.execute("DROP TRIGGER deployments_config_guard ON deployments")
    op.execute("DROP FUNCTION paper_append_only_guard()")
    op.execute("DROP FUNCTION paper_deployment_config_guard()")
    for table in ("trade_intents", "risk_decisions", "orders", "fills", "positions", "trades"):
        op.execute(f"DROP TRIGGER {table}_paper_ownership ON {table}")
    op.execute("DROP FUNCTION atlas_validate_canonical_ownership()")
    op.execute("DROP TRIGGER pending_entry_handoffs_owner_guard ON pending_entry_handoffs")
    op.execute("DROP FUNCTION paper_pending_entry_guard()")
    op.drop_table("account_transaction_cursors")
    op.drop_table("reconciliation_records")
    op.drop_table("system_events")
    op.drop_table("runtime_heartbeats")
    op.drop_table("runtime_ownership")
    op.drop_table("trading_account_snapshots")
    op.drop_index("uq_pending_entry_handoffs_active", table_name="pending_entry_handoffs")
    op.drop_table("pending_entry_handoffs")
    op.drop_table("deployment_frontiers")
    op.drop_table("strategy_states")
    op.drop_constraint("uq_fills_external_transaction_id", "fills", type_="unique")
    for name in ("related_transaction_ids", "external_trade_id", "external_transaction_id"):
        op.drop_column("fills", name)
    op.drop_constraint("uq_orders_external_order_id", "orders", type_="unique")
    for name in ("request_provenance", "related_transaction_ids", "external_trade_ids", "provider_request_id", "external_order_id", "price_bound", "time_in_force"):
        op.drop_column("orders", name)
    for name in ("evidence", "price_bound", "quote_observed_at", "target_multiple", "target_methodology"):
        op.drop_column("risk_decisions", name)
    op.drop_index("uq_trade_intents_deployment_frontier", table_name="trade_intents")
    op.drop_column("trade_intents", "target_methodology")
    op.drop_constraint("uq_positions_deployment_instrument", "positions", type_="unique")
    op.drop_constraint("uq_trades_deployment_sequence", "trades", type_="unique")
    for table in ("trade_intents", "orders", "positions", "trades"):
        op.drop_constraint(f"{table}_exactly_one_root", table, type_="check")
        op.drop_constraint(f"fk_{table}_deployment_id_deployments", table, type_="foreignkey")
        op.drop_column(table, "deployment_id")
        op.alter_column(table, "experiment_id", existing_type=UUID, nullable=False)
    op.drop_index("uq_deployments_active_account_instrument", table_name="deployments")
    op.drop_table("deployments")
    op.drop_table("trading_accounts")
