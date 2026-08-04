from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from backend.core.account_mode import AccountMode
from backend.execution import (
    AccountInfo,
    BrokerSnapshot,
    ExecutableMarket,
    Fill,
    Order,
    OrderResult,
    OrderSide,
    OrderStatus,
    PaperBroker,
    Position,
    PositionSide,
    Reconciler,
    ReconciliationBlock,
    ReconciliationResult,
)
from backend.persistence.repositories.memory import InMemoryExecutionRepository

NOW = datetime(2026, 1, 1, tzinfo=UTC)


class SnapshotBroker:
    def __init__(self, snapshot: BrokerSnapshot) -> None:
        self.snapshot = snapshot
        self.calls = 0

    async def reconcile(self) -> BrokerSnapshot:
        self.calls += 1
        return self.snapshot

    async def submit_order(self, order: Order, client_order_id: str) -> OrderResult:
        raise NotImplementedError

    async def cancel_order(self, order_id: str) -> bool:
        return False

    async def get_positions(self) -> list[Position]:
        return list(self.snapshot.positions)

    async def get_account(self) -> AccountInfo:
        return self.snapshot.account


def make_snapshot(
    account_id: UUID,
    *,
    orders: tuple[Order, ...] = (),
    positions: tuple[Position, ...] = (),
    fills: tuple[Fill, ...] = (),
) -> BrokerSnapshot:
    return BrokerSnapshot(
        account=AccountInfo(
            account_id=account_id,
            balance=Decimal("1000"),
            equity=Decimal("1000"),
            available_balance=Decimal("1000"),
            as_of=NOW,
        ),
        orders=orders,
        positions=positions,
        fills=fills,
        as_of=NOW,
    )


def make_order(
    account_id: UUID,
    instrument_id: UUID,
    *,
    client_order_id: str = "client-1",
    broker_order_id: str | None = None,
    status: OrderStatus = OrderStatus.PENDING,
    bot_id: UUID | None = None,
    strategy_version_id: UUID | None = None,
) -> Order:
    return Order(
        account_id=account_id,
        instrument_id=instrument_id,
        side=OrderSide.BUY,
        quantity=Decimal("1"),
        client_order_id=client_order_id,
        broker_order_id=broker_order_id,
        status=status,
        bot_id=bot_id,
        strategy_version_id=strategy_version_id,
        mode=AccountMode.PAPER,
        created_at=NOW,
        updated_at=NOW,
    )


def make_position(account_id: UUID, instrument_id: UUID) -> Position:
    return Position(
        account_id=account_id,
        instrument_id=instrument_id,
        side=PositionSide.LONG,
        quantity=Decimal("1"),
        entry_price=Decimal("100"),
        mode=AccountMode.PAPER,
        opened_at=NOW,
    )


async def run_reconciliation(
    repository: InMemoryExecutionRepository,
    snapshot: BrokerSnapshot,
    account_id: UUID,
    instrument_id: UUID,
    *,
    coordinator: ReconciliationBlock | None = None,
    bot_id: UUID | None = None,
) -> ReconciliationResult:
    reconciler = Reconciler(
        SnapshotBroker(snapshot), repository, repository, coordinator=coordinator
    )
    return await reconciler.reconcile(
        account_id=account_id,
        mode=AccountMode.PAPER,
        instrument_id=instrument_id,
        bot_id=bot_id,
    )


@pytest.mark.asyncio
async def test_matching_snapshot_clears_block_and_persists_run() -> None:
    account_id, instrument_id = uuid4(), uuid4()
    repository = InMemoryExecutionRepository()
    order = await repository.create_order(
        make_order(account_id, instrument_id, broker_order_id="broker-1")
    )
    position = make_position(account_id, instrument_id)
    await repository.save_position(position)
    coordinator = _Coordinator()
    result = await run_reconciliation(
        repository,
        make_snapshot(account_id, orders=(order,), positions=(position,)),
        account_id,
        instrument_id,
        coordinator=coordinator,
    )
    assert result.safe_to_execute is True
    assert coordinator.cleared == [(account_id, instrument_id, AccountMode.PAPER)]
    assert len(repository._reconciliations) == 1


@pytest.mark.asyncio
async def test_broker_order_without_local_provenance_blocks() -> None:
    account_id, instrument_id = uuid4(), uuid4()
    result = await run_reconciliation(
        InMemoryExecutionRepository(),
        make_snapshot(account_id, orders=(make_order(account_id, instrument_id),)),
        account_id,
        instrument_id,
    )
    assert result.status == "blocked"
    assert any(item.startswith("missing_local_order") for item in result.differences)


