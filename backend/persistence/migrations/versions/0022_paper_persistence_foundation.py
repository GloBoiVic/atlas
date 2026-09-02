"""Add the provider-neutral PAPER execution persistence foundation."""

# fmt: off
# ruff: noqa: E501

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0022_paper_persistence"
down_revision = "0021_experiment_deletion"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB
NUMERIC = sa.Numeric(30, 10)
TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "paper_execution_attempts",
        sa.Column("attempt_id", UUID, nullable=False),
        sa.Column("strategy_version_id", UUID, nullable=False),
        sa.Column("strategy_key", sa.String(200), nullable=False),
        sa.Column("strategy_version_number", sa.Integer, nullable=False),
        sa.Column("source_fingerprint", sa.String(64), nullable=False),
        sa.Column("implementation_key", sa.String(200), nullable=False),
        sa.Column("validated_parameter_snapshot", JSONB, nullable=False),
        sa.Column("strategy_evaluation_snapshot", JSONB, nullable=False),
        sa.Column("risk_authority_snapshot", JSONB, nullable=False),
        sa.Column("strategy_decision", JSONB, nullable=False),
        sa.Column("pre_flight_risk_decision", JSONB, nullable=False),
        sa.Column("pre_submission_risk_decision", JSONB, nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("environment", sa.String(20), nullable=False),
        sa.Column("provider_account_id", sa.String(128), nullable=False),
        sa.Column("base_currency", sa.String(3), nullable=False),
        sa.Column("instrument", sa.String(20), nullable=False),
        sa.Column("direction", sa.String(5), nullable=False),
        sa.Column("requested_quantity", NUMERIC, nullable=False),
        sa.Column("approved_entry_price", NUMERIC, nullable=False),
        sa.Column("stop_price", NUMERIC, nullable=False),
        sa.Column("decision_time", TS, nullable=False),
        sa.Column("pricing_time", TS, nullable=False),
        sa.Column("account_transaction_id", sa.String(64), nullable=False),
        sa.Column("instrument_transaction_id", sa.String(64), nullable=False),
        sa.Column("display_precision", sa.Integer, nullable=False),
        sa.Column("trade_units_precision", sa.Integer, nullable=False),
        sa.Column("client_order_id", sa.String(128), nullable=False),
        sa.Column("client_trade_id", sa.String(128), nullable=False),
        sa.Column("client_stop_loss_order_id", sa.String(128), nullable=False),
        sa.Column("client_take_profit_order_id", sa.String(128), nullable=False),
        sa.Column("created_at", TS, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("fill_broker_order_id", sa.String(128)),
        sa.Column("fill_transaction_id", sa.String(64)),
        sa.Column("fill_trade_id", sa.String(128)),
        sa.Column("fill_signed_units", NUMERIC),
        sa.Column("fill_price", NUMERIC),
        sa.Column("fill_executed_at", TS),
        sa.Column("fill_actual_initial_risk", NUMERIC),
        sa.Column("actual_target_price", NUMERIC),
        sa.Column("stop_loss_status", sa.String(20), server_default=sa.text("'NOT_ATTEMPTED'"), nullable=False),
        sa.Column("stop_loss_broker_order_id", sa.String(128)),
        sa.Column("stop_loss_client_order_id", sa.String(128)),
        sa.Column("stop_loss_price", NUMERIC),
        sa.Column("stop_loss_provider_state", sa.String(64)),
        sa.Column("take_profit_status", sa.String(20), server_default=sa.text("'NOT_ATTEMPTED'"), nullable=False),
        sa.Column("take_profit_broker_order_id", sa.String(128)),
        sa.Column("take_profit_client_order_id", sa.String(128)),
        sa.Column("take_profit_price", NUMERIC),
        sa.Column("take_profit_provider_state", sa.String(64)),
        sa.Column("execution_outcome", sa.String(40)),
        sa.Column("rejection_code", sa.String(64)),
        sa.Column("rejection_broker_order_id", sa.String(128)),
        sa.Column("rejection_transaction_id", sa.String(64)),
        sa.Column("uncertainty_code", sa.String(64)),
        sa.Column("reconciliation_status", sa.String(24), server_default=sa.text("'NOT_RUN'"), nullable=False),
        sa.Column("reconciliation_block_code", sa.String(64)),
        sa.Column("last_reconciliation_run_id", UUID),
        sa.Column("last_reconciled_at", TS),
        sa.Column("last_applied_transaction_id", sa.String(64)),
        sa.Column("projection_version", sa.BigInteger, server_default=sa.text("0"), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("attempt_id"),
        sa.ForeignKeyConstraint(["strategy_version_id"], ["strategy_versions.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("provider = 'OANDA'", name="paper_provider"),
        sa.CheckConstraint("environment = 'PRACTICE'", name="paper_environment"),
        sa.CheckConstraint("base_currency = 'USD'", name="paper_base_currency"),
        sa.CheckConstraint("instrument = 'EUR_USD'", name="paper_instrument"),
        sa.CheckConstraint("direction IN ('LONG', 'SHORT')", name="paper_direction"),
        sa.CheckConstraint("strategy_version_number > 0", name="paper_version_positive"),
        sa.CheckConstraint("source_fingerprint ~ '^[0-9a-f]{64}$'", name="paper_source_fingerprint"),
        sa.CheckConstraint("requested_quantity > 0 AND requested_quantity <> 'NaN'::numeric AND requested_quantity <> 'Infinity'::numeric AND requested_quantity <> '-Infinity'::numeric", name="paper_quantity_positive_finite"),
        sa.CheckConstraint("approved_entry_price > 0 AND approved_entry_price <> 'NaN'::numeric AND approved_entry_price <> 'Infinity'::numeric AND approved_entry_price <> '-Infinity'::numeric", name="paper_entry_price_positive_finite"),
        sa.CheckConstraint("stop_price > 0 AND stop_price <> 'NaN'::numeric AND stop_price <> 'Infinity'::numeric AND stop_price <> '-Infinity'::numeric", name="paper_stop_price_positive_finite"),
        sa.CheckConstraint("display_precision >= 0 AND trade_units_precision >= 0", name="paper_precision_nonnegative"),
        sa.CheckConstraint("(fill_broker_order_id IS NULL AND fill_transaction_id IS NULL AND fill_trade_id IS NULL AND fill_signed_units IS NULL AND fill_price IS NULL AND fill_executed_at IS NULL AND fill_actual_initial_risk IS NULL) OR (fill_broker_order_id IS NOT NULL AND fill_transaction_id IS NOT NULL AND fill_trade_id IS NOT NULL AND fill_signed_units IS NOT NULL AND fill_signed_units <> 0 AND fill_signed_units <> 'NaN'::numeric AND fill_signed_units <> 'Infinity'::numeric AND fill_signed_units <> '-Infinity'::numeric AND fill_price IS NOT NULL AND fill_price > 0 AND fill_price <> 'NaN'::numeric AND fill_price <> 'Infinity'::numeric AND fill_price <> '-Infinity'::numeric AND fill_executed_at IS NOT NULL AND fill_actual_initial_risk IS NOT NULL AND fill_actual_initial_risk >= 0 AND fill_actual_initial_risk <> 'NaN'::numeric AND fill_actual_initial_risk <> 'Infinity'::numeric AND fill_actual_initial_risk <> '-Infinity'::numeric)", name="paper_fill_all_or_none"),
        sa.CheckConstraint("stop_loss_status IN ('CONFIRMED', 'REJECTED', 'UNKNOWN', 'NOT_ATTEMPTED')", name="paper_stop_status"),
        sa.CheckConstraint("take_profit_status IN ('CONFIRMED', 'REJECTED', 'UNKNOWN', 'NOT_ATTEMPTED')", name="paper_take_profit_status"),
        sa.CheckConstraint("execution_outcome IS NULL OR execution_outcome IN ('FILLED_PROTECTED', 'FILLED_PROTECTION_INCOMPLETE', 'REJECTED', 'CANCELLED', 'UNKNOWN')", name="paper_execution_outcome"),
         sa.CheckConstraint("execution_outcome NOT IN ('FILLED_PROTECTED', 'FILLED_PROTECTION_INCOMPLETE') OR fill_broker_order_id IS NOT NULL", name="paper_filled_outcome_requires_fill"),
         sa.CheckConstraint("execution_outcome NOT IN ('REJECTED', 'CANCELLED', 'UNKNOWN') OR fill_broker_order_id IS NULL", name="paper_no_fill_outcome"),
         sa.CheckConstraint("execution_outcome <> 'FILLED_PROTECTED' OR (stop_loss_status = 'CONFIRMED' AND take_profit_status = 'CONFIRMED' AND actual_target_price IS NOT NULL)", name="paper_protected_outcome"),
        sa.CheckConstraint("actual_target_price IS NULL OR (actual_target_price > 0 AND actual_target_price <> 'NaN'::numeric AND actual_target_price <> 'Infinity'::numeric AND actual_target_price <> '-Infinity'::numeric)", name="paper_actual_target_positive_finite"),
        sa.CheckConstraint("reconciliation_status IN ('NOT_RUN', 'CONSISTENT', 'UNRESOLVED', 'CONFLICT', 'LIFECYCLE_ADVANCED')", name="paper_reconciliation_status"),
        sa.CheckConstraint("projection_version >= 0", name="paper_projection_version"),
        sa.UniqueConstraint("client_order_id", name="uq_paper_attempts_client_order"),
        sa.UniqueConstraint("client_trade_id", name="uq_paper_attempts_client_trade"),
        sa.UniqueConstraint("client_stop_loss_order_id", name="uq_paper_attempts_client_stop"),
        sa.UniqueConstraint("client_take_profit_order_id", name="uq_paper_attempts_client_take_profit"),
    )
    op.create_index("ix_paper_execution_attempts_outcome", "paper_execution_attempts", ["execution_outcome"])
    op.create_index("ix_paper_execution_attempts_reconciliation", "paper_execution_attempts", ["reconciliation_status"])

    op.create_table(
        "paper_mutation_claims",
        sa.Column("claim_id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("attempt_id", UUID, nullable=False),
        sa.Column("phase", sa.String(20), nullable=False),
        sa.Column("claimed_at", TS, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("provider_endpoint_key", sa.String(128), nullable=False),
        sa.Column("normalized_request_fingerprint", sa.String(64), nullable=False),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.ForeignKeyConstraint(["attempt_id"], ["paper_execution_attempts.attempt_id"], ondelete="RESTRICT"),
        sa.CheckConstraint("phase IN ('ENTRY', 'TAKE_PROFIT')", name="paper_claim_phase"),
        sa.CheckConstraint("normalized_request_fingerprint ~ '^[0-9a-f]{64}$'", name="paper_claim_request_fingerprint"),
        sa.UniqueConstraint("attempt_id", "phase", name="uq_paper_claims_attempt_phase"),
    )
    op.create_index("ix_paper_mutation_claims_attempt", "paper_mutation_claims", ["attempt_id"])

    op.create_table(
        "paper_reconciliation_runs",
        sa.Column("run_id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("attempt_id", UUID, nullable=False),
        sa.Column("run_sequence", sa.BigInteger, nullable=False),
        sa.Column("requested_at", TS, nullable=False),
        sa.Column("read_started_at", TS, nullable=False),
        sa.Column("completed_at", TS, nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("projection_version_observed", sa.BigInteger, nullable=False),
        sa.Column("projection_version_applied", sa.BigInteger),
        sa.Column("read_count", sa.Integer, nullable=False),
        sa.Column("read_budget", sa.Integer, nullable=False),
        sa.Column("frontier_before", sa.String(64)),
        sa.Column("frontier_observed", sa.String(64)),
        sa.Column("frontier_applied", sa.String(64)),
        sa.Column("non_atomic_read_set", sa.Boolean, server_default=sa.text("true"), nullable=False),
        sa.Column("prior_execution_outcome", sa.String(40)),
        sa.Column("resulting_execution_outcome", sa.String(40)),
        sa.Column("finding_codes", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("diagnostic_summary", sa.String(500), server_default=sa.text("''"), nullable=False),
        sa.Column("created_at", TS, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("run_id"),
        sa.ForeignKeyConstraint(["attempt_id"], ["paper_execution_attempts.attempt_id"], ondelete="RESTRICT"),
        sa.CheckConstraint("run_sequence > 0", name="paper_run_sequence"),
        sa.CheckConstraint("status IN ('PROVEN', 'UNRESOLVED', 'CONFLICT', 'LIFECYCLE_ADVANCED', 'FAILED')", name="paper_run_status"),
        sa.CheckConstraint("projection_version_observed >= 0", name="paper_run_observed_version"),
        sa.CheckConstraint("projection_version_applied IS NULL OR projection_version_applied >= 0", name="paper_run_applied_version"),
        sa.CheckConstraint("read_count >= 0 AND read_budget > 0 AND read_count <= read_budget", name="paper_run_budget"),
        sa.CheckConstraint("jsonb_typeof(finding_codes) = 'array' AND jsonb_array_length(finding_codes) <= 64", name="paper_run_findings"),
        sa.CheckConstraint("prior_execution_outcome IS NULL OR prior_execution_outcome IN ('FILLED_PROTECTED', 'FILLED_PROTECTION_INCOMPLETE', 'REJECTED', 'CANCELLED', 'UNKNOWN')", name="paper_run_prior_outcome"),
        sa.CheckConstraint("resulting_execution_outcome IS NULL OR resulting_execution_outcome IN ('FILLED_PROTECTED', 'FILLED_PROTECTION_INCOMPLETE', 'REJECTED', 'CANCELLED', 'UNKNOWN')", name="paper_run_resulting_outcome"),
        sa.UniqueConstraint("attempt_id", "run_sequence", name="uq_paper_runs_attempt_sequence"),
    )
    op.create_index("ix_paper_reconciliation_runs_attempt_created", "paper_reconciliation_runs", ["attempt_id", "created_at"])
    op.create_foreign_key(
        "fk_paper_execution_attempts_last_reconciliation_run",
        "paper_execution_attempts",
        "paper_reconciliation_runs",
        ["last_reconciliation_run_id"],
        ["run_id"],
        ondelete="RESTRICT",
    )

    op.create_table(
        "paper_broker_observations",
        sa.Column("observation_id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("attempt_id", UUID, nullable=False),
        sa.Column("mutation_claim_id", UUID),
        sa.Column("reconciliation_run_id", UUID),
        sa.Column("observation_sequence", sa.BigInteger, nullable=False),
        sa.Column("read_kind", sa.String(40), nullable=False),
        sa.Column("object_kind", sa.String(20), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("environment", sa.String(20), nullable=False),
        sa.Column("provider_account_id", sa.String(128), nullable=False),
        sa.Column("instrument", sa.String(20)),
        sa.Column("provider_order_id", sa.String(128)),
        sa.Column("provider_transaction_id", sa.String(64)),
        sa.Column("provider_trade_id", sa.String(128)),
        sa.Column("client_order_id", sa.String(128)),
        sa.Column("client_trade_id", sa.String(128)),
        sa.Column("client_protection_order_id", sa.String(128)),
        sa.Column("provider_type", sa.String(64)),
        sa.Column("provider_state", sa.String(64)),
        sa.Column("signed_units", NUMERIC),
        sa.Column("price", NUMERIC),
        sa.Column("executed_at", TS),
        sa.Column("request_id", sa.String(256)),
        sa.Column("batch_id", sa.String(128)),
        sa.Column("related_transaction_ids", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("last_transaction_id", sa.String(64)),
        sa.Column("provider_observed_at", TS),
        sa.Column("atlas_observed_at", TS, nullable=False),
        sa.Column("normalized_schema_version", sa.String(100), nullable=False),
        sa.Column("normalized_facts", JSONB, nullable=False),
        sa.Column("normalized_facts_fingerprint", sa.String(64), nullable=False),
        sa.PrimaryKeyConstraint("observation_id"),
        sa.ForeignKeyConstraint(["attempt_id"], ["paper_execution_attempts.attempt_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["mutation_claim_id"], ["paper_mutation_claims.claim_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reconciliation_run_id"], ["paper_reconciliation_runs.run_id"], ondelete="RESTRICT"),
        sa.CheckConstraint("observation_sequence > 0", name="paper_observation_sequence"),
        sa.CheckConstraint("read_kind IN ('ENTRY_MUTATION_RESPONSE', 'TAKE_PROFIT_MUTATION_RESPONSE', 'ORDER_DETAIL', 'TRANSACTION_DETAIL', 'TRANSACTION_RANGE', 'TRADE_DETAIL', 'ACCOUNT_DETAILS')", name="paper_observation_read_kind"),
        sa.CheckConstraint("object_kind IN ('ORDER', 'TRANSACTION', 'TRADE', 'ACCOUNT', 'MUTATION_RESULT')", name="paper_observation_object_kind"),
        sa.CheckConstraint("provider = 'OANDA' AND environment = 'PRACTICE'", name="paper_observation_scope"),
        sa.CheckConstraint("instrument IS NULL OR instrument = 'EUR_USD'", name="paper_observation_instrument"),
        sa.CheckConstraint("jsonb_typeof(normalized_facts) = 'object'", name="paper_observation_facts_object"),
        sa.CheckConstraint("jsonb_typeof(related_transaction_ids) = 'array' AND jsonb_array_length(related_transaction_ids) <= 64", name="paper_observation_related_ids"),
        sa.CheckConstraint("normalized_schema_version <> ''", name="paper_observation_schema_version"),
        sa.UniqueConstraint("attempt_id", "normalized_facts_fingerprint", name="uq_paper_observations_fact"),
        sa.UniqueConstraint("attempt_id", "observation_sequence", name="uq_paper_observations_sequence"),
    )
    op.create_index("ix_paper_broker_observations_attempt_kind", "paper_broker_observations", ["attempt_id", "read_kind"])

    # Claims and all provider facts are append-only.  Attempt evidence is
    # immutable while its explicitly named outcome/reconciliation projection
    # may advance through the repository's semantic guards.
    op.execute("""CREATE FUNCTION paper_mutation_claim_append_only() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'PAPER mutation claims are append-only'; END IF; RETURN NEW; END; $$""")
    op.execute("CREATE TRIGGER paper_mutation_claims_append_only BEFORE UPDATE OR DELETE ON paper_mutation_claims FOR EACH ROW EXECUTE FUNCTION paper_mutation_claim_append_only()")
    op.execute("""CREATE FUNCTION paper_broker_observation_append_only() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'PAPER broker observations are append-only'; END IF; RETURN NEW; END; $$""")
    op.execute("CREATE TRIGGER paper_broker_observations_append_only BEFORE UPDATE OR DELETE ON paper_broker_observations FOR EACH ROW EXECUTE FUNCTION paper_broker_observation_append_only()")
    op.execute("""CREATE FUNCTION paper_reconciliation_run_append_only() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'PAPER reconciliation runs are append-only'; END IF; RETURN NEW; END; $$""")
    op.execute("CREATE TRIGGER paper_reconciliation_runs_append_only BEFORE UPDATE OR DELETE ON paper_reconciliation_runs FOR EACH ROW EXECUTE FUNCTION paper_reconciliation_run_append_only()")
    op.execute("""CREATE FUNCTION paper_execution_attempt_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
      IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'PAPER execution attempts are immutable'; END IF;
      IF (to_jsonb(OLD) - ARRAY['fill_broker_order_id','fill_transaction_id','fill_trade_id','fill_signed_units','fill_price','fill_executed_at','fill_actual_initial_risk','actual_target_price','stop_loss_status','stop_loss_broker_order_id','stop_loss_client_order_id','stop_loss_price','stop_loss_provider_state','take_profit_status','take_profit_broker_order_id','take_profit_client_order_id','take_profit_price','take_profit_provider_state','execution_outcome','rejection_code','rejection_broker_order_id','rejection_transaction_id','uncertainty_code','reconciliation_status','reconciliation_block_code','last_reconciliation_run_id','last_reconciled_at','last_applied_transaction_id','projection_version','updated_at']) IS DISTINCT FROM (to_jsonb(NEW) - ARRAY['fill_broker_order_id','fill_transaction_id','fill_trade_id','fill_signed_units','fill_price','fill_executed_at','fill_actual_initial_risk','actual_target_price','stop_loss_status','stop_loss_broker_order_id','stop_loss_client_order_id','stop_loss_price','stop_loss_provider_state','take_profit_status','take_profit_broker_order_id','take_profit_client_order_id','take_profit_price','take_profit_provider_state','execution_outcome','rejection_code','rejection_broker_order_id','rejection_transaction_id','uncertainty_code','reconciliation_status','reconciliation_block_code','last_reconciliation_run_id','last_reconciled_at','last_applied_transaction_id','projection_version','updated_at']) THEN RAISE EXCEPTION 'PAPER attempt evidence is immutable'; END IF;
      IF OLD.fill_broker_order_id IS NOT NULL AND (to_jsonb(OLD) - ARRAY['actual_target_price','stop_loss_status','stop_loss_broker_order_id','stop_loss_client_order_id','stop_loss_price','stop_loss_provider_state','take_profit_status','take_profit_broker_order_id','take_profit_client_order_id','take_profit_price','take_profit_provider_state','execution_outcome','rejection_code','rejection_broker_order_id','rejection_transaction_id','uncertainty_code','reconciliation_status','reconciliation_block_code','last_reconciliation_run_id','last_reconciled_at','last_applied_transaction_id','projection_version','updated_at']) IS DISTINCT FROM (to_jsonb(NEW) - ARRAY['actual_target_price','stop_loss_status','stop_loss_broker_order_id','stop_loss_client_order_id','stop_loss_price','stop_loss_provider_state','take_profit_status','take_profit_broker_order_id','take_profit_client_order_id','take_profit_price','take_profit_provider_state','execution_outcome','rejection_code','rejection_broker_order_id','rejection_transaction_id','uncertainty_code','reconciliation_status','reconciliation_block_code','last_reconciliation_run_id','last_reconciled_at','last_applied_transaction_id','projection_version','updated_at']) THEN RAISE EXCEPTION 'PAPER Fill facts are immutable'; END IF;
      IF OLD.execution_outcome = 'FILLED_PROTECTED' AND NEW.execution_outcome <> 'FILLED_PROTECTED' THEN RAISE EXCEPTION 'FILLED_PROTECTED cannot be downgraded'; END IF;
      IF OLD.execution_outcome = 'FILLED_PROTECTION_INCOMPLETE' AND NEW.execution_outcome IN ('UNKNOWN','REJECTED','CANCELLED') THEN RAISE EXCEPTION 'proven PAPER Fill cannot be downgraded'; END IF;
      RETURN NEW;
    END; $$""")
    op.execute("CREATE TRIGGER paper_execution_attempt_guard BEFORE UPDATE OR DELETE ON paper_execution_attempts FOR EACH ROW EXECUTE FUNCTION paper_execution_attempt_guard()")


def downgrade() -> None:
    op.execute("DROP TRIGGER paper_broker_observations_append_only ON paper_broker_observations")
    op.execute("DROP FUNCTION paper_broker_observation_append_only()")
    op.execute("DROP TRIGGER paper_reconciliation_runs_append_only ON paper_reconciliation_runs")
    op.execute("DROP FUNCTION paper_reconciliation_run_append_only()")
    op.execute("DROP TRIGGER paper_mutation_claims_append_only ON paper_mutation_claims")
    op.execute("DROP FUNCTION paper_mutation_claim_append_only()")
    op.execute("DROP TRIGGER paper_execution_attempt_guard ON paper_execution_attempts")
    op.execute("DROP FUNCTION paper_execution_attempt_guard()")
    op.drop_table("paper_broker_observations")
    op.drop_constraint(
        "fk_paper_execution_attempts_last_reconciliation_run",
        "paper_execution_attempts",
        type_="foreignkey",
    )
    op.drop_index("ix_paper_reconciliation_runs_attempt_created", table_name="paper_reconciliation_runs")
    op.drop_table("paper_reconciliation_runs")
    op.drop_index("ix_paper_mutation_claims_attempt", table_name="paper_mutation_claims")
    op.drop_table("paper_mutation_claims")
    op.drop_index("ix_paper_execution_attempts_reconciliation", table_name="paper_execution_attempts")
    op.drop_index("ix_paper_execution_attempts_outcome", table_name="paper_execution_attempts")
    op.drop_table("paper_execution_attempts")
