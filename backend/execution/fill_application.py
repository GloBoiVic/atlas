"""The sole persistence boundary at which a Fill changes financial state."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Final

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
    source_market_bar_id=None,
    details: dict[str, object] | None = None,
) -> None:
    sequence = session.scalar(
        select(func.coalesce(func.max(OrderEventModel.sequence_number), 0) + 1)
        .where(OrderEventModel.order_id == order.id)
    )
    session.add(OrderEventModel(
        order_id=order.id,
        sequence_number=int(sequence),
        event_type=event_type,
        occurred_at=occurred_at,
        source_market_bar_id=source_market_bar_id,
        details=details or {},
    ))


def _cancel_protection_siblings(
    session: Session, entry_order_id, executed_at: datetime
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
    ambiguity_source_market_bar_id=None,
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
        phase4 = session.scalar(
            select(ExperimentModel.model_version).where(
                ExperimentModel.id == order.experiment_id
            )
        ) == "PHASE4_HISTORICAL_EXECUTION_V1"
        if order.current_status in {
            "FILLED", "CANCELED", "REJECTED", "EXPIRED", "UNKNOWN"
        }:
            raise ValueError("order cannot receive another Fill")
        if fill.sequence_number != 1 or fill.quantity != order.quantity:
            raise ValueError("historical execution requires one full sequence-one Fill")
        experiment_id = order.experiment_id
        position = session.scalar(
            select(PositionModel)
            .where(PositionModel.experiment_id == experiment_id)
            .with_for_update()
        )
        account = session.scalar(
            select(ExperimentAccountModel)
            .where(ExperimentAccountModel.experiment_id == experiment_id)
            .with_for_update()
        )
        if position is None or account is None:
            raise ValueError("experiment financial projections are missing")
        existing = session.scalar(
            select(FillModel).where(
                FillModel.order_id == fill.order_id,
                FillModel.sequence_number == fill.sequence_number,
            )
        )
        if existing is not None:
            raise ValueError("fill sequence already exists")

        if phase4 and order.current_status == "PENDING_SUBMISSION":
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
            sequence = session.scalar(
                select(func.coalesce(func.max(TradeModel.sequence_number), 0) + 1)
                .where(TradeModel.experiment_id == experiment_id)
            )
            trade = TradeModel(
                experiment_id=experiment_id,
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
            trade = session.scalar(
                select(TradeModel)
                .where(
                    TradeModel.experiment_id == experiment_id,
                    TradeModel.status == "OPEN",
                )
                .with_for_update()
            )
            if trade is None:
                raise ValueError("exit Fill has no open Trade")
            if trade.direction != position.state:
                raise ValueError("Trade and Position directions disagree")
            pnl = (
                (fill.execution_price - position.entry_price) * fill.quantity
                if position.state == "LONG"
                else (position.entry_price - fill.execution_price) * fill.quantity
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
            trade.commission_cost = (trade.commission_cost or _ZERO) + fill.fee
            trade.financing_cost = None
            trade.net_pnl = pnl - trade.commission_cost
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
            account.realized_pnl += pnl - trade.commission_cost
            _cancel_protection_siblings(session, trade.entry_order_id, fill.executed_at)
        else:
            raise ValueError("order purpose cannot be applied by Phase 3")

        account.unrealized_pnl = _ZERO
        account.equity = account.starting_capital + account.realized_pnl
        session.flush()
        return fill_row


__all__ = ["apply_fill"]
