from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from backend.core.account_mode import AccountMode
from backend.data.models import Instrument, MarketContext
from backend.execution import (
    ExecutableMarket,
    Order,
    OrderSide,
    OrderStatus,
    PaperBroker,
    PaperFillMode,
    executable_market_from_context,
)
from backend.persistence.repositories.memory import InMemoryExecutionRepository


def market(
    instrument_id: UUID,
    *,
    bid: str = "99",
    ask: str = "101",
    mark: str = "100",
    age: int = 0,
    next_open: str | None = None,
) -> ExecutableMarket:
    return ExecutableMarket(
        instrument_id=instrument_id,
        bid=Decimal(bid),
        ask=Decimal(ask),
        mark_price=Decimal(mark),
        as_of=datetime(2026, 1, 1, tzinfo=UTC) - timedelta(seconds=age),
        next_candle_open=Decimal(next_open) if next_open else None,
    )


def order(
    account_id: UUID,
    instrument_id: UUID,
    side: OrderSide,
    quantity: str = "1",
    *,
    client_order_id: str | None = None,
    reduce_only: bool = False,
    leverage: Decimal = Decimal("1"),
    stop_loss: Decimal = Decimal("0"),
    take_profit: Decimal = Decimal("0"),
) -> Order:
    return Order(
        account_id=account_id,
        instrument_id=instrument_id,
        side=side,
        quantity=Decimal(quantity),
        client_order_id=client_order_id or str(uuid4()),
        mode=AccountMode.PAPER,
        reduce_only=reduce_only,
        leverage=leverage,
        stop_loss=stop_loss,
        take_profit=take_profit,
    )


@pytest.mark.asyncio
async def test_live_fill_uses_executable_side_and_configured_taker_fee() -> None:
    account_id, instrument_id = uuid4(), uuid4()
    broker = PaperBroker(
        account_id=account_id,
        initial_balance=Decimal("1000"),
        clock=lambda: datetime(2026, 1, 1, tzinfo=UTC),
    )
    broker.set_market(market(instrument_id))

    result = await broker.submit_order(
        order(account_id, instrument_id, OrderSide.BUY), "client-1"
    )

    assert result.status is OrderStatus.FILLED
    assert result.fills[0].price == Decimal("101.0505")
    assert result.fills[0].fee == Decimal("0.05052525")


def test_live_market_adapter_preserves_context_without_next_candle_open() -> None:
    instrument_id = uuid4()
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    context = MarketContext(
        instrument_id=instrument_id,
        provider="binance_usdm",
        bid=Decimal("99"),
        ask=Decimal("101"),
        mark_price=Decimal("100"),
        index_price=Decimal("100"),
        funding_rate=Decimal("0.0001"),
        next_funding_time=timestamp + timedelta(hours=8),
        as_of=timestamp,
        bid_at=timestamp,
        ask_at=timestamp,
        mark_at=timestamp,
        index_at=timestamp,
        funding_at=timestamp,
    )
    instrument = Instrument(instrument_id, "BTCUSDT", "binance_usdm", "crypto")

    executable = executable_market_from_context(context, instrument)

    assert executable.mark_price == context.mark_price
    assert executable.next_candle_open is None


@pytest.mark.asyncio
async def test_paper_broker_restores_durable_position_and_idempotent_funding() -> None:
    account_id, instrument_id = uuid4(), uuid4()
    repository = InMemoryExecutionRepository()
    def clock() -> datetime:
        return datetime(2026, 1, 1, tzinfo=UTC)
    broker = PaperBroker(account_id=account_id, repository=repository, clock=clock)
    broker.set_market(market(instrument_id))
    await broker.submit_order(order(account_id, instrument_id, OrderSide.BUY), "restore-entry")
    await broker.apply_funding(
        Decimal("-2"),
        instrument_id=instrument_id,
        funding_timestamp=datetime(2026, 1, 1, 8, tzinfo=UTC),
    )

    restored = PaperBroker(account_id=account_id, repository=repository, clock=clock)
    await restored.restore()
    restored.set_market(market(instrument_id))
    duplicate = await restored.apply_funding(
        Decimal("-2"),
        instrument_id=instrument_id,
        funding_timestamp=datetime(2026, 1, 1, 8, tzinfo=UTC),
    )

    assert len(await restored.get_positions()) == 1
    assert duplicate.amount == Decimal("-2")
    assert len(await repository.get_funding_adjustments(
        account_id=account_id, instrument_id=instrument_id, mode=AccountMode.PAPER
    )) == 1


