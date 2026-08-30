"""Add the explicit Experiment deletion receipt and guarded delete context."""

# ruff: noqa: E501

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.naming import conv

revision = "0021_experiment_deletion"
down_revision = "0020_fix_snapshot_guard"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "experiment_deletion_receipts",
        sa.Column("receipt_id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("deleted_experiment_id", UUID, nullable=False),
        sa.Column("pre_delete_status", sa.String(20), nullable=False),
        sa.Column("strategy_id", UUID, nullable=False),
        sa.Column("strategy_version_id", UUID, nullable=False),
        sa.Column("strategy_source_fingerprint", sa.String(64), nullable=False),
        sa.Column("instrument", sa.String(20), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("trading_period_start", TS, nullable=False),
        sa.Column("trading_period_end", TS, nullable=False),
        sa.Column("deleted_at", TS, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("dataset_snapshot_id", UUID, nullable=False),
        sa.Column("snapshot_deleted", sa.Boolean, nullable=False),
        sa.Column("confirmation_schema_version", sa.String(100), nullable=False),
        sa.PrimaryKeyConstraint("receipt_id"),
        sa.UniqueConstraint("deleted_experiment_id"),
        sa.CheckConstraint("pre_delete_status IN ('PENDING', 'FAILED', 'COMPLETED')", name="deletable_pre_delete_status"),
        sa.CheckConstraint(
            "strategy_source_fingerprint ~ '^[0-9a-f]{64}$'",
            name=conv("ck_experiment_deletion_receipts_sha256_strategy_source__74ef"),
        ),
        sa.CheckConstraint(
            "confirmation_schema_version <> ''",
            name=conv("ck_experiment_deletion_receipts_confirmation_schema_ver_1fd5"),
        ),
    )
    op.execute(
        """CREATE FUNCTION atlas_deletion_context_matches(target UUID) RETURNS boolean
        LANGUAGE sql STABLE AS $$
          SELECT current_setting('atlas.experiment_deletion_id', true) = target::text
        $$"""
    )
    # Phase 3 installed these guards before Phase 4 added its more specific
    # guards.  PostgreSQL runs both trigger sets, so the legacy guards must
    # participate in the reviewed deletion context as well; otherwise a
    # populated graph is still rejected before the Phase 4 guards can allow it.
    op.execute("""CREATE OR REPLACE FUNCTION prevent_completed_trade_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
      IF TG_OP = 'DELETE' AND atlas_deletion_context_matches(OLD.experiment_id) THEN RETURN OLD; END IF;
      IF TG_OP = 'DELETE' OR OLD.status = 'COMPLETED' THEN RAISE EXCEPTION 'completed trades are immutable'; END IF;
      RETURN NEW;
    END; $$""")
    op.execute("""CREATE OR REPLACE FUNCTION prevent_order_fact_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
      IF TG_OP = 'DELETE' AND atlas_deletion_context_matches(OLD.experiment_id) THEN RETURN OLD; END IF;
      IF TG_OP = 'DELETE' OR (to_jsonb(OLD) - ARRAY['current_status','submitted_at']) IS DISTINCT FROM (to_jsonb(NEW) - ARRAY['current_status','submitted_at']) THEN RAISE EXCEPTION 'order facts are immutable'; END IF;
      RETURN NEW;
    END; $$""")
    op.execute("""CREATE OR REPLACE FUNCTION prevent_fact_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ DECLARE experiment UUID; BEGIN
      IF TG_TABLE_NAME = 'trade_intents' THEN experiment := OLD.experiment_id;
      ELSIF TG_TABLE_NAME = 'fills' THEN SELECT o.experiment_id INTO experiment FROM orders o WHERE o.id = OLD.order_id;
      ELSE SELECT ti.experiment_id INTO experiment FROM trade_intents ti WHERE ti.id = OLD.trade_intent_id;
      END IF;
      IF TG_OP = 'DELETE' AND atlas_deletion_context_matches(experiment) THEN RETURN OLD; END IF;
      RAISE EXCEPTION 'historical facts are immutable';
    END; $$""")
    op.execute("""CREATE OR REPLACE FUNCTION prevent_experiment_config_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
      IF TG_OP = 'DELETE' THEN
        IF atlas_deletion_context_matches(OLD.id) THEN RETURN OLD; END IF;
        RAISE EXCEPTION 'experiments are immutable';
      END IF;
      IF (to_jsonb(OLD) - ARRAY['status','completed_at','failure_category','failure_code','failure_detail']) IS DISTINCT FROM (to_jsonb(NEW) - ARRAY['status','completed_at','failure_category','failure_code','failure_detail']) THEN RAISE EXCEPTION 'experiment configuration is immutable'; END IF;
      IF OLD.status IN ('COMPLETED','FAILED') AND (to_jsonb(OLD) - ARRAY['status','completed_at']) IS DISTINCT FROM (to_jsonb(NEW) - ARRAY['status','completed_at']) THEN RAISE EXCEPTION 'terminal experiment is immutable'; END IF;
      RETURN NEW;
    END; $$""")
    op.execute("""CREATE OR REPLACE FUNCTION phase_4_append_only_guard() RETURNS trigger LANGUAGE plpgsql AS $$ DECLARE experiment UUID; BEGIN
      IF TG_TABLE_NAME = 'order_events' THEN SELECT o.experiment_id INTO experiment FROM orders o WHERE o.id = CASE WHEN TG_OP = 'DELETE' THEN OLD.order_id ELSE NEW.order_id END;
      ELSIF TG_TABLE_NAME IN ('experiment_equity_points', 'experiment_results') THEN experiment := CASE WHEN TG_OP = 'DELETE' THEN OLD.experiment_id ELSE NEW.experiment_id END;
      ELSIF TG_TABLE_NAME = 'fills' THEN SELECT o.experiment_id INTO experiment FROM orders o WHERE o.id = CASE WHEN TG_OP = 'DELETE' THEN OLD.order_id ELSE NEW.order_id END;
      ELSIF TG_TABLE_NAME = 'trade_intents' THEN experiment := CASE WHEN TG_OP = 'DELETE' THEN OLD.experiment_id ELSE NEW.experiment_id END;
      ELSE SELECT ti.experiment_id INTO experiment FROM trade_intents ti WHERE ti.id = CASE WHEN TG_OP = 'DELETE' THEN OLD.trade_intent_id ELSE NEW.trade_intent_id END;
      END IF;
      IF TG_OP <> 'INSERT' THEN
        IF atlas_deletion_context_matches(experiment) THEN RETURN OLD; END IF;
        RAISE EXCEPTION 'historical facts are immutable';
      END IF;
      IF EXISTS (SELECT 1 FROM experiments WHERE id = experiment AND status IN ('COMPLETED','FAILED')) THEN RAISE EXCEPTION 'terminal experiment graph is immutable'; END IF;
      RETURN NEW;
    END; $$""")
    op.execute("""CREATE OR REPLACE FUNCTION phase_4_order_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
      IF TG_OP = 'DELETE' THEN
        IF atlas_deletion_context_matches(OLD.experiment_id) THEN RETURN OLD; END IF;
        RAISE EXCEPTION 'terminal order is immutable';
      END IF;
      IF OLD.current_status IN ('FILLED','CANCELED','REJECTED','EXPIRED','UNKNOWN') THEN RAISE EXCEPTION 'terminal order is immutable'; END IF;
      IF (to_jsonb(OLD) - ARRAY['current_status','submitted_at']) IS DISTINCT FROM (to_jsonb(NEW) - ARRAY['current_status','submitted_at']) THEN RAISE EXCEPTION 'order facts are immutable'; END IF;
      RETURN NEW;
    END; $$""")
    op.execute("""CREATE OR REPLACE FUNCTION phase_4_terminal_projection_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
      IF TG_OP = 'DELETE' AND atlas_deletion_context_matches(OLD.experiment_id) THEN RETURN OLD; END IF;
      IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'terminal experiment projection is immutable'; END IF;
      IF EXISTS (SELECT 1 FROM experiments WHERE id = OLD.experiment_id AND status IN ('COMPLETED','FAILED')) THEN RAISE EXCEPTION 'terminal experiment projection is immutable'; END IF;
      RETURN NEW;
    END; $$""")
    op.execute("""CREATE OR REPLACE FUNCTION experiment_gap_decision_append_only() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
      IF TG_OP = 'DELETE' AND atlas_deletion_context_matches(OLD.experiment_id) THEN RETURN OLD; END IF;
      IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'experiment gap decisions are immutable'; END IF;
      RETURN NEW;
    END; $$""")
    op.execute("""CREATE OR REPLACE FUNCTION snapshot_v2_append_only_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
      IF TG_OP = 'DELETE' AND atlas_deletion_context_matches(OLD.dataset_snapshot_id) THEN RETURN OLD; END IF;
      IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'dataset snapshot memberships are immutable'; END IF;
      IF NOT EXISTS (SELECT 1 FROM dataset_snapshots WHERE id = NEW.dataset_snapshot_id AND snapshot_schema = 'ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2') THEN RAISE EXCEPTION 'V2 membership requires a V2 snapshot'; END IF;
      IF TG_TABLE_NAME = 'dataset_snapshot_execution_observations' AND NOT EXISTS (SELECT 1 FROM market_bars WHERE id = NEW.market_bar_id AND resolution = 'M1' AND price_component = NEW.price_component AND complete IS TRUE) THEN RAISE EXCEPTION 'execution membership must reference a completed matching M1 observation'; END IF;
      RETURN NEW;
    END; $$""")
    op.execute("""CREATE OR REPLACE FUNCTION prevent_dataset_snapshot_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
      IF TG_OP = 'DELETE' AND atlas_deletion_context_matches(OLD.id) THEN RETURN OLD; END IF;
      RAISE EXCEPTION 'dataset_snapshots are immutable';
    END; $$""")
    op.execute("""CREATE OR REPLACE FUNCTION prevent_dataset_snapshot_bar_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
      IF TG_OP = 'DELETE' AND atlas_deletion_context_matches(OLD.dataset_snapshot_id) THEN RETURN OLD; END IF;
      RAISE EXCEPTION 'dataset_snapshot_bars are immutable';
    END; $$""")
    op.execute(
        """CREATE FUNCTION experiment_deletion_receipt_append_only() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
          IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'experiment deletion receipts are append-only'; END IF;
          RETURN NEW;
        END; $$"""
    )
    op.execute(
        """CREATE TRIGGER experiment_deletion_receipts_append_only
        BEFORE UPDATE OR DELETE ON experiment_deletion_receipts
        FOR EACH ROW EXECUTE FUNCTION experiment_deletion_receipt_append_only()"""
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER experiment_deletion_receipts_append_only ON experiment_deletion_receipts")
    op.execute("DROP FUNCTION experiment_deletion_receipt_append_only()")
    op.drop_table("experiment_deletion_receipts")
    # Restore the exact trigger bodies owned by the schema at 0020 before
    # removing the deletion-only helper they no longer reference. Trigger
    # definitions survive this revision, so merely dropping the helper would
    # leave every guarded DML path broken after downgrade.
    op.execute("""CREATE OR REPLACE FUNCTION prevent_experiment_config_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
      IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'experiments are immutable'; END IF;
      IF OLD.status IN ('COMPLETED','FAILED') AND (to_jsonb(OLD) - ARRAY['status','completed_at']) IS DISTINCT FROM (to_jsonb(NEW) - ARRAY['status','completed_at']) THEN RAISE EXCEPTION 'terminal experiment is immutable'; END IF;
      IF (to_jsonb(OLD) - ARRAY['status','completed_at','failure_category','failure_code','failure_detail']) IS DISTINCT FROM (to_jsonb(NEW) - ARRAY['status','completed_at','failure_category','failure_code','failure_detail']) THEN RAISE EXCEPTION 'experiment configuration is immutable'; END IF;
      RETURN NEW;
    END; $$""")
    op.execute("""CREATE OR REPLACE FUNCTION prevent_completed_trade_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF TG_OP = 'DELETE' OR OLD.status = 'COMPLETED' THEN RAISE EXCEPTION 'completed trades are immutable'; END IF; RETURN NEW; END; $$""")
    op.execute("""CREATE OR REPLACE FUNCTION prevent_order_fact_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF TG_OP = 'DELETE' OR (to_jsonb(OLD) - ARRAY['current_status','submitted_at']) IS DISTINCT FROM (to_jsonb(NEW) - ARRAY['current_status','submitted_at']) THEN RAISE EXCEPTION 'order facts are immutable'; END IF; RETURN NEW; END; $$""")
    op.execute("""CREATE OR REPLACE FUNCTION prevent_fact_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'historical facts are immutable'; END; $$""")
    op.execute("""CREATE OR REPLACE FUNCTION phase_4_append_only_guard() RETURNS trigger LANGUAGE plpgsql AS $$ DECLARE experiment UUID; BEGIN
      IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'historical facts are immutable'; END IF;
      IF TG_TABLE_NAME = 'order_events' THEN SELECT o.experiment_id INTO experiment FROM orders o WHERE o.id = NEW.order_id;
      ELSIF TG_TABLE_NAME = 'experiment_equity_points' OR TG_TABLE_NAME = 'experiment_results' THEN experiment := NEW.experiment_id;
      ELSIF TG_TABLE_NAME = 'fills' THEN SELECT o.experiment_id INTO experiment FROM orders o WHERE o.id = NEW.order_id;
      ELSIF TG_TABLE_NAME = 'trade_intents' THEN experiment := NEW.experiment_id;
      ELSE SELECT ti.experiment_id INTO experiment FROM trade_intents ti WHERE ti.id = NEW.trade_intent_id;
      END IF;
      IF EXISTS (SELECT 1 FROM experiments WHERE id = experiment AND status IN ('COMPLETED','FAILED')) THEN RAISE EXCEPTION 'terminal experiment graph is immutable'; END IF;
      RETURN NEW;
    END; $$""")
    op.execute("""CREATE OR REPLACE FUNCTION phase_4_order_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
      IF TG_OP <> 'UPDATE' OR OLD.current_status IN ('FILLED','CANCELED','REJECTED','EXPIRED','UNKNOWN') THEN RAISE EXCEPTION 'terminal order is immutable'; END IF;
      IF (to_jsonb(OLD) - ARRAY['current_status','submitted_at']) IS DISTINCT FROM (to_jsonb(NEW) - ARRAY['current_status','submitted_at']) THEN RAISE EXCEPTION 'order facts are immutable'; END IF;
      RETURN NEW;
    END; $$""")
    op.execute("""CREATE OR REPLACE FUNCTION phase_4_terminal_projection_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
      IF EXISTS (SELECT 1 FROM experiments WHERE id = OLD.experiment_id AND status IN ('COMPLETED','FAILED')) THEN RAISE EXCEPTION 'terminal experiment projection is immutable'; END IF;
      RETURN NEW;
    END; $$""")
    op.execute("""CREATE OR REPLACE FUNCTION experiment_gap_decision_append_only() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
      IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'experiment gap decisions are immutable'; END IF;
      RETURN NEW;
    END; $$""")
    op.execute("""CREATE OR REPLACE FUNCTION snapshot_v2_append_only_guard() RETURNS trigger
    LANGUAGE plpgsql AS $$ BEGIN
      IF TG_OP = 'INSERT' THEN
        RAISE EXCEPTION 'insert validation must use the statement trigger';
      END IF;
      RAISE EXCEPTION 'dataset snapshot memberships are immutable';
    END; $$""")
    op.execute("""CREATE OR REPLACE FUNCTION prevent_dataset_snapshot_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN RAISE EXCEPTION 'dataset_snapshots are immutable'; END; $$""")
    op.execute("""CREATE OR REPLACE FUNCTION prevent_dataset_snapshot_bar_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN RAISE EXCEPTION 'dataset_snapshot_bars are immutable'; END; $$""")
    op.execute("DROP FUNCTION atlas_deletion_context_matches(UUID)")
