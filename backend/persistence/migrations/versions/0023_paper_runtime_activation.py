"""Add the durable PAPER runtime activation, cycle, and ownership projection."""

# fmt: off
# ruff: noqa: E501

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0023_paper_runtime_activation"
down_revision = "0022_paper_persistence"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB
NUMERIC = sa.Numeric()
TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "paper_runtime_activations",
        sa.Column("activation_id", UUID, nullable=False),
        sa.Column("strategy_version_id", UUID, nullable=False),
        sa.Column("strategy_key", sa.String(200), nullable=False),
        sa.Column("strategy_version_number", sa.Integer, nullable=False),
        sa.Column("source_fingerprint", sa.String(64), nullable=False),
        sa.Column("implementation_key", sa.String(200), nullable=False),
        sa.Column("validated_parameter_snapshot", JSONB, nullable=False),
        sa.Column("parameter_fingerprint", sa.String(64), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("environment", sa.String(20), nullable=False),
        sa.Column("provider_account_id", sa.String(128), nullable=False),
        sa.Column("base_currency", sa.String(3), nullable=False),
        sa.Column("instrument", sa.String(20), nullable=False),
        sa.Column("risk_per_trade", NUMERIC, nullable=False),
        sa.Column("state_origin", sa.String(32), nullable=False),
        sa.Column("runtime_policy_version", sa.String(100), nullable=False),
        sa.Column("poll_interval_seconds", sa.Integer, nullable=False),
        sa.Column("approval_kind", sa.String(64), nullable=False),
        sa.Column("approval_code", sa.String(64), nullable=False),
        sa.Column("requested_at", TS, nullable=False),
        sa.Column("lifecycle_state", sa.String(24), nullable=False),
        sa.Column("state_reason_code", sa.String(64)),
        sa.Column("state_detail", sa.String(500)),
        sa.Column("state_changed_at", TS, nullable=False),
        sa.Column("operational_phase", sa.String(32), nullable=False),
        sa.Column("last_operational_reason_code", sa.String(64)),
        sa.Column("last_operational_at", TS),
        sa.Column("strategy_state", JSONB),
        sa.Column("strategy_state_fingerprint", sa.String(64)),
        sa.Column("last_frontier_end", TS),
        sa.Column("last_cycle_id", UUID),
        sa.Column("control_version", sa.BigInteger, server_default=sa.text("0"), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("activation_id"),
        sa.ForeignKeyConstraint(
            ["strategy_version_id"], ["strategy_versions.id"], ondelete="RESTRICT"
        ),
        sa.CheckConstraint("provider = 'OANDA'", name="paper_runtime_provider"),
        sa.CheckConstraint("environment = 'PRACTICE'", name="paper_runtime_environment"),
        sa.CheckConstraint("base_currency = 'USD'", name="paper_runtime_base_currency"),
        sa.CheckConstraint("instrument = 'EUR_USD'", name="paper_runtime_instrument"),
        sa.CheckConstraint("strategy_version_number > 0", name="paper_runtime_version_positive"),
        sa.CheckConstraint("source_fingerprint ~ '^[0-9a-f]{64}$'", name="paper_runtime_source_fingerprint"),
        sa.CheckConstraint("parameter_fingerprint ~ '^[0-9a-f]{64}$'", name="paper_runtime_parameter_fingerprint"),
        sa.CheckConstraint(
            "risk_per_trade > 0 AND risk_per_trade < 1 AND risk_per_trade <> 'NaN'::numeric "
            "AND risk_per_trade <> 'Infinity'::numeric AND risk_per_trade <> '-Infinity'::numeric",
            name="paper_runtime_risk_positive_finite",
        ),
        sa.CheckConstraint("state_origin = 'FRESH_BOOTSTRAP'", name="paper_runtime_state_origin"),
        sa.CheckConstraint("runtime_policy_version = 'ATLAS_PAPER_RUNTIME_V1'", name="paper_runtime_policy_version"),
        sa.CheckConstraint("poll_interval_seconds = 15", name="paper_runtime_poll_interval"),
        sa.CheckConstraint("approval_kind = 'EXPLICIT_LOCAL_TRADER'", name="paper_runtime_approval_kind"),
        sa.CheckConstraint("approval_code = 'ACTIVATE_PAPER'", name="paper_runtime_approval_code"),
        sa.CheckConstraint(
            "lifecycle_state IN ('REQUESTED', 'STARTING', 'RUNNING', 'STOP_REQUESTED', 'STOPPED', 'BLOCKED', 'FAILED')",
            name="paper_runtime_lifecycle_state",
        ),
        sa.CheckConstraint(
            "operational_phase IN ('IDLE', 'STARTING', 'WAITING_FRONTIER', 'WAITING_DATA', 'WAITING_PROVIDER', 'EVALUATING', 'EXECUTING', 'RECOVERING', 'STOPPING', 'BLOCKED', 'FAILED')",
            name="paper_runtime_operational_phase",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(validated_parameter_snapshot) = 'object' AND octet_length(validated_parameter_snapshot::text) <= 32768",
            name="paper_runtime_parameters_object_bounded",
        ),
        sa.CheckConstraint(
            "strategy_state IS NULL OR (jsonb_typeof(strategy_state) = 'object' AND octet_length(strategy_state::text) <= 32768)",
            name="paper_runtime_state_object_bounded",
        ),
        sa.CheckConstraint(
            "strategy_state_fingerprint IS NULL OR strategy_state_fingerprint ~ '^[0-9a-f]{64}$'",
            name="paper_runtime_state_fingerprint",
        ),
        sa.CheckConstraint("control_version >= 0", name="paper_runtime_control_version"),
    )
    op.create_index(
        "uq_paper_runtime_nonterminal_activation",
        "paper_runtime_activations",
        [sa.text("(1)")],
        unique=True,
        postgresql_where=sa.text(
            "lifecycle_state IN ('REQUESTED', 'STARTING', 'RUNNING', 'STOP_REQUESTED')"
        ),
    )

    op.create_table(
        "paper_runtime_cycles",
        sa.Column("cycle_id", UUID, nullable=False),
        sa.Column("activation_id", UUID, nullable=False),
        sa.Column("cycle_sequence", sa.BigInteger, nullable=False),
        sa.Column("evaluation_key", sa.String(256), nullable=False),
        sa.Column("strategy_version_id", UUID, nullable=False),
        sa.Column("parameter_fingerprint", sa.String(64), nullable=False),
        sa.Column("frontier_start", TS, nullable=False),
        sa.Column("frontier_end", TS, nullable=False),
        sa.Column("prior_frontier_end", TS),
        sa.Column("state_before", JSONB),
        sa.Column("state_before_fingerprint", sa.String(64)),
        sa.Column("state_after", JSONB),
        sa.Column("state_after_fingerprint", sa.String(64)),
        sa.Column("financial_position_state", sa.String(10), nullable=False),
        sa.Column("account_transaction_id", sa.String(64), nullable=False),
        sa.Column("account_observed_at", TS, nullable=False),
        sa.Column("account_open_trade_count", sa.Integer, nullable=False),
        sa.Column("account_open_position_count", sa.Integer, nullable=False),
        sa.Column("account_pending_order_count", sa.Integer, nullable=False),
        sa.Column("account_gate_fingerprint", sa.String(64), nullable=False),
        sa.Column("strategy_evaluation_snapshot", JSONB),
        sa.Column("decision_snapshot", JSONB),
        sa.Column("attempt_id", UUID),
        sa.Column("cycle_status", sa.String(32), nullable=False),
        sa.Column("cycle_reason_code", sa.String(64)),
        sa.Column("claimed_at", TS, nullable=False),
        sa.Column("evaluated_at", TS),
        sa.Column("completed_at", TS),
        sa.Column("updated_at", TS, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("cycle_id"),
        sa.ForeignKeyConstraint(
            ["activation_id"], ["paper_runtime_activations.activation_id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["strategy_version_id"], ["strategy_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id"], ["paper_execution_attempts.attempt_id"], ondelete="RESTRICT"
        ),
        sa.CheckConstraint("cycle_sequence > 0", name="paper_runtime_cycle_sequence"),
        sa.CheckConstraint(
            "length(evaluation_key) BETWEEN 1 AND 256 AND evaluation_key !~ '[[:cntrl:]]'",
            name="paper_runtime_cycle_evaluation_key",
        ),
        sa.CheckConstraint("parameter_fingerprint ~ '^[0-9a-f]{64}$'", name="paper_runtime_cycle_parameter_fingerprint"),
        sa.CheckConstraint("account_gate_fingerprint ~ '^[0-9a-f]{64}$'", name="paper_runtime_cycle_account_fingerprint"),
        sa.CheckConstraint("frontier_end > frontier_start", name="paper_runtime_cycle_frontier_interval"),
        sa.CheckConstraint("prior_frontier_end IS NULL OR prior_frontier_end < frontier_end", name="paper_runtime_cycle_prior_frontier"),
        sa.CheckConstraint("financial_position_state IN ('FLAT', 'LONG', 'SHORT')", name="paper_runtime_cycle_position_state"),
        sa.CheckConstraint(
            "account_open_trade_count >= 0 AND account_open_position_count >= 0 AND account_pending_order_count >= 0",
            name="paper_runtime_cycle_account_counts",
        ),
        sa.CheckConstraint(
            "(financial_position_state = 'FLAT' AND account_open_trade_count = 0 AND account_open_position_count = 0) OR "
            "(financial_position_state IN ('LONG', 'SHORT') AND (account_open_trade_count > 0 OR account_open_position_count > 0))",
            name="paper_runtime_cycle_position_counts",
        ),
        sa.CheckConstraint(
            "state_before IS NULL OR (jsonb_typeof(state_before) = 'object' AND octet_length(state_before::text) <= 32768)",
            name="paper_runtime_cycle_state_before",
        ),
        sa.CheckConstraint(
            "state_after IS NULL OR (jsonb_typeof(state_after) = 'object' AND octet_length(state_after::text) <= 32768)",
            name="paper_runtime_cycle_state_after",
        ),
        sa.CheckConstraint(
            "strategy_evaluation_snapshot IS NULL OR (jsonb_typeof(strategy_evaluation_snapshot) = 'object' AND octet_length(strategy_evaluation_snapshot::text) <= 32768)",
            name="paper_runtime_cycle_evaluation_bounded",
        ),
        sa.CheckConstraint(
            "decision_snapshot IS NULL OR (jsonb_typeof(decision_snapshot) = 'object' AND octet_length(decision_snapshot::text) <= 32768)",
            name="paper_runtime_cycle_decision_bounded",
        ),
        sa.CheckConstraint("state_before_fingerprint IS NULL OR state_before_fingerprint ~ '^[0-9a-f]{64}$'", name="paper_runtime_cycle_state_before_fingerprint"),
        sa.CheckConstraint("state_after_fingerprint IS NULL OR state_after_fingerprint ~ '^[0-9a-f]{64}$'", name="paper_runtime_cycle_state_after_fingerprint"),
        sa.CheckConstraint(
            "cycle_status IN ('CLAIMED', 'EVALUATING', 'NO_ACTION', 'REFUSED', 'ENTRY_CLAIMED', 'ENTRY_RESOLVED', 'TAKE_PROFIT_CLAIMED', 'COMPLETE', 'RECOVERY_REQUIRED', 'BLOCKED')",
            name="paper_runtime_cycle_status",
        ),
        sa.UniqueConstraint("evaluation_key", "frontier_end", name="uq_paper_runtime_cycles_evaluation_frontier"),
        sa.UniqueConstraint("activation_id", "cycle_sequence", name="uq_paper_runtime_cycles_activation_sequence"),
        sa.UniqueConstraint("activation_id", "frontier_end", name="uq_paper_runtime_cycles_activation_frontier"),
    )
    op.create_index(
        "ix_paper_runtime_cycles_activation_status",
        "paper_runtime_cycles",
        ["activation_id", "cycle_status"],
    )

    op.create_table(
        "paper_runtime_ownership",
        sa.Column("slot_key", sa.String(32), nullable=False),
        sa.Column("owner_id", UUID, nullable=False),
        sa.Column("activation_id", UUID),
        sa.Column("owner_generation", sa.BigInteger, nullable=False),
        sa.Column("acquired_at", TS, nullable=False),
        sa.Column("heartbeat_at", TS, nullable=False),
        sa.Column("phase", sa.String(24), nullable=False),
        sa.PrimaryKeyConstraint("slot_key"),
        sa.ForeignKeyConstraint(
            ["activation_id"], ["paper_runtime_activations.activation_id"], ondelete="RESTRICT"
        ),
        sa.CheckConstraint("slot_key = 'ATLAS_PAPER_RUNTIME'", name="paper_runtime_ownership_slot"),
        sa.CheckConstraint("owner_generation > 0", name="paper_runtime_owner_generation"),
        sa.CheckConstraint(
            "phase IN ('ACQUIRED', 'STARTING', 'RUNNING', 'STOP_REQUESTED', 'STOPPING', 'STOPPED', 'BLOCKED', 'FAILED')",
            name="paper_runtime_ownership_phase",
        ),
    )

    op.create_foreign_key(
        "fk_paper_runtime_activations_last_cycle",
        "paper_runtime_activations",
        "paper_runtime_cycles",
        ["last_cycle_id"],
        ["cycle_id"],
        ondelete="RESTRICT",
    )

    op.execute("""CREATE FUNCTION paper_runtime_activation_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'PAPER runtime activations are immutable'; END IF;
      IF (to_jsonb(OLD) - ARRAY['lifecycle_state','state_reason_code','state_detail','state_changed_at','operational_phase','last_operational_reason_code','last_operational_at','strategy_state','strategy_state_fingerprint','last_frontier_end','last_cycle_id','control_version','updated_at']) IS DISTINCT FROM
         (to_jsonb(NEW) - ARRAY['lifecycle_state','state_reason_code','state_detail','state_changed_at','operational_phase','last_operational_reason_code','last_operational_at','strategy_state','strategy_state_fingerprint','last_frontier_end','last_cycle_id','control_version','updated_at']) THEN
        RAISE EXCEPTION 'PAPER runtime activation configuration is immutable';
      END IF;
      RETURN NEW;
    END; $$""")
    op.execute("CREATE TRIGGER paper_runtime_activation_guard BEFORE UPDATE OR DELETE ON paper_runtime_activations FOR EACH ROW EXECUTE FUNCTION paper_runtime_activation_guard()")

    op.execute("""CREATE FUNCTION paper_runtime_cycle_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'PAPER runtime cycles are immutable'; END IF;
      IF (to_jsonb(OLD) - ARRAY['state_after','state_after_fingerprint','strategy_evaluation_snapshot','decision_snapshot','attempt_id','cycle_status','cycle_reason_code','evaluated_at','completed_at','updated_at']) IS DISTINCT FROM
         (to_jsonb(NEW) - ARRAY['state_after','state_after_fingerprint','strategy_evaluation_snapshot','decision_snapshot','attempt_id','cycle_status','cycle_reason_code','evaluated_at','completed_at','updated_at']) THEN
        RAISE EXCEPTION 'PAPER runtime cycle identity/evidence is immutable';
      END IF;
      RETURN NEW;
    END; $$""")
    op.execute("CREATE TRIGGER paper_runtime_cycle_guard BEFORE UPDATE OR DELETE ON paper_runtime_cycles FOR EACH ROW EXECUTE FUNCTION paper_runtime_cycle_guard()")

    op.execute("""CREATE FUNCTION paper_runtime_ownership_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'PAPER runtime ownership projection is immutable'; END IF;
      IF OLD.slot_key <> NEW.slot_key THEN RAISE EXCEPTION 'PAPER runtime ownership slot is immutable'; END IF;
      RETURN NEW;
    END; $$""")
    op.execute("CREATE TRIGGER paper_runtime_ownership_guard BEFORE UPDATE OR DELETE ON paper_runtime_ownership FOR EACH ROW EXECUTE FUNCTION paper_runtime_ownership_guard()")


def downgrade() -> None:
    op.execute("DROP TRIGGER paper_runtime_ownership_guard ON paper_runtime_ownership")
    op.execute("DROP FUNCTION paper_runtime_ownership_guard()")
    op.execute("DROP TRIGGER paper_runtime_cycle_guard ON paper_runtime_cycles")
    op.execute("DROP FUNCTION paper_runtime_cycle_guard()")
    op.execute("DROP TRIGGER paper_runtime_activation_guard ON paper_runtime_activations")
    op.execute("DROP FUNCTION paper_runtime_activation_guard()")
    op.drop_constraint(
        "fk_paper_runtime_activations_last_cycle",
        "paper_runtime_activations",
        type_="foreignkey",
    )
    op.drop_table("paper_runtime_ownership")
    op.drop_index("ix_paper_runtime_cycles_activation_status", table_name="paper_runtime_cycles")
    op.drop_table("paper_runtime_cycles")
    op.drop_index("uq_paper_runtime_nonterminal_activation", table_name="paper_runtime_activations")
    op.drop_table("paper_runtime_activations")