@pytest.mark.asyncio
async def test_unknown_order_found_is_resolved_with_local_provenance() -> None:
    account_id, instrument_id, bot_id, strategy_id = uuid4(), uuid4(), uuid4(), uuid4()
    repository = InMemoryExecutionRepository()
    local = make_order(
        account_id,
        instrument_id,
        client_order_id="unknown-client",
        broker_order_id="broker-unknown",
        status=OrderStatus.UNKNOWN,
        bot_id=bot_id,
        strategy_version_id=strategy_id,
    )
    await repository.create_order(local)
    broker_order = replace(local, id=uuid4(), status=OrderStatus.FILLED)
    await run_reconciliation(
        repository,
        make_snapshot(account_id, orders=(broker_order,)),
        account_id,
        instrument_id,
    )
    recovered = await repository.get_order_by_client_id("unknown-client")
    assert recovered is not None
    assert recovered.status is OrderStatus.FILLED
    assert recovered.bot_id == bot_id


@pytest.mark.asyncio
async def test_unknown_order_absent_is_canceled_and_does_not_block() -> None:
    account_id, instrument_id = uuid4(), uuid4()
    repository = InMemoryExecutionRepository()
    await repository.create_order(
        make_order(
            account_id,
            instrument_id,
            client_order_id="unknown-client",
            status=OrderStatus.UNKNOWN,
        )
    )
    result = await run_reconciliation(
        repository, make_snapshot(account_id), account_id, instrument_id
    )
    assert result.safe_to_execute is True
    recovered = await repository.get_order_by_client_id("unknown-client")
    assert recovered is not None
    assert recovered.status is OrderStatus.CANCELED


@pytest.mark.asyncio
async def test_broker_position_mismatch_is_persisted_authoritatively_but_blocks() -> None:
    account_id, instrument_id = uuid4(), uuid4()
    repository = InMemoryExecutionRepository()
    local = make_position(account_id, instrument_id)
    await repository.save_position(local)
    broker_position = replace(local, quantity=Decimal("2"), id=uuid4())
    result = await run_reconciliation(
        repository,
        make_snapshot(account_id, positions=(broker_position,)),
        account_id,
        instrument_id,
    )
    assert result.status == "blocked"
    current = await repository.get_position(
        account_id=account_id, instrument_id=instrument_id, mode=AccountMode.PAPER
    )
    assert current is not None
    assert current.quantity == Decimal("2")


@pytest.mark.asyncio
async def test_duplicate_execution_report_is_idempotent() -> None:
    account_id, instrument_id = uuid4(), uuid4()
    repository = InMemoryExecutionRepository()
    order = make_order(account_id, instrument_id, broker_order_id="broker-1")
    await repository.create_order(order)
    fill = Fill(
        order_id=order.id,
        account_id=account_id,
        instrument_id=instrument_id,
        side=OrderSide.BUY,
        quantity=Decimal("1"),
        price=Decimal("100"),
        fee=Decimal("1"),
        filled_at=NOW,
        broker_fill_id="execution-1",
    )
    await run_reconciliation(
        repository,
        make_snapshot(account_id, orders=(order,), fills=(fill,)),
        account_id,
        instrument_id,
    )
    await run_reconciliation(
        repository,
        make_snapshot(account_id, orders=(order,), fills=(fill,)),
        account_id,
        instrument_id,
    )
    assert len(await repository.get_fills(account_id=account_id, mode=AccountMode.PAPER)) == 1


@pytest.mark.asyncio
async def test_paper_broker_reconcile_contains_orders_and_fills() -> None:
    account_id, instrument_id = uuid4(), uuid4()
    broker = PaperBroker(account_id=account_id, clock=lambda: NOW)
    broker.set_market(
        ExecutableMarket(
            instrument_id=instrument_id,
            bid=Decimal("99"),
            ask=Decimal("101"),
            mark_price=Decimal("100"),
            as_of=NOW,
        )
    )
    order = make_order(account_id, instrument_id)
    result = await broker.submit_order(order, order.client_order_id)
    snapshot = await broker.reconcile()
    assert snapshot.orders[0].status is OrderStatus.FILLED
    assert snapshot.orders[0].broker_order_id == result.order_id
    assert snapshot.fills == result.fills


