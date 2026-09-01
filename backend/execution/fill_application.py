"""The sole persistence boundary at which a Fill changes financial state."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Final
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.persistence.models import (
    ExperimentAccountModel,
    ExperimentModel,
    FillModel,
    OrderEventModel,
    OrderModel,
    PositionModel,
    RiskDecisionModel,
    TradeModel,
)

_ZERO: Final = Decimal("0")


def _require_decimal(value: Decimal, name: str) -> None:
    if type(value) is not Decimal or not value.is_finite() or value <= 0:
        raise ValueError(f"{name} must be a positive finite Decimal")


def _require_utc(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("executed_at must be timezone-aware UTC")


def _append_event(
    session: Session,
    order: OrderModel,
    event_type: str,
    occurred_at: datetime,
    *,
    source_market_bar_id: UUID | None = None,
    details: dict[str, object] | None = None,
) -> None:
    sequence = session.scalar(
        select(func.coalesce(func.max(OrderEventModel.sequence_number), 0) + 1)
        .where(OrderEventModel.order_id == order.id)
    )
    if sequence is None:
        raise ValueError("could not sequence Order event")
    session.add(OrderEventModel(
        order_id=order.id,
        sequence_number=int(sequence),
        event_type=event_type,
        occurred_at=occurred_at,
        source_market_bar_id=source_market_bar_id,
        details=details or {},
    ))


def _cancel_protection_siblings(
    session: Session, entry_order_id: UUID, executed_at: datetime
) -> None:
    siblings = session.scalars(
        select(OrderModel)
        .where(
            OrderModel.parent_entry_order_id == entry_order_id,
            OrderModel.purpose.in_(["STOP_LOSS", "TAKE_PROFIT"]),
            OrderModel.current_status.not_in(["FILLED", "CANCELED"]),
        )
        .with_for_update()
    ).all()
    for sibling in siblings:
        sibling.current_status = "CANCELED"
        _append_event(session, sibling, "ORDER_CANCELED", executed_at)


def apply_fill(
    session: Session,
    fill: FillModel,
    *,
    ambiguity_policy: str | None = None,
    ambiguity_observed_at: datetime | None = None,
    ambiguity_source_market_bar_id: UUID | None = None,
) -> FillModel:
    """Atomically persist one full Fill and update all financial projections.

    This is intentionally flush-only: the caller owns the outer transaction.
    A savepoint makes every failure rollback the Fill and every projection
    update, without closing or committing the caller-owned Session.
    """
    _require_decimal(fill.quantity, "fill quantity")
    _require_decimal(fill.execution_price, "execution price")
    if type(fill.fee) is not Decimal or not fill.fee.is_finite() or fill.fee < _ZERO:
        raise ValueError("fill fee must be a finite non-negative Decimal")
    _require_utc(fill.executed_at)

    with session.begin_nested():
        order = session.scalar(
            select(OrderModel).where(OrderModel.id == fill.order_id).with_for_update()
        )
        if order is None:
            raise ValueError("fill order does not exist")
        model_version = (
            session.scalar(
                select(ExperimentModel.model_version).where(
                    ExperimentModel.id == order.experiment_id
                )
            )
            if order.experiment_id is not None
            else None
        )
        # Historical V2 uses the same constrained exit-reason vocabulary as
        # the original Phase 4 model.  Keep the legacy value for persisted
        # Phase 4 rows while ensuring V2 end-of-experiment fills are not
        # misclassified as the unrestricted live/runtime EXIT reason.
        phase4 = model_version in {
            "PHASE4_HISTORICAL_EXECUTION_V1",
            "PHASE5_HISTORICAL_EXECUTION_V2",
        }
        if order.current_status in {
            "FILLED", "CANCELED", "REJECTED", "EXPIRED", "UNKNOWN"
        }:
            raise ValueError("order cannot receive another Fill")
        if fill.sequence_number != 1 or fill.quantity != order.quantity:
            raise ValueError(
                "PAPER 01 requires one unambiguous full Fill"
                if order.deployment_id is not None
                else "historical execution requires one full sequence-one Fill"
            )
        experiment_id = order.experiment_id
        deployment_id = order.deployment_id
        position_query = select(PositionModel).with_for_update()
        position_query = position_query.where(
            PositionModel.experiment_id == experiment_id
            if experiment_id is not None
            else PositionModel.deployment_id == deployment_id
        )
        position = session.scalar(position_query)
        account = None
        if experiment_id is not None:
            account = session.scalar(
                select(ExperimentAccountModel)
                .where(ExperimentAccountModel.experiment_id == experiment_id)
                .with_for_update()
            )
        if position is None or (experiment_id is not None and account is None):
            raise ValueError("financial projections are missing")
        existing = session.scalar(
            select(FillModel).where(
                FillModel.order_id == fill.order_id,
                FillModel.sequence_number == fill.sequence_number,
            )
        )
        if existing is not None:
            raise ValueError("fill sequence already exists")

        if order.current_status == "PENDING_SUBMISSION":
            order.current_status = "SUBMITTED"
            order.submitted_at = fill.executed_at
            _append_event(session, order, "ORDER_SUBMITTED", fill.executed_at)
        fill_row = fill
        session.add(fill_row)
        order.current_status = "FILLED"
        _append_event(
            session, order, "ORDER_FILLED", fill.executed_at,
            source_market_bar_id=fill.source_market_bar_id,
            details={"price_basis": fill.price_basis},
        )

        if order.purpose == "ENTRY":
            if position.state != "FLAT":
                raise ValueError("entry Fill requires a FLAT Position")
            if order.direction not in {"LONG", "SHORT"}:
                raise ValueError("entry order direction is invalid")
            position.state = order.direction
            position.quantity = fill.quantity
            position.entry_price = fill.execution_price
            position.opened_at = fill.executed_at
            risk = session.scalar(
                select(RiskDecisionModel)
                .where(RiskDecisionModel.id == order.risk_decision_id)
            )
            sequence_query = select(
                func.coalesce(func.max(TradeModel.sequence_number), 0) + 1
            )
            sequence_query = sequence_query.where(
                TradeModel.experiment_id == experiment_id
                if experiment_id is not None
                else TradeModel.deployment_id == deployment_id
            )
            sequence = session.scalar(sequence_query)
            if sequence is None:
                raise ValueError("could not sequence Trade")
            trade = TradeModel(
                experiment_id=experiment_id,
                deployment_id=deployment_id,
                trade_intent_id=order.trade_intent_id,
                entry_order_id=order.id,
                direction=order.direction,
                quantity=fill.quantity,
                entry_price=fill.execution_price,
                opened_at=fill.executed_at,
                sequence_number=int(sequence),
                initial_risk=(
                    risk.actual_risk
                    if risk and risk.actual_risk is not None
                    else risk.risk_budget if risk else None
                ),
                commission_cost=fill.fee,
                financing_cost=None,
            )
            session.add(trade)
        elif order.purpose in {"EXIT", "STOP_LOSS", "TAKE_PROFIT"}:
            if position.state not in {"LONG", "SHORT"}:
                raise ValueError("exit Fill requires an exposed Position")
            if position.quantity != fill.quantity or position.entry_price is None:
                raise ValueError("exit Fill must close the current Position")
            trade_query = select(TradeModel).where(TradeModel.status == "OPEN")
            trade_query = trade_query.where(
                TradeModel.experiment_id == experiment_id
                if experiment_id is not None
                else TradeModel.deployment_id == deployment_id
            ).with_for_update()
            trade = session.scalar(trade_query)
            if trade is None:
                raise ValueError("exit Fill has no open Trade")
            if trade.direction != position.state:
                raise ValueError("Trade and Position directions disagree")
            entry_price = position.entry_price
            pnl = (
                (fill.execution_price - entry_price) * fill.quantity
                if position.state == "LONG"
                else (entry_price - fill.execution_price) * fill.quantity
            )
            trade.exit_order_id = order.id
            trade.exit_price = fill.execution_price
            trade.closed_at = fill.executed_at
            trade.gross_pnl = pnl
            trade.exit_reason = (
                "STOP_LOSS" if order.purpose == "STOP_LOSS"
                else "TAKE_PROFIT" if order.purpose == "TAKE_PROFIT"
                else "END_OF_EXPERIMENT" if phase4 else "EXIT"
            )
            commission_cost = (trade.commission_cost or _ZERO) + fill.fee
            trade.commission_cost = commission_cost
            trade.financing_cost = None
            trade.net_pnl = pnl - commission_cost
            if trade.initial_risk and trade.initial_risk != _ZERO:
                trade.r_multiple = pnl / trade.initial_risk
            if ambiguity_policy is not None:
                trade.intrabar_ambiguous = True
                trade.ambiguity_policy = ambiguity_policy
                trade.ambiguity_observed_at = ambiguity_observed_at or fill.executed_at
                trade.ambiguity_source_market_bar_id = ambiguity_source_market_bar_id
            trade.status = "COMPLETED"
            position.state = "FLAT"
            position.quantity = None
            position.entry_price = None
            position.opened_at = None
            if account is not None:
                account.realized_pnl += pnl - commission_cost
            _cancel_protection_siblings(session, trade.entry_order_id, fill.executed_at)
        else:
            raise ValueError("order purpose cannot be applied by Phase 3")

        if account is not None:
            account.unrealized_pnl = _ZERO
            account.equity = account.starting_capital + account.realized_pnl
        session.flush()
        return fill_row


__all__ = ["apply_fill"]
