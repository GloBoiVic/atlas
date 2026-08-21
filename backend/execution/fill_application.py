"""The sole persistence boundary at which a Fill changes financial state."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Final

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.persistence.models import (
    ExperimentAccountModel,
    FillModel,
    OrderModel,
    PositionModel,
    TradeModel,
)

_ZERO: Final = Decimal("0")


def _require_decimal(value: Decimal, name: str) -> None:
    if type(value) is not Decimal or not value.is_finite() or value <= 0:
        raise ValueError(f"{name} must be a positive finite Decimal")


def _require_utc(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("executed_at must be timezone-aware UTC")


def apply_fill(session: Session, fill: FillModel) -> FillModel:
    """Atomically persist one full Fill and update all financial projections.

    This is intentionally flush-only: the caller owns the outer transaction.
    A savepoint makes every failure rollback the Fill and every projection
    update, without closing or committing the caller-owned Session.
    """
    _require_decimal(fill.quantity, "fill quantity")
    _require_decimal(fill.execution_price, "execution price")
    if type(fill.fee) is not Decimal or not fill.fee.is_finite() or fill.fee != _ZERO:
        raise ValueError("Phase 3 fills must have a finite zero Decimal fee")
    _require_utc(fill.executed_at)

    with session.begin_nested():
        order = session.scalar(
            select(OrderModel).where(OrderModel.id == fill.order_id).with_for_update()
        )
        if order is None:
            raise ValueError("fill order does not exist")
        if order.current_status in {"FILLED", "CANCELED", "REJECTED", "EXPIRED"}:
            raise ValueError("order cannot receive another Phase 3 fill")
        if fill.sequence_number != 1 or fill.quantity != order.quantity:
            raise ValueError("Phase 3 requires one full sequence-one Fill")
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

        fill_row = fill
        session.add(fill_row)
        order.current_status = "FILLED"

        if order.purpose == "ENTRY":
            if position.state != "FLAT":
                raise ValueError("entry Fill requires a FLAT Position")
            if order.direction not in {"LONG", "SHORT"}:
                raise ValueError("entry order direction is invalid")
            position.state = order.direction
            position.quantity = fill.quantity
            position.entry_price = fill.execution_price
            position.opened_at = fill.executed_at
            trade = TradeModel(
                experiment_id=experiment_id,
                trade_intent_id=order.trade_intent_id,
                entry_order_id=order.id,
                direction=order.direction,
                quantity=fill.quantity,
                entry_price=fill.execution_price,
                opened_at=fill.executed_at,
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
                else "EXIT"
            )
            trade.status = "COMPLETED"
            position.state = "FLAT"
            position.quantity = None
            position.entry_price = None
            position.opened_at = None
            account.realized_pnl += pnl
        else:
            raise ValueError("order purpose cannot be applied by Phase 3")

        account.unrealized_pnl = _ZERO
        account.equity = account.starting_capital + account.realized_pnl
        session.flush()
        return fill_row


__all__ = ["apply_fill"]