@pytest.mark.asyncio
async def test_restore_preserves_realized_pnl_and_fees() -> None:
    account_id, instrument_id = uuid4(), uuid4()
    repository = InMemoryExecutionRepository()
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    broker = PaperBroker(
        account_id=account_id,
        initial_balance=Decimal("1000"),
        repository=repository,
        clock=lambda: timestamp,
    )
    broker.set_market(market(instrument_id, bid="100", ask="100", mark="100"))
    await broker.submit_order(
        order(account_id, instrument_id, OrderSide.BUY), "restore-pnl-entry"
    )
    broker.set_market(market(instrument_id, bid="110", ask="110", mark="110"))
    await broker.submit_order(
        order(account_id, instrument_id, OrderSide.SELL, reduce_only=True), "restore-pnl-close"
    )
    expected_balance = broker.balance

    restored = PaperBroker(
        account_id=account_id,
        initial_balance=Decimal("1000"),
        repository=repository,
        clock=lambda: timestamp,
    )
    await restored.restore()

    assert restored.balance == expected_balance
    assert restored.balance == Decimal("1009.79000250")


@pytest.mark.asyncio
async def test_duplicate_client_id_returns_same_fill_without_duplicate_position() -> None:
    account_id, instrument_id = uuid4(), uuid4()
    broker = PaperBroker(account_id=account_id, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC))
    broker.set_market(market(instrument_id))
    request = order(account_id, instrument_id, OrderSide.BUY, client_order_id="same")

    first = await broker.submit_order(request, "same")
    second = await broker.submit_order(request, "same")

    assert first == second
    assert len(await broker.get_positions()) == 1


@pytest.mark.asyncio
async def test_memory_order_queries_do_not_match_unscoped_orders_to_a_mode() -> None:
    account_id, instrument_id = uuid4(), uuid4()
    repository = InMemoryExecutionRepository()
    unscoped = order(account_id, instrument_id, OrderSide.BUY)
    unscoped = replace(unscoped, mode=None)
    await repository.create_order(unscoped)

    assert await repository.get_orders(account_id=account_id, mode=AccountMode.PAPER) == []
    assert await repository.get_non_terminal_orders(
        account_id=account_id, mode=AccountMode.PAPER
    ) == [unscoped]


@pytest.mark.asyncio
async def test_funding_requires_durable_scope_fields() -> None:
    broker = PaperBroker()

    with pytest.raises(ValueError, match="requires an instrument"):
        await broker.apply_funding(
            Decimal("1"), funding_timestamp=datetime(2026, 1, 1, tzinfo=UTC)
        )
    with pytest.raises(ValueError, match="requires a funding timestamp"):
        await broker.apply_funding(Decimal("1"), instrument_id=uuid4())


@pytest.mark.asyncio
async def test_same_side_accumulation_uses_quantity_weighted_average() -> None:
    account_id, instrument_id = uuid4(), uuid4()
    broker = PaperBroker(account_id=account_id, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC))
    broker.set_market(market(instrument_id))
    await broker.submit_order(order(account_id, instrument_id, OrderSide.BUY), "first")
    broker.set_market(market(instrument_id, bid="100", ask="102", mark="101"))
    await broker.submit_order(order(account_id, instrument_id, OrderSide.BUY), "second")

    position = (await broker.get_positions())[0]
    assert position.quantity == Decimal("2")
    assert position.entry_price == Decimal("101.55075")


@pytest.mark.asyncio
async def test_partial_close_reduces_position_and_full_close_removes_it() -> None:
    account_id, instrument_id = uuid4(), uuid4()
    broker = PaperBroker(account_id=account_id, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC))
    broker.set_market(market(instrument_id))
    await broker.submit_order(order(account_id, instrument_id, OrderSide.BUY, "2"), "open")

    partial = await broker.submit_order(
        order(account_id, instrument_id, OrderSide.SELL, "0.5", reduce_only=True), "partial"
    )
    assert partial.status is OrderStatus.FILLED
    position = (await broker.get_positions())[0]
    assert position.quantity == Decimal("1.5")
    assert position.status.value == "reducing"

    full = await broker.submit_order(
        order(account_id, instrument_id, OrderSide.SELL, "1.5", reduce_only=True), "full"
    )
    assert full.status is OrderStatus.FILLED
    assert await broker.get_positions() == []


@pytest.mark.asyncio
async def test_mark_price_updates_unrealized_pnl_and_stale_context_fails_closed() -> None:
    account_id, instrument_id = uuid4(), uuid4()
    now = datetime(2026, 1, 1, tzinfo=UTC)
    broker = PaperBroker(account_id=account_id, clock=lambda: now)
    broker.set_market(market(instrument_id))
    await broker.submit_order(order(account_id, instrument_id, OrderSide.BUY), "open")
    broker.set_market(market(instrument_id, bid="109", ask="111", mark="110"))

    position = (await broker.get_positions())[0]
    assert position.unrealized_pnl == Decimal("8.9495")

    broker.set_market(market(instrument_id, age=6))
    rejected = await broker.submit_order(
        order(account_id, instrument_id, OrderSide.BUY, client_order_id="stale"), "stale"
    )
    assert rejected.status is OrderStatus.REJECTED
    assert rejected.unknown is False


