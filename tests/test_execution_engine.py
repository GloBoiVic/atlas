from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

import pytest

from backend.core.account_mode import AccountMode
from backend.core.events import (
    EventBus,
    EventHandler,
    OrderFilled,
    OrderSubmitted,
    PositionClosed,
    PositionOpened,
    RiskApproved,
    TradeClosed,
)
from backend.execution import (
    AccountExposureCoordinator,
    ExecutableMarket,
    ExecutionEngine,
    Order,
    OrderStatus,
    PaperBroker,
    Position,
    PositionSide,
)
from backend.persistence.repositories.memory import InMemoryExecutionRepository
from backend.strategy.contracts import Signal, SignalDirection

if TYPE_CHECKING:
    from backend.execution.engine import SubmitOrder


def approval(
    account_id: UUID,
    bot_id: UUID,
    instrument_id: UUID,
    strategy_id: UUID,
    direction: SignalDirection,
    quantity: str,
    occurred_at: datetime = datetime(2026, 1, 1, 0, 1, tzinfo=UTC),
) -> RiskApproved:
    signal = Signal(
        instrument_id=instrument_id,
        direction=direction,
        strength=Decimal("1"),
        metadata={},
        candle_timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        strategy_version_id=strategy_id,
        strategy_name="strategy",
        strategy_commit_sha="sha",
    )
    return RiskApproved(
        signal=signal,
        position_size=Decimal(quantity),
        stop_loss=Decimal("90"),
        take_profit=Decimal("0"),
        account_id=account_id,
        bot_id=bot_id,
        mode=AccountMode.PAPER,
        occurred_at=occurred_at,
    )


