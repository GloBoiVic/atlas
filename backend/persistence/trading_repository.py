"""Small repositories for immutable trading facts and order projections."""

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    FillModel,
    OrderEventModel,
    OrderModel,
    RiskDecisionModel,
    TradeIntentModel,
    ExperimentProposalDiagnosticModel,
)


class TradingRepository:
    """Persistence operations that do not apply a Fill.

    In particular, creating an Order only records an instruction; it never
    touches Position, Trade, or account state.  Fill application lives in its
    own explicit boundary.
    """

    def create_intent(
        self, session: Session, *, experiment_id: UUID, strategy_version_id: UUID,
        venue_instrument_id: UUID, decision_frontier: datetime, action: str,
        direction: str | None, proposed_stop: Decimal | None,
        target_multiple: Decimal | None, rationale: Mapping[str, object],
        entry_policy: str = "IMMEDIATE", trigger_price: Decimal | None = None,
        trigger_price_basis: str | None = None, expiry_time: datetime | None = None,
        expiry_bars: int | None = None, proposal_status: str = "PENDING",
        diagnostics: Mapping[str, object] | None = None,
        intent_id: UUID | None = None,
    ) -> TradeIntentModel:
        row = TradeIntentModel(
            id=intent_id, experiment_id=experiment_id,
            strategy_version_id=strategy_version_id,
            venue_instrument_id=venue_instrument_id,
            decision_frontier=decision_frontier, action=action,
            direction=direction, proposed_stop=proposed_stop,
            target_multiple=target_multiple, rationale=dict(rationale),
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

    def create_proposal_diagnostic(self, session: Session, **values: object) -> ExperimentProposalDiagnosticModel:
        row = ExperimentProposalDiagnosticModel(**values)  # type: ignore[arg-type]
        session.add(row)
        session.flush()
        return row

    def create_order(
        self, session: Session, *, experiment_id: UUID, trade_intent_id: UUID,
        risk_decision_id: UUID, order_type: str, purpose: str, direction: str,
        quantity: Decimal, client_correlation_id: str,
        requested_price: Decimal | None = None, order_id: UUID | None = None,
        parent_entry_order_id: UUID | None = None,
    ) -> OrderModel:
        row = OrderModel(
            id=order_id, experiment_id=experiment_id,
            trade_intent_id=trade_intent_id, risk_decision_id=risk_decision_id,
            order_type=order_type, purpose=purpose, direction=direction,
            quantity=quantity, requested_price=requested_price,
            client_correlation_id=client_correlation_id,
            parent_entry_order_id=parent_entry_order_id,
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
