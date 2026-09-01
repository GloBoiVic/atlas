"""Fence PAPER ENTRY Orders behind persisted authorization and uniqueness."""

# ruff: noqa: E501

import sqlalchemy as sa
from alembic import op

revision = "0024_authorization_fence"
down_revision = "0023_analytical_frontier"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The original shared trigger accessed root-only NEW fields before branching
    # by table, which makes every RiskDecision insert fail in PostgreSQL.  Keep
    # the frozen ownership rules while branching before table-specific access.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION atlas_validate_canonical_ownership() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE ti_experiment UUID; ti_deployment UUID; entry_experiment UUID; entry_deployment UUID; exit_experiment UUID; exit_deployment UUID; parent_experiment UUID; parent_deployment UUID; decision_intent UUID;
        BEGIN
          IF TG_TABLE_NAME IN ('trade_intents','orders','positions','trades') THEN
            IF ((NEW.experiment_id IS NULL) = (NEW.deployment_id IS NULL)) THEN RAISE EXCEPTION 'canonical fact must have exactly one root owner'; END IF;
          END IF;
          IF TG_TABLE_NAME = 'trade_intents' THEN RETURN NEW; END IF;
          IF TG_TABLE_NAME = 'risk_decisions' THEN
            SELECT experiment_id, deployment_id INTO ti_experiment, ti_deployment FROM trade_intents WHERE id = NEW.trade_intent_id;
            IF NOT FOUND THEN RAISE EXCEPTION 'RiskDecision requires an existing TradeIntent'; END IF;
            IF ti_deployment IS NOT NULL AND NEW.phase = 'PRE_SUBMISSION' AND NEW.target_price IS NOT NULL THEN RAISE EXCEPTION 'PAPER PRE_SUBMISSION target must be NULL'; END IF;
            IF ti_deployment IS NOT NULL AND NEW.outcome = 'APPROVED' AND (NEW.target_methodology IS DISTINCT FROM (SELECT target_methodology FROM trade_intents WHERE id = NEW.trade_intent_id) OR NEW.target_multiple IS DISTINCT FROM (SELECT target_multiple FROM trade_intents WHERE id = NEW.trade_intent_id)) THEN RAISE EXCEPTION 'RiskDecision target methodology does not match TradeIntent'; END IF;
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
        END; $$
        """
    )
    # A PAPER intent may receive a later fresh authorization after reconciliation,
    # while a single timestamp remains an immutable decision identity.
    op.drop_constraint(
        "uq_risk_decisions_intent_phase", "risk_decisions", type_="unique"
    )
    op.create_unique_constraint(
        "uq_risk_decisions_intent_phase_time",
        "risk_decisions",
        ["trade_intent_id", "phase", "evaluated_at"],
    )
    op.create_index(
        "uq_orders_paper_entry_intent",
        "orders",
        ["trade_intent_id"],
        unique=True,
        postgresql_where=sa.text(
            "deployment_id IS NOT NULL AND purpose = 'ENTRY'"
        ),
    )
    op.execute(
        """
        CREATE FUNCTION atlas_validate_paper_entry_authorization() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
          decision_intent UUID;
          decision_phase TEXT;
          decision_outcome TEXT;
          decision_quantity NUMERIC;
          decision_price_bound NUMERIC;
          decision_target NUMERIC;
        BEGIN
          IF NEW.deployment_id IS NULL OR NEW.purpose <> 'ENTRY' THEN
            RETURN NEW;
          END IF;
          SELECT trade_intent_id, phase, outcome, quantity, price_bound, target_price
            INTO decision_intent, decision_phase, decision_outcome,
                 decision_quantity, decision_price_bound, decision_target
            FROM risk_decisions
           WHERE id = NEW.risk_decision_id;
          IF NOT FOUND
             OR decision_intent IS DISTINCT FROM NEW.trade_intent_id
             OR decision_phase <> 'PRE_SUBMISSION'
             OR decision_outcome <> 'APPROVED'
             OR decision_quantity IS DISTINCT FROM NEW.quantity
             OR decision_price_bound IS NULL
             OR decision_price_bound IS DISTINCT FROM NEW.price_bound
             OR decision_target IS NOT NULL THEN
            RAISE EXCEPTION 'PAPER ENTRY lacks persisted approval';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER orders_paper_authorization_guard
        BEFORE INSERT OR UPDATE OF deployment_id, trade_intent_id,
          risk_decision_id, purpose, quantity, price_bound
        ON orders
        FOR EACH ROW EXECUTE FUNCTION atlas_validate_paper_entry_authorization()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS orders_paper_authorization_guard ON orders")
    op.execute("DROP FUNCTION IF EXISTS atlas_validate_paper_entry_authorization()")
    op.drop_index("uq_orders_paper_entry_intent", table_name="orders")
    op.drop_constraint(
        "uq_risk_decisions_intent_phase_time", "risk_decisions", type_="unique"
    )
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM risk_decisions
            GROUP BY trade_intent_id, phase HAVING count(*) > 1
          ) THEN
            RAISE EXCEPTION 'cannot restore one RiskDecision per phase';
          END IF;
        END $$
        """
    )
    op.create_unique_constraint(
        "uq_risk_decisions_intent_phase",
        "risk_decisions",
        ["trade_intent_id", "phase"],
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION atlas_validate_canonical_ownership() RETURNS trigger LANGUAGE plpgsql AS $$
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
        END; $$
        """
    )
