from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import JSON, MetaData, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from backend.backtester.models import (
    BacktestConfig,
    BacktestResult,
    BacktestRun,
    BacktestStatus,
    BacktestTrade,
)
from backend.persistence.models import BacktestRunModel, BacktestTradeModel, Instrument
from backend.persistence.repositories.backtest import (
    InMemoryBacktestRepository,
    SqlAlchemyBacktestRepository,
)

INSTRUMENT_ID = UUID("00000000-0000-0000-0000-000000000001")
RUN_ID = UUID("00000000-0000-0000-0000-000000000002")


def make_run(run_id: UUID = RUN_ID, created_at: datetime | None = None) -> BacktestRun:
    timestamp = created_at or datetime(2026, 8, 1, tzinfo=UTC)
    return BacktestRun(
        id=run_id,
        strategy_name="sma",
        strategy_version="1.0",
        strategy_commit_sha="a" * 40,
        strategy_parameters={"threshold": Decimal("1.25")},
        instrument_id=INSTRUMENT_ID,
        symbol="BTCUSDT",
        timeframe="1m",
        data_source="binance",
        dataset_id="sha256:test",
        start_date=timestamp,
        end_date=timestamp + timedelta(minutes=2),
        risk_config={"risk": Decimal("0.01")},
        execution_config={
            "fee_rate": Decimal("0.001"),
            "fill_model": "next_candle_open",
            "protective_trigger_rule": "stop_loss_first",
        },
        fill_model="next_candle_open",
        status=BacktestStatus.PENDING,
        created_at=timestamp,
    )


def make_trade(trade_id: UUID, entry_time: datetime) -> BacktestTrade:
    return BacktestTrade(
        id=trade_id,
        backtest_run_id=RUN_ID,
        instrument_id=INSTRUMENT_ID,
        symbol="BTCUSDT",
        direction="buy",
        entry_price=Decimal("100.123456789012"),
        quantity=Decimal("0.123456789012"),
        pnl=Decimal("1.000000000001"),
        entry_time=entry_time,
        exit_price=Decimal("101.123456789012"),
        exit_time=entry_time + timedelta(minutes=1),
        signal_metadata={"strength": Decimal("0.5")},
    )


@pytest.mark.asyncio
async def test_memory_repository_is_idempotent_and_deterministically_ordered() -> None:
    repository = InMemoryBacktestRepository()
    run = make_run()
    assert await repository.create_run(run) == run
    assert await repository.create_run(make_run()) == run
    assert await repository.list_runs() == [run]

    first = make_trade(UUID("00000000-0000-0000-0000-000000000010"), run.start_date)
    second = make_trade(UUID("00000000-0000-0000-0000-000000000011"), run.start_date)
    assert await repository.save_trade(first) == first
    assert await repository.save_trade(first) == first
    assert await repository.save_trade(second) == second
    assert [trade.id for trade in await repository.get_trades(RUN_ID)] == [first.id, second.id]


@pytest.mark.asyncio
async def test_sqlalchemy_repository_preserves_decimal_json_and_cascades() -> None:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata = MetaData()
    for table in (Instrument.__table__, BacktestRunModel.__table__, BacktestTradeModel.__table__):
        copied = table.to_metadata(metadata)  # type: ignore[attr-defined]
        for column in copied.columns:
            if column.type.__class__.__name__ == "JSONB":
                column.type = JSON()
    async with engine.begin() as connection:
        await connection.run_sync(metadata.create_all)
        await connection.exec_driver_sql("PRAGMA foreign_keys=ON")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    repository = SqlAlchemyBacktestRepository(factory)
    async with factory.begin() as session:
        session.add(
            Instrument(
                id=INSTRUMENT_ID,
                symbol="BTCUSDT",
                asset_type="crypto",
                provider="binance",
                price_precision=8,
                quantity_precision=8,
            )
        )

    run = make_run()
    assert await repository.create_run(run) == run
    assert await repository.create_run(make_run()) == run
    fetched_pending = await repository.get_run(RUN_ID)
    assert fetched_pending is not None
    assert fetched_pending.result is None
    trade = make_trade(UUID("00000000-0000-0000-0000-000000000012"), run.start_date)
    assert await repository.save_trade(trade) == trade
    assert await repository.get_trades(RUN_ID) == [trade]
    updated = make_run()
    object.__setattr__(updated, "status", BacktestStatus.COMPLETED)
    object.__setattr__(updated, "created_at", datetime(2027, 1, 1, tzinfo=UTC))
    object.__setattr__(updated, "result", BacktestResult(
        total_return=Decimal("0.1"), total_pnl=Decimal("1.2"),
        starting_equity=Decimal("100"), ending_equity=Decimal("101.2"),
    ))
    assert (await repository.update_run(updated)).status == BacktestStatus.COMPLETED  # type: ignore[union-attr]
    assert (await repository.get_run(RUN_ID)).result.total_pnl == Decimal("1.2")  # type: ignore[union-attr]
    assert (await repository.get_run(RUN_ID)).created_at == run.created_at  # type: ignore[union-attr]
    finalized = replace(updated, dataset_id="sha256:finalized", created_at=run.created_at)
    assert await repository.finalize_run(finalized, []) == finalized
    assert (await repository.get_run(RUN_ID)).dataset_id == "sha256:finalized"  # type: ignore[union-attr]

    async with factory.begin() as session:
        row = await session.get(BacktestRunModel, RUN_ID)
        assert row is not None
        await session.delete(row)
    async with factory() as session:
        assert await session.scalar(select(BacktestTradeModel.id)) is None
    await engine.dispose()


def test_backtest_config_rejects_missing_execution_contract() -> None:
    with pytest.raises(ValueError, match="fill_model"):
        BacktestConfig(
            instrument_id=INSTRUMENT_ID,
            account_id=RUN_ID,
            strategy_version_id=UUID("00000000-0000-0000-0000-000000000003"),
            timeframe="1m",
            start_date=datetime(2026, 8, 1, tzinfo=UTC),
            end_date=datetime(2026, 8, 1, 0, 1, tzinfo=UTC),
            strategy_parameters={}, risk_config={}, execution_config={},
            initial_balance=Decimal("100"),
        )
