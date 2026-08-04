from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from backend.core.account_mode import AccountMode
from backend.execution import (
    AccountInfo,
    BrokerSnapshot,
    Fill,
    Order,
    OrderResult,
    OrderSide,
    OrderStatus,
    Position,
    PositionSide,
    Trade,
    TradeStatus,
)
from backend.persistence.repositories.memory import InMemoryExecutionRepository


def test_order_uses_uuid_instrument_identity_and_decimal_quantity() -> None:
    order = Order(
        account_id=uuid4(),
        instrument_id=uuid4(),
        side=OrderSide.SELL,
        quantity=Decimal("0.25"),
        client_order_id="client-1",
        mode=AccountMode.PAPER,
    )

    assert isinstance(order.instrument_id, UUID)
    assert order.order_type.value == "market"
    assert order.status is OrderStatus.PENDING


def test_order_rejects_filled_quantity_above_order_quantity() -> None:
    with pytest.raises(ValueError, match="filled_quantity"):
        Order(
            account_id=uuid4(),
            instrument_id=uuid4(),
            side=OrderSide.BUY,
            quantity=Decimal("1"),
            filled_quantity=Decimal("2"),
            client_order_id="client-1",
        )


def test_fill_rejects_non_utc_timestamp() -> None:
    with pytest.raises(ValueError, match="UTC"):
        Fill(
            order_id=uuid4(),
            account_id=uuid4(),
            instrument_id=uuid4(),
            side=OrderSide.BUY,
            quantity=Decimal("1"),
            price=Decimal("100"),
            fee=Decimal("0"),
            filled_at=datetime(2026, 1, 1, tzinfo=timezone(timedelta(hours=1))),
        )


def test_position_and_trade_are_one_way_futures_contracts() -> None:
    account_id = uuid4()
    instrument_id = uuid4()
    position = Position(
        account_id=account_id,
        instrument_id=instrument_id,
        side=PositionSide.SHORT,
        quantity=Decimal("1"),
        entry_price=Decimal("100"),
        mode=AccountMode.PAPER,
    )
    trade = Trade(
        account_id=account_id,
        instrument_id=instrument_id,
        position_id=position.id,
        direction=PositionSide.SHORT,
        entry_price=Decimal("100"),
        quantity=Decimal("1"),
        total_fees=Decimal("0"),
        entry_time=datetime(2026, 1, 1, tzinfo=UTC),
    )

    assert position.side is PositionSide.SHORT
    assert trade.position_id == position.id


def test_broker_result_and_snapshot_are_typed_immutable_contracts() -> None:
    account = AccountInfo(
        account_id=uuid4(),
        balance=Decimal("1000"),
        equity=Decimal("1000"),
        available_balance=Decimal("1000"),
    )
    result = OrderResult(success=False, status=OrderStatus.UNKNOWN, unknown=True, error="timeout")
    snapshot = BrokerSnapshot(account=account)

    assert result.unknown is True
    assert result.broker_order_id is None
    assert snapshot.positions == ()
    with pytest.raises((AttributeError, TypeError)):
        result.error = "retry"  # type: ignore[misc]


@pytest.mark.asyncio
async def test_memory_trade_lookup_returns_only_entered_trade() -> None:
    repository = InMemoryExecutionRepository()
    account_id, instrument_id, position_id = uuid4(), uuid4(), uuid4()
    exited = Trade(
        account_id=account_id,
        instrument_id=instrument_id,
        position_id=position_id,
        direction=PositionSide.LONG,
        entry_price=Decimal("100"),
        quantity=Decimal("1"),
        total_fees=Decimal("1"),
        entry_time=datetime(2026, 1, 1, tzinfo=UTC),
        status=TradeStatus.EXITED,
        exit_price=Decimal("101"),
        exit_time=datetime(2026, 1, 2, tzinfo=UTC),
    )
    entered = Trade(
        account_id=account_id,
        instrument_id=instrument_id,
        position_id=position_id,
        direction=PositionSide.LONG,
        entry_price=Decimal("100"),
        quantity=Decimal("1"),
        total_fees=Decimal("0"),
        entry_time=datetime(2026, 1, 1, tzinfo=UTC),
    )
    await repository.save_trade(exited)
    assert await repository.get_trade_by_position(position_id) is None
    await repository.save_trade(entered)
    assert await repository.get_trade_by_position(position_id) == entered
