from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from backend.core.account_mode import AccountMode
from backend.core.events import EventBus, MarketContextUpdated
from backend.data.models import Instrument, MarketContext
from backend.execution import (
    ExecutableMarket,
    Order,
    OrderResult,
    OrderSide,
    PositionStatus,
)
from backend.execution.paper_broker import PaperBroker
from backend.persistence.repositories.memory import InMemoryExecutionRepository
from backend.worker.paper_pipeline import LivePaperPipeline


class _Session:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True


class _Engine:
    def __init__(self) -> None:
        self.enabled = True
        self.closed = False

    def set_execution_enabled(self, enabled: bool) -> None:
        self.enabled = enabled

    @property
    def execution_enabled(self) -> bool:
        return self.enabled

    def close(self) -> None:
        self.closed = True


class _RecordingBroker(PaperBroker):
    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self.maintenance_calls: list[str] = []

    async def check_protective_triggers(
        self, *args: object, **kwargs: object
    ) -> OrderResult | None:
        self.maintenance_calls.append("protective")
        return await super().check_protective_triggers(*args, **kwargs)  # type: ignore[arg-type]

    async def check_liquidation(self, *args: object, **kwargs: object) -> OrderResult | None:
        self.maintenance_calls.append("liquidation")
        return await super().check_liquidation(*args, **kwargs)  # type: ignore[arg-type]

def _context(instrument_id: UUID, timestamp: datetime) -> MarketContext:
    return MarketContext(
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


def _funding_context(
    instrument_id: UUID, timestamp: datetime, *, mark: str = "100"
) -> MarketContext:
    context = _context(instrument_id, timestamp - timedelta(hours=8))
    return MarketContext(
        instrument_id=instrument_id,
        provider=context.provider,
        bid=context.bid,
        ask=context.ask,
        mark_price=Decimal(mark),
        index_price=context.index_price,
        funding_rate=context.funding_rate,
        next_funding_time=timestamp,
        as_of=timestamp,
        bid_at=timestamp,
        ask_at=timestamp,
        mark_at=timestamp,
        index_at=timestamp,
        funding_at=timestamp,
    )


def _pipeline(
    account_id: UUID,
    bot_id: UUID,
    instrument_id: UUID,
    broker: PaperBroker,
    repository: InMemoryExecutionRepository,
    bus: EventBus,
) -> LivePaperPipeline:
    return LivePaperPipeline(
        event_bus=bus,
        session=_Session(),  # type: ignore[arg-type]
        strategy_engine=_Engine(),  # type: ignore[arg-type]
        risk_engine=_Engine(),  # type: ignore[arg-type]
        execution_engine=_Engine(),  # type: ignore[arg-type]
        broker=broker,
        repository=repository,
        instrument=Instrument(instrument_id, "BTCUSDT", "binance_usdm", "crypto"),
        account_id=account_id,
        bot_id=bot_id,
    )


@pytest.mark.asyncio
async def test_live_paper_pipeline_scopes_context_and_cleans_up() -> None:
    account_id, bot_id, instrument_id = uuid4(), uuid4(), uuid4()
    repository = InMemoryExecutionRepository()
    broker = _RecordingBroker(
        account_id=account_id,
        repository=repository,
        clock=lambda: datetime(2026, 1, 1, tzinfo=UTC),
    )
    session = _Session()
    strategy, risk, execution = _Engine(), _Engine(), _Engine()
    bus = EventBus()
    pipeline = LivePaperPipeline(
        event_bus=bus,
        session=session,  # type: ignore[arg-type]
        strategy_engine=strategy,  # type: ignore[arg-type]
        risk_engine=risk,  # type: ignore[arg-type]
        execution_engine=execution,  # type: ignore[arg-type]
        broker=broker,
        repository=repository,
        instrument=Instrument(instrument_id, "BTCUSDT", "binance_usdm", "crypto"),
        account_id=account_id,
        bot_id=bot_id,
    )
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)

    await pipeline.start()
    await bus.publish(
        MarketContextUpdated(
            context=_context(instrument_id, timestamp),
            account_id=account_id,
            bot_id=bot_id,
            mode=AccountMode.PAPER,
            occurred_at=timestamp,
        )
    )
    await pipeline.stop()

    assert session.started
    assert session.stopped
    assert strategy.closed and risk.closed and execution.closed


