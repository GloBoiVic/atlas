"""Small repositories for immutable trading facts and order projections."""

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    ExperimentProposalDiagnosticModel,
    FillModel,
    OrderEventModel,
    OrderModel,
    RiskDecisionModel,
    TradeIntentModel,
)
from .timestamps import require_optional_utc, require_utc


class TradingRepository:
    """Persistence operations that do not apply a Fill.

    In particular, creating an Order only records an instruction; it never
    touches Position, Trade, or account state.  Fill application lives in its
    own explicit boundary.
    """

    def create_intent(
        self, session: Session, *, experiment_id: UUID | None = None,
        deployment_id: UUID | None = None, strategy_version_id: UUID,
        venue_instrument_id: UUID, decision_frontier: datetime, action: str,
        direction: str | None, proposed_stop: Decimal | None,
        target_multiple: Decimal | None, rationale: Mapping[str, object],
        target_methodology: str | None = None,
        entry_policy: str = "IMMEDIATE", trigger_price: Decimal | None = None,
        trigger_price_basis: str | None = None, expiry_time: datetime | None = None,
        expiry_bars: int | None = None, proposal_status: str = "PENDING",
        diagnostics: Mapping[str, object] | None = None,
        intent_id: UUID | None = None,
    ) -> TradeIntentModel:
        if (experiment_id is None) == (deployment_id is None):
            raise ValueError("TradeIntent requires exactly one root owner")
        if deployment_id is not None:
            require_utc(decision_frontier, "decision_frontier")
            require_optional_utc(expiry_time, "expiry_time")
        row = TradeIntentModel(
            id=intent_id, experiment_id=experiment_id,
            deployment_id=deployment_id,
            strategy_version_id=strategy_version_id,
            venue_instrument_id=venue_instrument_id,
            decision_frontier=decision_frontier, action=action,
            direction=direction, proposed_stop=proposed_stop,
            target_multiple=target_multiple, rationale=dict(rationale),
            target_methodology=target_methodology,
            entry_policy=entry_policy, trigger_price=trigger_price,
            trigger_price_basis=trigger_price_basis, expiry_time=expiry_time,
            expiry_bars=expiry_bars, proposal_status=proposal_status,
            diagnostics=dict(diagnostics or {}),
        )
        session.add(row)
        session.flush()
        return row

    def create_risk_decision(
        self, session: Session, **values: object
    ) -> RiskDecisionModel:
        row = RiskDecisionModel(**values)  # type: ignore[arg-type]
        session.add(row)
        session.flush()
        return row

    def create_paper_risk_decision(
        self,
        session: Session,
        *,
        trade_intent_id: UUID,
        decision: object,
        evaluated_at: datetime,
    ) -> RiskDecisionModel:
        """Persist a PAPER decision without changing historical Risk shape."""
        from backend.risk import RiskDecision, RiskPhase

        if type(decision) is not RiskDecision:
            raise TypeError("decision must be a RiskDecision")
        require_utc(evaluated_at, "evaluated_at")
        require_optional_utc(decision.quote_observed_at, "quote_observed_at")
        if (
            decision.phase is RiskPhase.PRE_SUBMISSION
            and decision.target_price is not None
        ):
            raise ValueError("PAPER PRE_SUBMISSION target must be NULL")
        row = RiskDecisionModel(
            trade_intent_id=trade_intent_id,
            phase=decision.phase.value,
            outcome="APPROVED" if decision.approved else "REJECTED",
            quantity=decision.quantity,
            entry_price=decision.entry_price,
            stop_price=decision.stop_price,
            target_price=decision.target_price,
            risk_budget=decision.risk_budget,
            quote_bid=decision.quote_bid,
            quote_ask=decision.quote_ask,
            rejection_code=decision.rejection.value if decision.rejection else None,
            actual_risk=decision.actual_risk,
            target_methodology=decision.target_methodology,
            target_multiple=decision.target_multiple,
            quote_observed_at=decision.quote_observed_at,
            price_bound=decision.price_bound,
            evidence=dict(decision.evidence),
            evaluated_at=evaluated_at,
        )
        session.add(row)
        session.flush()
        return row

    def create_proposal_diagnostic(
        self, session: Session, **values: object
    ) -> ExperimentProposalDiagnosticModel:
        row = ExperimentProposalDiagnosticModel(**values)  # type: ignore[arg-type]
        session.add(row)
        session.flush()
        return row

    def create_order(
        self, session: Session, *, experiment_id: UUID | None = None,
        deployment_id: UUID | None = None, trade_intent_id: UUID,
        risk_decision_id: UUID, order_type: str, purpose: str, direction: str,
        quantity: Decimal, client_correlation_id: str,
        requested_price: Decimal | None = None, order_id: UUID | None = None,
        parent_entry_order_id: UUID | None = None, time_in_force: str | None = None,
        price_bound: Decimal | None = None, external_order_id: str | None = None,
        request_provenance: Mapping[str, object] | None = None,
    ) -> OrderModel:
        if (experiment_id is None) == (deployment_id is None):
            raise ValueError("Order requires exactly one root owner")
        row = OrderModel(
            id=order_id, experiment_id=experiment_id,
            deployment_id=deployment_id,
            trade_intent_id=trade_intent_id, risk_decision_id=risk_decision_id,
            order_type=order_type, purpose=purpose, direction=direction,
            quantity=quantity, requested_price=requested_price,
            client_correlation_id=client_correlation_id,
            parent_entry_order_id=parent_entry_order_id,
            time_in_force=time_in_force,
            price_bound=price_bound,
            external_order_id=external_order_id,
            request_provenance=dict(request_provenance or {}),
        )
        session.add(row)
        session.flush()
        self.append_order_event(
            session,
            order_id=row.id,
            sequence_number=1,
            event_type="ORDER_CREATED",
            occurred_at=row.created_at,
            details={},
        )
        return row

    def append_order_event(self, session: Session, **values: object) -> OrderEventModel:
        row = OrderEventModel(**values)  # type: ignore[arg-type]
        session.add(row)
        session.flush()
        return row

    def create_fill(self, session: Session, **values: object) -> FillModel:
        row = FillModel(**values)  # type: ignore[arg-type]
        session.add(row)
        session.flush()
        return row

    def get_order(self, session: Session, order_id: UUID) -> OrderModel | None:
        return session.get(OrderModel, order_id)

    def fills_for_order(
        self, session: Session, order_id: UUID
    ) -> tuple[FillModel, ...]:
        return tuple(session.scalars(
            select(FillModel).where(FillModel.order_id == order_id)
            .order_by(FillModel.sequence_number)
        ).all())


__all__ = ["TradingRepository"]