@pytest.mark.asyncio
async def test_broker_fill_missing_locally_is_appended_when_order_is_known() -> None:
    account_id, instrument_id = uuid4(), uuid4()
    repository = InMemoryExecutionRepository()
    order = make_order(account_id, instrument_id, broker_order_id="broker-1")
    await repository.create_order(order)
    fill = Fill(
        order_id=order.id,
        account_id=account_id,
        instrument_id=instrument_id,
        side=OrderSide.BUY,
        quantity=Decimal("1"),
        price=Decimal("100"),
        fee=Decimal("1"),
        filled_at=NOW,
        broker_fill_id="recovered-execution",
    )
    result = await run_reconciliation(
        repository,
        make_snapshot(account_id, orders=(order,), fills=(fill,)),
        account_id,
        instrument_id,
    )
    assert result.safe_to_execute is True
    assert await repository.get_fill_by_broker_id("recovered-execution") == fill


@pytest.mark.asyncio
async def test_local_position_absent_from_broker_is_closed_and_blocks() -> None:
    account_id, instrument_id = uuid4(), uuid4()
    repository = InMemoryExecutionRepository()
    await repository.save_position(make_position(account_id, instrument_id))
    result = await run_reconciliation(
        repository, make_snapshot(account_id), account_id, instrument_id
    )
    assert result.status == "blocked"
    assert result.differences == (f"missing_broker_position:{instrument_id}",)
    assert (
        await repository.get_position(
            account_id=account_id, instrument_id=instrument_id, mode=AccountMode.PAPER
        )
        is None
    )


@pytest.mark.asyncio
async def test_memory_fills_are_scoped_by_their_mode_bearing_orders() -> None:
    account_id, instrument_id = uuid4(), uuid4()
    repository = InMemoryExecutionRepository()
    paper = make_order(account_id, instrument_id, client_order_id="paper")
    testnet = replace(paper, id=uuid4(), client_order_id="testnet", mode=AccountMode.TESTNET)
    await repository.create_order(paper)
    await repository.create_order(testnet)
    for order, fill_id in ((paper, "paper-fill"), (testnet, "testnet-fill")):
        await repository.append_fill(
            Fill(
                order_id=order.id,
                account_id=account_id,
                instrument_id=instrument_id,
                side=OrderSide.BUY,
                quantity=Decimal("1"),
                price=Decimal("100"),
                fee=Decimal("1"),
                filled_at=NOW,
                broker_fill_id=fill_id,
            )
        )
    paper_fills = await repository.get_fills(account_id=account_id, mode=AccountMode.PAPER)
    assert [fill.broker_fill_id for fill in paper_fills] == ["paper-fill"]


@pytest.mark.asyncio
async def test_entry_points_and_bot_id_are_persisted() -> None:
    account_id, instrument_id, bot_id = uuid4(), uuid4(), uuid4()
    repository = InMemoryExecutionRepository()
    broker = SnapshotBroker(make_snapshot(account_id))
    reconciler = Reconciler(broker, repository, repository)
    for entry_point in (reconciler.startup, reconciler.reconnect, reconciler.periodic):
        result = await entry_point(
            account_id=account_id,
            mode=AccountMode.PAPER,
            instrument_id=instrument_id,
            bot_id=bot_id,
        )
        assert result.safe_to_execute is True
    assert broker.calls == 3
    records = list(repository._reconciliations.values())
    assert all(record.bot_id == bot_id for record in records)


@pytest.mark.asyncio
async def test_account_scope_mismatch_blocks_execution() -> None:
    account_id, broker_account, instrument_id = uuid4(), uuid4(), uuid4()
    coordinator = _Coordinator()
    result = await run_reconciliation(
        InMemoryExecutionRepository(),
        make_snapshot(broker_account),
        account_id,
        instrument_id,
        coordinator=coordinator,
    )
    assert result.status == "blocked"
    assert result.differences == ("account_scope_mismatch",)
    assert coordinator.blocked == [(account_id, instrument_id, AccountMode.PAPER)]


class _Coordinator:
    def __init__(self) -> None:
        self.cleared: list[tuple[object, object, AccountMode]] = []
        self.blocked: list[tuple[object, object, AccountMode]] = []

    def clear_block(self, account_id: UUID, instrument_id: UUID, mode: AccountMode) -> None:
        self.cleared.append((account_id, instrument_id, mode))

    def block(self, account_id: UUID, instrument_id: UUID, mode: AccountMode) -> None:
        self.blocked.append((account_id, instrument_id, mode))