@pytest.mark.asyncio
async def test_funding_computation_long_and_short_uses_broker_position() -> None:
    account_id, bot_id, instrument_id = uuid4(), uuid4(), uuid4()
    repository = InMemoryExecutionRepository()
    broker = PaperBroker(
        account_id=account_id,
        repository=repository,
        clock=lambda: datetime(2026, 1, 1, tzinfo=UTC),
    )
    bus = EventBus()
    _pipeline(account_id, bot_id, instrument_id, broker, repository, bus)
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    broker.set_market(
        ExecutableMarket(instrument_id, Decimal("99"), Decimal("101"), Decimal("100"), timestamp)
    )
    await broker.submit_order(
        Order(
            account_id=account_id,
            instrument_id=instrument_id,
            side=OrderSide.BUY,
            quantity=Decimal("2"),
            client_order_id="funding-long",
            mode=AccountMode.PAPER,
        ),
        "funding-long",
    )
    position = (await broker.get_positions())[0]
    await repository.save_position(
        replace(position, status=PositionStatus.CLOSED, closed_at=timestamp)
    )
    await bus.publish(
        MarketContextUpdated(
            context=_funding_context(instrument_id, timestamp + timedelta(hours=8)),
            account_id=account_id,
            bot_id=bot_id,
            mode=AccountMode.PAPER,
            occurred_at=timestamp + timedelta(hours=8),
        )
    )
    adjustments = await repository.get_funding_adjustments(
        account_id=account_id, instrument_id=instrument_id, mode=AccountMode.PAPER
    )
    assert adjustments[0].amount == Decimal("-0.0200")

    await broker.submit_order(
        Order(
            account_id=account_id,
            instrument_id=instrument_id,
            side=OrderSide.SELL,
            quantity=Decimal("2"),
            client_order_id="funding-long-close",
            mode=AccountMode.PAPER,
            reduce_only=True,
        ),
        "funding-long-close",
    )
    await broker.submit_order(
        Order(
            account_id=account_id,
            instrument_id=instrument_id,
            side=OrderSide.SELL,
            quantity=Decimal("1"),
            client_order_id="funding-short",
            mode=AccountMode.PAPER,
        ),
        "funding-short",
    )
    second_timestamp = timestamp + timedelta(hours=16)
    await bus.publish(
        MarketContextUpdated(
            context=_funding_context(instrument_id, second_timestamp),
            account_id=account_id,
            bot_id=bot_id,
            mode=AccountMode.PAPER,
            occurred_at=second_timestamp,
        )
    )
    adjustments = await repository.get_funding_adjustments(
        account_id=account_id, instrument_id=instrument_id, mode=AccountMode.PAPER
    )
    assert [item.amount for item in adjustments] == [Decimal("-0.0200"), Decimal("0.0100")]


@pytest.mark.asyncio
async def test_maintenance_ordering_liquidation_closes_before_funding() -> None:
    account_id, bot_id, instrument_id = uuid4(), uuid4(), uuid4()
    repository = InMemoryExecutionRepository()
    broker = _RecordingBroker(
        account_id=account_id,
        repository=repository,
        initial_balance=Decimal("100"),
        leverage=Decimal("2"),
    )
    bus = EventBus()
    _pipeline(account_id, bot_id, instrument_id, broker, repository, bus)
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    broker.set_market(ExecutableMarket(
        instrument_id, Decimal("100"), Decimal("100"), Decimal("100"), timestamp
    ))

    await broker.submit_order(
        Order(
            account_id=account_id,
            instrument_id=instrument_id,
            side=OrderSide.BUY,
            quantity=Decimal("1"),
            client_order_id="maintenance-entry",
            mode=AccountMode.PAPER,
            leverage=Decimal("2"),
        ),
        "maintenance-entry",
    )
    await bus.publish(
        MarketContextUpdated(
            context=_funding_context(instrument_id, timestamp + timedelta(hours=8), mark="50"),
            account_id=account_id,
            bot_id=bot_id,
            mode=AccountMode.PAPER,
            occurred_at=timestamp + timedelta(hours=8),
        )
    )

    assert await broker.get_positions() == []
    assert broker.maintenance_calls == ["protective", "liquidation"]
    assert await repository.get_funding_adjustments(
        account_id=account_id, instrument_id=instrument_id, mode=AccountMode.PAPER
    ) == []