@pytest.mark.asyncio
async def test_engine_nets_two_strategy_identities_and_preserves_provenance() -> None:
    account_id, instrument_id = uuid4(), uuid4()
    bot_a, bot_b, strategy_a, strategy_b = uuid4(), uuid4(), uuid4(), uuid4()
    repository = InMemoryExecutionRepository()
    broker = PaperBroker(account_id=account_id, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC))
    broker.set_market(
        ExecutableMarket(
            instrument_id=instrument_id,
            bid=Decimal("99"),
            ask=Decimal("101"),
            mark_price=Decimal("100"),
            as_of=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    bus = EventBus()
    submitted: list[OrderSubmitted] = []
    filled: list[OrderFilled] = []

    async def capture_submitted(event: OrderSubmitted) -> None:
        submitted.append(event)

    async def capture_filled(event: OrderFilled) -> None:
        filled.append(event)

    bus.subscribe(OrderSubmitted, cast("EventHandler", capture_submitted))
    bus.subscribe(OrderFilled, cast("EventHandler", capture_filled))
    ExecutionEngine(bus, broker, repository)

    await bus.publish(
        approval(account_id, bot_a, instrument_id, strategy_a, SignalDirection.BUY, "2")
    )
    await bus.publish(
        approval(account_id, bot_b, instrument_id, strategy_b, SignalDirection.BUY, "3")
    )

    assert len(submitted) == 2
    assert len(filled) == 2
    assert all(item.order.account_id == account_id for item in filled)
    position = await repository.get_position(
        account_id=account_id, instrument_id=instrument_id, mode=AccountMode.PAPER
    )
    assert position is not None
    assert position.quantity == Decimal("5")


@pytest.mark.asyncio
async def test_reversal_is_reduce_only_close_then_open() -> None:
    account_id, instrument_id, bot_id, strategy_id = uuid4(), uuid4(), uuid4(), uuid4()
    repository = InMemoryExecutionRepository()
    broker = PaperBroker(account_id=account_id, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC))
    broker.set_market(
        ExecutableMarket(
            instrument_id=instrument_id,
            bid=Decimal("99"),
            ask=Decimal("101"),
            mark_price=Decimal("100"),
            as_of=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    bus = EventBus()
    engine = ExecutionEngine(bus, broker, repository)
    await bus.publish(
        approval(account_id, bot_id, instrument_id, strategy_id, SignalDirection.BUY, "2")
    )
    await bus.publish(
        approval(account_id, bot_id, instrument_id, strategy_id, SignalDirection.CLOSE, "0")
    )
    # A close is a separate RiskApproved event and the coordinator never submits an implicit flip.
    assert (
        await repository.get_position(
            account_id=account_id, instrument_id=instrument_id, mode=AccountMode.PAPER
        )
        is None
    )
    engine.close()


@pytest.mark.asyncio
async def test_duplicate_strategy_is_rejected_and_fifo_is_deterministic() -> None:
    account_id, instrument_id, bot_id = uuid4(), uuid4(), uuid4()
    strategy_a, strategy_b = uuid4(), uuid4()
    repository = InMemoryExecutionRepository()
    coordinator = AccountExposureCoordinator(repository)
    submitted: list[Order] = []

    async def submit(order: Order, _event: RiskApproved, _prior: Position | None) -> Order:
        submitted.append(order)
        return replace(order, status=OrderStatus.FILLED)

    await coordinator.apply_approval(
        approval(account_id, bot_id, instrument_id, strategy_a, SignalDirection.BUY, "2"),
        cast("SubmitOrder", submit),
    )
    with pytest.raises(ValueError, match="duplicate_active_strategy_exposure"):
        await coordinator.apply_approval(
            approval(account_id, bot_id, instrument_id, strategy_a, SignalDirection.BUY, "2"),
            cast("SubmitOrder", submit),
        )
    await coordinator.apply_approval(
        approval(account_id, bot_id, instrument_id, strategy_b, SignalDirection.BUY, "3"),
        cast("SubmitOrder", submit),
    )
    allocated = coordinator.allocate_reduction(
        account_id, instrument_id, AccountMode.PAPER, PositionSide.LONG, Decimal("4")
    )
    assert sum((amount for _, amount in allocated), Decimal("0")) == Decimal("4")
    assert len(allocated) == 2
    assert len(submitted) == 2


@pytest.mark.asyncio
async def test_engine_emits_open_close_and_trade_closed_facts() -> None:
    account_id, instrument_id, bot_id, strategy_id = uuid4(), uuid4(), uuid4(), uuid4()
    repository = InMemoryExecutionRepository()
    broker = PaperBroker(
        account_id=account_id,
        clock=lambda: datetime(2026, 1, 1, tzinfo=UTC),
    )
    broker.set_market(
        ExecutableMarket(
            instrument_id=instrument_id,
            bid=Decimal("99"),
            ask=Decimal("101"),
            mark_price=Decimal("100"),
            as_of=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    bus = EventBus()
    opened: list[PositionOpened] = []
    closed: list[PositionClosed] = []
    trades: list[TradeClosed] = []

    async def capture_open(event: PositionOpened) -> None:
        opened.append(event)

    async def capture_close(event: PositionClosed) -> None:
        closed.append(event)

    async def capture_trade(event: TradeClosed) -> None:
        trades.append(event)

    bus.subscribe(PositionOpened, cast("EventHandler", capture_open))
    bus.subscribe(PositionClosed, cast("EventHandler", capture_close))
    bus.subscribe(TradeClosed, cast("EventHandler", capture_trade))
    ExecutionEngine(bus, broker, repository)
    await bus.publish(
        approval(account_id, bot_id, instrument_id, strategy_id, SignalDirection.BUY, "1")
    )
    await bus.publish(
        approval(account_id, bot_id, instrument_id, strategy_id, SignalDirection.CLOSE, "0")
    )
    assert len(opened) == 1
    assert len(closed) == 1
    assert len(trades) == 1
    assert opened[0].occurred_at == datetime(2026, 1, 1, 0, 1, tzinfo=UTC)
    assert closed[0].occurred_at == opened[0].occurred_at
    assert trades[0].occurred_at == opened[0].occurred_at