@pytest.mark.asyncio
async def test_reduce_only_close_and_reversal_are_explicit() -> None:
    account_id, instrument_id = uuid4(), uuid4()
    broker = PaperBroker(account_id=account_id, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC))
    broker.set_market(market(instrument_id))
    await broker.submit_order(order(account_id, instrument_id, OrderSide.BUY), "open")

    reversal = await broker.submit_order(
        order(account_id, instrument_id, OrderSide.SELL), "reverse"
    )
    assert reversal.status is OrderStatus.REJECTED
    close = await broker.submit_order(
        order(account_id, instrument_id, OrderSide.SELL, reduce_only=True), "close"
    )
    assert close.status is OrderStatus.FILLED
    assert (await broker.get_positions()) == []


@pytest.mark.asyncio
async def test_protective_trigger_uses_mark_price_and_executable_exit_price() -> None:
    account_id, instrument_id = uuid4(), uuid4()
    broker = PaperBroker(account_id=account_id, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC))
    broker.set_market(market(instrument_id))
    await broker.submit_order(
        order(
            account_id,
            instrument_id,
            OrderSide.BUY,
            stop_loss=Decimal("99"),
        ),
        "protected-open",
    )
    broker.set_market(market(instrument_id, bid="97", ask="99", mark="98"))

    result = await broker.check_protective_triggers(instrument_id)

    assert result is not None
    assert result.status is OrderStatus.FILLED
    assert result.fills[0].price == Decimal("96.9515")
    assert await broker.get_positions() == []


@pytest.mark.asyncio
async def test_funding_is_separate_and_balance_never_goes_negative_on_liquidation() -> None:
    account_id, instrument_id = uuid4(), uuid4()
    funding_broker = PaperBroker(
        account_id=account_id,
        initial_balance=Decimal("10"),
        clock=lambda: datetime(2026, 1, 1, tzinfo=UTC),
    )
    await funding_broker.apply_funding(
        Decimal("-20"),
        instrument_id=instrument_id,
        funding_timestamp=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert funding_broker.balance == Decimal("0")

    liquidation_broker = PaperBroker(
        account_id=account_id,
        initial_balance=Decimal("100"),
        leverage=Decimal("2"),
        clock=lambda: datetime(2026, 1, 1, tzinfo=UTC),
    )
    liquidation_broker.set_market(market(instrument_id, bid="100", ask="101", mark="100"))
    result = await liquidation_broker.submit_order(
        order(account_id, instrument_id, OrderSide.BUY, quantity="1", leverage=Decimal("2")),
        "liquidatable",
    )
    assert result.status is OrderStatus.FILLED
    liquidation_broker.set_market(market(instrument_id, bid="50", ask="51", mark="50"))
    liquidation = await liquidation_broker.check_liquidation(instrument_id)

    assert liquidation is not None
    assert liquidation.status is OrderStatus.FILLED
    assert await liquidation_broker.get_positions() == []
    assert liquidation_broker.balance >= 0


@pytest.mark.asyncio
async def test_repository_backing_persists_order_fill_position_and_duplicate_result() -> None:
    account_id, instrument_id = uuid4(), uuid4()
    repository = InMemoryExecutionRepository()
    broker = PaperBroker(
        account_id=account_id,
        repository=repository,
        clock=lambda: datetime(2026, 1, 1, tzinfo=UTC),
    )
    broker.set_market(market(instrument_id))
    request = order(account_id, instrument_id, OrderSide.BUY, client_order_id="durable")

    first = await broker.submit_order(request, "durable")
    second = await broker.submit_order(request, "durable")

    assert first == second
    assert await repository.get_order_by_client_id("durable") is not None
    assert await repository.get_fill_by_broker_id(first.fills[0].broker_fill_id or "") is not None
    assert await repository.get_position(
        account_id=account_id,
        instrument_id=instrument_id,
        mode=AccountMode.PAPER,
    ) is not None


@pytest.mark.asyncio
async def test_backtest_requires_next_candle_open() -> None:
    account_id, instrument_id = uuid4(), uuid4()
    broker = PaperBroker(
        account_id=account_id,
        fill_mode=PaperFillMode.BACKTEST,
        clock=lambda: datetime(2026, 1, 1, tzinfo=UTC),
    )
    broker.set_market(market(instrument_id))
    result = await broker.submit_order(order(account_id, instrument_id, OrderSide.BUY), "backtest")
    assert result.status is OrderStatus.REJECTED
