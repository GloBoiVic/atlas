from datetime import UTC, datetime
from decimal import Decimal
from typing import cast
from uuid import uuid4

import pytest

from backend.backtester.service import StrategyVersionRecord
from backend.core.account_mode import AccountMode
from backend.core.events import EventBus, InMemoryFailureRecorder, TradeClosed
from backend.execution.models import PositionSide, Trade, TradeStatus
from backend.journal.models import JournalDirection
from backend.journal.service import JournalService
from backend.persistence.repositories.memory import (
    InMemoryInstrumentRepository,
    InMemoryJournalRepository,
)
from backend.persistence.repositories.protocols import InstrumentRecord


class FakeStrategyVersions:
    def __init__(self, record: StrategyVersionRecord | None) -> None:
        self.record = record
        self.calls = 0

    async def get(self, strategy_version_id: object) -> StrategyVersionRecord | None:
        self.calls += 1
        return self.record


def make_trade(
    *, strategy_version_id: object | None = None, signal: dict[str, object] | None = None
) -> Trade:
    account_id = uuid4()
    instrument_id = uuid4()
    return Trade(
        account_id=account_id,
        instrument_id=instrument_id,
        position_id=uuid4(),
        direction=PositionSide.LONG,
        entry_price=Decimal("100.25"),
        quantity=Decimal("2.5"),
        total_fees=Decimal("0.10"),
        entry_time=datetime(2026, 1, 1, 12, tzinfo=UTC),
        bot_id=uuid4(),
        strategy_version_id=strategy_version_id,  # type: ignore[arg-type]
        exit_price=Decimal("101.25"),
        gross_pnl=Decimal("2.5"),
        net_pnl=Decimal("2.4"),
        status=TradeStatus.EXITED,
        signal_metadata=signal or {"nested": {"strength": Decimal("0.8")}},
        market_context={"book": {"bid": Decimal("100.2")}},
        exit_time=datetime(2026, 1, 1, 13, tzinfo=UTC),
    )


def make_dependencies(
    trade: Trade,
) -> tuple[InMemoryInstrumentRepository, FakeStrategyVersions]:
    instrument_repository = InMemoryInstrumentRepository(
        [
            InstrumentRecord(
                id=trade.instrument_id,
                symbol="BTCUSDT",
                provider="binance_usdm",
                asset_type="crypto",
                base_currency="BTC",
                quote_currency="USDT",
                price_precision=8,
                quantity_precision=8,
                is_active=True,
            )
        ]
    )
    versions = FakeStrategyVersions(
        StrategyVersionRecord(trade.strategy_version_id or uuid4(), "breakout", "1", "sha")
    )
    return instrument_repository, versions


@pytest.mark.asyncio
async def test_service_subscribes_and_closes() -> None:
    trade = make_trade(strategy_version_id=uuid4())
    instruments, versions = make_dependencies(trade)
    bus = EventBus()
    service = JournalService(bus, InMemoryJournalRepository(), versions, instruments)

    assert bus.stats == {"subscribed_events": 1}
    service.close()
    service.close()
    assert bus.stats == {"subscribed_events": 0}


@pytest.mark.asyncio
async def test_service_maps_trade_and_snapshots_context() -> None:
    signal: dict[str, object] = {"nested": {"strength": Decimal("0.8")}}
    trade = make_trade(strategy_version_id=uuid4(), signal=signal)
    instruments, versions = make_dependencies(trade)
    repository = InMemoryJournalRepository()
    service = JournalService(EventBus(), repository, versions, instruments)

    await service._on_trade_closed(TradeClosed(trade=trade, mode=AccountMode.PAPER))
    entry = await repository.get_by_trade_id(trade.id)

    assert entry is not None
    assert entry.account_id == trade.account_id
    assert entry.bot_id == trade.bot_id
    assert entry.instrument_id == trade.instrument_id
    assert entry.symbol == "BTCUSDT"
    assert entry.direction is JournalDirection.LONG
    assert entry.entry_price == trade.entry_price
    assert entry.exit_price == trade.exit_price
    assert entry.quantity == trade.quantity
    assert entry.pnl == trade.net_pnl
    assert entry.strategy_version_id == trade.strategy_version_id
    assert entry.strategy_name == "breakout"
    assert entry.opened_at == trade.entry_time
    assert entry.closed_at == trade.exit_time
    assert entry.signal == signal
    cast("dict[str, object]", signal["nested"])["strength"] = Decimal("0.1")
    trade.market_context["book"] = {"bid": Decimal("1")}
    assert cast("dict[str, object]", entry.signal["nested"])["strength"] == Decimal("0.8")
    assert cast("dict[str, object]", entry.market_conditions["book"])["bid"] == Decimal("100.2")


@pytest.mark.asyncio
async def test_repeated_trade_closed_events_create_one_entry() -> None:
    trade = make_trade(strategy_version_id=uuid4())
    instruments, versions = make_dependencies(trade)
    repository = InMemoryJournalRepository()
    bus = EventBus()
    JournalService(bus, repository, versions, instruments)
    event = TradeClosed(trade=trade)

    await bus.publish(event)
    await bus.publish(event)
    entries = await repository.list_entries()

    assert len(entries) == 1
    assert versions.calls == 1


@pytest.mark.asyncio
async def test_missing_strategy_identity_fails_closed_and_is_recorded() -> None:
    trade = make_trade()
    instruments, versions = make_dependencies(trade)
    recorder = InMemoryFailureRecorder()
    bus = EventBus(failure_recorder=recorder)
    JournalService(bus, InMemoryJournalRepository(), versions, instruments)

    await bus.publish(TradeClosed(trade=trade, bot_id=trade.bot_id))

    assert len(recorder.failures) == 1
    assert isinstance(recorder.failures[0].exception, ValueError)


@pytest.mark.asyncio
async def test_missing_strategy_version_record_fails_closed() -> None:
    trade = make_trade(strategy_version_id=uuid4())
    instruments, _ = make_dependencies(trade)
    repository = InMemoryJournalRepository()
    service = JournalService(
        EventBus(), repository, FakeStrategyVersions(None), instruments
    )

    with pytest.raises(ValueError, match="strategy version"):
        await service._on_trade_closed(TradeClosed(trade=trade))

    assert await repository.get_by_trade_id(trade.id) is None
