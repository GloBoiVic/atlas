"""Add durable Account Changes receipts for the PAPER cursor fence."""

# ruff: noqa: E501

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0026_oanda_transaction_receipts"
down_revision = "0025_restart_continuity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # An OANDA PAPER entry is durably PENDING_SUBMISSION before the provider
    # reveals its immutable execution identities.  Preserve historical Order
    # immutability while allowing that one bounded identity capture before the
    # Order reaches a terminal state.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION phase_4_order_guard() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'UPDATE'
             AND OLD.deployment_id IS NOT NULL
             AND OLD.current_status = 'PENDING_SUBMISSION'
             AND OLD.external_trade_ids = '[]'::jsonb
             AND OLD.related_transaction_ids = '[]'::jsonb
             AND (to_jsonb(OLD) - ARRAY[
               'current_status', 'submitted_at', 'external_order_id',
               'external_trade_ids', 'related_transaction_ids',
               'provider_request_id'
             ]) IS NOT DISTINCT FROM (to_jsonb(NEW) - ARRAY[
               'current_status', 'submitted_at', 'external_order_id',
               'external_trade_ids', 'related_transaction_ids',
               'provider_request_id'
             ])
          THEN
            RETURN NEW;
          END IF;
          IF TG_OP <> 'UPDATE'
             OR OLD.current_status IN ('FILLED','CANCELED','REJECTED','EXPIRED','UNKNOWN')
          THEN
            RAISE EXCEPTION 'terminal order is immutable';
          END IF;
          IF (to_jsonb(OLD) - ARRAY['current_status','submitted_at'])
             IS DISTINCT FROM (to_jsonb(NEW) - ARRAY['current_status','submitted_at'])
          THEN
            RAISE EXCEPTION 'order facts are immutable';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_order_fact_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'DELETE' AND atlas_deletion_context_matches(OLD.experiment_id) THEN
            RETURN OLD;
          END IF;
          IF TG_OP = 'UPDATE'
             AND OLD.deployment_id IS NOT NULL
             AND OLD.current_status = 'PENDING_SUBMISSION'
             AND OLD.external_trade_ids = '[]'::jsonb
             AND OLD.related_transaction_ids = '[]'::jsonb
             AND (to_jsonb(OLD) - ARRAY[
               'current_status', 'submitted_at', 'external_order_id',
               'external_trade_ids', 'related_transaction_ids',
               'provider_request_id'
             ]) IS NOT DISTINCT FROM (to_jsonb(NEW) - ARRAY[
               'current_status', 'submitted_at', 'external_order_id',
               'external_trade_ids', 'related_transaction_ids',
               'provider_request_id'
             ])
          THEN
            RETURN NEW;
          END IF;
          IF TG_OP = 'DELETE'
             OR (to_jsonb(OLD) - ARRAY['current_status','submitted_at'])
                IS DISTINCT FROM (to_jsonb(NEW) - ARRAY['current_status','submitted_at'])
          THEN
            RAISE EXCEPTION 'order facts are immutable';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_fact_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE experiment UUID;
        BEGIN
          IF TG_TABLE_NAME = 'trade_intents' THEN
            IF TG_OP = 'UPDATE'
               AND OLD.deployment_id IS NOT NULL
               AND OLD.proposal_status = 'PENDING'
               AND NEW.proposal_status = 'FILLED'
               AND (to_jsonb(OLD) - ARRAY['proposal_status'])
                  IS NOT DISTINCT FROM (to_jsonb(NEW) - ARRAY['proposal_status'])
            THEN
              RETURN NEW;
            END IF;
          END IF;
          IF TG_TABLE_NAME = 'trade_intents' THEN
            experiment := OLD.experiment_id;
          ELSIF TG_TABLE_NAME = 'fills' THEN
            SELECT o.experiment_id INTO experiment FROM orders o WHERE o.id = OLD.order_id;
          ELSE
            SELECT ti.experiment_id INTO experiment
              FROM trade_intents ti WHERE ti.id = OLD.trade_intent_id;
          END IF;
          IF TG_OP = 'DELETE' AND atlas_deletion_context_matches(experiment) THEN
            RETURN OLD;
          END IF;
          RAISE EXCEPTION 'historical facts are immutable';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION phase_4_append_only_guard() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE experiment UUID;
        BEGIN
          IF TG_TABLE_NAME = 'trade_intents' THEN
            IF TG_OP = 'UPDATE'
               AND OLD.deployment_id IS NOT NULL
               AND OLD.proposal_status = 'PENDING'
               AND NEW.proposal_status = 'FILLED'
               AND (to_jsonb(OLD) - ARRAY['proposal_status'])
                  IS NOT DISTINCT FROM (to_jsonb(NEW) - ARRAY['proposal_status'])
            THEN
              RETURN NEW;
            END IF;
          END IF;
          IF TG_TABLE_NAME = 'order_events' THEN
            SELECT o.experiment_id INTO experiment FROM orders o
              WHERE o.id = CASE WHEN TG_OP = 'DELETE' THEN OLD.order_id ELSE NEW.order_id END;
          ELSIF TG_TABLE_NAME IN ('experiment_equity_points', 'experiment_results') THEN
            experiment := CASE WHEN TG_OP = 'DELETE' THEN OLD.experiment_id ELSE NEW.experiment_id END;
          ELSIF TG_TABLE_NAME = 'fills' THEN
            SELECT o.experiment_id INTO experiment FROM orders o
              WHERE o.id = CASE WHEN TG_OP = 'DELETE' THEN OLD.order_id ELSE NEW.order_id END;
          ELSIF TG_TABLE_NAME = 'trade_intents' THEN
            experiment := CASE WHEN TG_OP = 'DELETE' THEN OLD.experiment_id ELSE NEW.experiment_id END;
          ELSE
            SELECT ti.experiment_id INTO experiment FROM trade_intents ti
              WHERE ti.id = CASE WHEN TG_OP = 'DELETE' THEN OLD.trade_intent_id ELSE NEW.trade_intent_id END;
          END IF;
          IF TG_OP <> 'INSERT' THEN
            IF atlas_deletion_context_matches(experiment) THEN
              RETURN OLD;
            END IF;
            RAISE EXCEPTION 'historical facts are immutable';
          END IF;
          IF EXISTS (
            SELECT 1 FROM experiments WHERE id = experiment AND status IN ('COMPLETED','FAILED')
          ) THEN
            RAISE EXCEPTION 'terminal experiment graph is immutable';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.create_table(
        "oanda_transaction_receipts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "trading_account_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column(
            "external_transaction_id", sa.String(length=80), nullable=False
        ),
        sa.Column("transaction_type", sa.String(length=80), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("instrument", sa.String(length=20), nullable=True),
        sa.Column("external_order_id", sa.String(length=100), nullable=True),
        sa.Column("external_trade_id", sa.String(length=100), nullable=True),
        sa.Column("normalized_digest", sa.String(length=64), nullable=False),
        sa.Column("disposition", sa.String(length=30), nullable=False),
        sa.Column("canonical_order_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("canonical_fill_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "external_transaction_id ~ '^[0-9]+$'",
            name=op.f("ck_oanda_transaction_receipts_oanda_tx_receipt_id"),
        ),
        sa.CheckConstraint(
            "normalized_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_oanda_transaction_receipts_oanda_tx_receipt_digest"),
        ),
        sa.CheckConstraint(
            "disposition IN "
            "('APPLIED','IDEMPOTENT','OBSERVED_NO_PROJECTION',"
            "'IGNORED_OTHER_INSTRUMENT')",
            name=op.f("ck_oanda_transaction_receipts_oanda_tx_receipt_disposition"),
        ),
        sa.ForeignKeyConstraint(
            ["trading_account_id"], ["trading_accounts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["canonical_order_id"], ["orders.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["canonical_fill_id"], ["fills.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "trading_account_id",
            "external_transaction_id",
            name="uq_oanda_transaction_receipts_account_transaction",
        ),
    )


def downgrade() -> None:
    op.drop_table("oanda_transaction_receipts")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION phase_4_order_guard() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP <> 'UPDATE'
             OR OLD.current_status IN ('FILLED','CANCELED','REJECTED','EXPIRED','UNKNOWN')
          THEN
            RAISE EXCEPTION 'terminal order is immutable';
          END IF;
          IF (to_jsonb(OLD) - ARRAY['current_status','submitted_at'])
             IS DISTINCT FROM (to_jsonb(NEW) - ARRAY['current_status','submitted_at'])
          THEN
            RAISE EXCEPTION 'order facts are immutable';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_order_fact_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'DELETE' AND atlas_deletion_context_matches(OLD.experiment_id) THEN
            RETURN OLD;
          END IF;
          IF TG_OP = 'DELETE'
             OR (to_jsonb(OLD) - ARRAY['current_status','submitted_at'])
                IS DISTINCT FROM (to_jsonb(NEW) - ARRAY['current_status','submitted_at'])
          THEN
            RAISE EXCEPTION 'order facts are immutable';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_fact_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE experiment UUID;
        BEGIN
          IF TG_TABLE_NAME = 'trade_intents' THEN
            experiment := OLD.experiment_id;
          ELSIF TG_TABLE_NAME = 'fills' THEN
            SELECT o.experiment_id INTO experiment FROM orders o WHERE o.id = OLD.order_id;
          ELSE
            SELECT ti.experiment_id INTO experiment
              FROM trade_intents ti WHERE ti.id = OLD.trade_intent_id;
          END IF;
          IF TG_OP = 'DELETE' AND atlas_deletion_context_matches(experiment) THEN
            RETURN OLD;
          END IF;
          RAISE EXCEPTION 'historical facts are immutable';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION phase_4_append_only_guard() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE experiment UUID;
        BEGIN
          IF TG_TABLE_NAME = 'order_events' THEN
            SELECT o.experiment_id INTO experiment FROM orders o
              WHERE o.id = CASE WHEN TG_OP = 'DELETE' THEN OLD.order_id ELSE NEW.order_id END;
          ELSIF TG_TABLE_NAME IN ('experiment_equity_points', 'experiment_results') THEN
            experiment := CASE WHEN TG_OP = 'DELETE' THEN OLD.experiment_id ELSE NEW.experiment_id END;
          ELSIF TG_TABLE_NAME = 'fills' THEN
            SELECT o.experiment_id INTO experiment FROM orders o
              WHERE o.id = CASE WHEN TG_OP = 'DELETE' THEN OLD.order_id ELSE NEW.order_id END;
          ELSIF TG_TABLE_NAME = 'trade_intents' THEN
            experiment := CASE WHEN TG_OP = 'DELETE' THEN OLD.experiment_id ELSE NEW.experiment_id END;
          ELSE
            SELECT ti.experiment_id INTO experiment FROM trade_intents ti
              WHERE ti.id = CASE WHEN TG_OP = 'DELETE' THEN OLD.trade_intent_id ELSE NEW.trade_intent_id END;
          END IF;
          IF TG_OP <> 'INSERT' THEN
            IF atlas_deletion_context_matches(experiment) THEN
              RETURN OLD;
            END IF;
            RAISE EXCEPTION 'historical facts are immutable';
          END IF;
          IF EXISTS (
            SELECT 1 FROM experiments WHERE id = experiment AND status IN ('COMPLETED','FAILED')
          ) THEN
            RAISE EXCEPTION 'terminal experiment graph is immutable';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
