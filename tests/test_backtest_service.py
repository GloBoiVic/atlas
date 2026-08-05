import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, cast
from unittest.mock import patch
from uuid import uuid4

import pytest

from backend.backtester.engine import BacktestReplayResult
from backend.backtester.models import BacktestConfig, BacktestRun, BacktestStatus, BacktestTrade
from backend.backtester.service import (
    BacktestRunConflict,
    BacktestService,
    StrategyVersionRecord,
)
from backend.data.models import Candle
from backend.persistence.repositories.backtest import InMemoryBacktestRepository
from backend.persistence.repositories.memory import (
    InMemoryCandleRepository,
    InMemoryInstrumentRepository,
)
from backend.persistence.repositories.protocols import InstrumentRecord
from backend.strategy.base import Strategy
from backend.strategy.contracts import (
    DataRequirement,
    DataType,
    SignalDirection,
    StrategyDecision,
)
from backend.strategy.registry import StrategyRegistry


class NoopStrategy(Strategy):
    def required_data(self) -> DataRequirement:
        return DataRequirement(DataType.CANDLE, "1m", warmup_candles=1)

    def on_candle(self, candle: Candle) -> None:
        return None


class FailingStrategy(Strategy):
    def required_data(self) -> DataRequirement:
        return DataRequirement(DataType.CANDLE, "1m")

    def on_candle(self, candle: Candle) -> None:
        raise RuntimeError("strategy failure " + ("x" * 1200))


class ProtectiveStrategy(Strategy):
    def required_data(self) -> DataRequirement:
        return DataRequirement(DataType.CANDLE, "1m")

    def on_candle(self, candle: Candle) -> StrategyDecision | None:
        if candle.open == Decimal("100"):
            return StrategyDecision(SignalDirection.BUY, Decimal("1"), {"reason": "stop"})
        return None


class Versions:
    def __init__(self, record: StrategyVersionRecord | None) -> None:
        self.record = record

    async def get(self, strategy_version_id: Any) -> StrategyVersionRecord | None:
        if self.record is None or strategy_version_id != self.record.id:
            return None
        return self.record


def _setup(strategy_factory: type[Strategy] = NoopStrategy) -> tuple[
    BacktestService,
    BacktestConfig,
    InMemoryBacktestRepository,
    InMemoryCandleRepository,
    list[Candle],
]:
    instrument_id, account_id, version_id = uuid4(), uuid4(), uuid4()
    instrument_repository = InMemoryInstrumentRepository(
        [
            InstrumentRecord(
                id=instrument_id,
                symbol="BTCUSDT",
                provider="csv",
                asset_type="crypto",
                base_currency="BTC",
                quote_currency="USDT",
                price_precision=8,
                quantity_precision=8,
                is_active=True,
                constraints={"tick_size": "0.01", "step_size": "0.001", "min_qty": "0.001"},
            )
        ]
    )
    candles = InMemoryCandleRepository()
    start = datetime(2026, 1, 1, tzinfo=UTC)
    candle_values = [Decimal("100"), Decimal("101"), Decimal("102")]
    candles_to_save = [
        Candle(
            instrument_id=instrument_id,
            provider="csv",
            timeframe="1m",
            open_time=start + timedelta(minutes=index),
            open=value,
            high=value,
            low=value,
            close=value,
        )
        for index, value in enumerate(candle_values)
    ]
    version = StrategyVersionRecord(version_id, "noop", "1.0", "commit")
    registry = StrategyRegistry()
    registry.register(version_id, version.name, version.commit_sha, strategy_factory)
    repository = InMemoryBacktestRepository()
    service = BacktestService(
        candle_repository=candles,
        backtest_repository=repository,
        instrument_repository=instrument_repository,
        strategy_version_repository=Versions(version),
        strategy_registry=registry,
    )
    config = BacktestConfig(
        instrument_id=instrument_id,
        account_id=account_id,
        strategy_version_id=version_id,
        timeframe="1m",
        start_date=start,
        end_date=start + timedelta(minutes=2),
        strategy_parameters={},
        risk_config={},
        execution_config={
            "fee_rate": Decimal("0"),
            "slippage_rate": Decimal("0"),
            "fill_model": "next_candle_open",
            "protective_trigger_rule": "stop_loss_first",
        },
        initial_balance=Decimal("1000"),
    )
    return service, config, repository, candles, candles_to_save


@pytest.mark.asyncio
async def test_service_persists_terminal_success_and_dataset_identity() -> None:
    service, config, repository, candles, candles_to_save = _setup()
    await candles.save_many(candles_to_save)

    run = await service.run(config)

    assert run.status is BacktestStatus.COMPLETED
    assert run.dataset_id.startswith("sha256:")
    assert (await repository.get_run(run.id)).status is BacktestStatus.COMPLETED  # type: ignore[union-attr]
    assert run.completed_at is not None
    assert run.last_processed_timestamp == candles_to_save[-1].open_time


@pytest.mark.asyncio
async def test_service_marks_empty_dataset_failed_without_trades() -> None:
    service, config, repository, _, _ = _setup()

    run = await service.run(config)

    assert run.status is BacktestStatus.FAILED
    assert run.error_message == "backtest dataset is empty"
    assert await repository.get_trades(run.id) == []
    assert run.completed_at is not None


@pytest.mark.asyncio
async def test_service_does_not_rerun_terminal_run() -> None:
    service, config, repository, _, _ = _setup()
    run_id = uuid4()
    existing = await service.run(config, run_id=run_id)

    returned = await service.run(config, run_id=run_id)

    assert returned == existing


@pytest.mark.asyncio
async def test_service_rejects_active_run_id() -> None:
    service, config, repository, _, _ = _setup()
    run_id = uuid4()
    existing = await service.run(config, run_id=run_id)
    await repository.update_run(replace(existing, status=BacktestStatus.RUNNING))
    with pytest.raises(BacktestRunConflict):
        await service.run(config, run_id=run_id)


@pytest.mark.asyncio
async def test_service_persists_cancelled_and_reraises_cancellation() -> None:
    service, config, repository, _, _ = _setup()
    class CancelledEngine:
        last_processed_timestamp = None

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def run(self, config: BacktestConfig, *, run_id: Any) -> BacktestReplayResult:
            task = asyncio.current_task()
            assert task is not None
            task.cancel()
            await asyncio.sleep(0)
            raise AssertionError("cancellation should have interrupted the task")

    with (
        patch("backend.backtester.service.BacktesterEngine", CancelledEngine),
        pytest.raises(asyncio.CancelledError),
    ):
        await service.run(config)

    runs = await repository.list_runs()
    assert runs[0].status is BacktestStatus.CANCELLED
    assert runs[0].completed_at is not None


@pytest.mark.asyncio
async def test_service_rejects_missing_strategy_version() -> None:
    service, config, _, _, _ = _setup()
    cast("Versions", service._versions).record = None

    with pytest.raises(ValueError, match="strategy version"):
        await service.run(config)


@pytest.mark.asyncio
async def test_service_rejects_missing_instrument() -> None:
    service, config, _, _, _ = _setup()
    missing_config = replace(config, instrument_id=uuid4())

    with pytest.raises(ValueError, match="instrument"):
        await service.run(missing_config)


@pytest.mark.asyncio
async def test_service_rejects_inactive_instrument() -> None:
    service, config, _, _, _ = _setup()
    instrument = await service._instruments.get(config.instrument_id)
    assert instrument is not None
    instrument_repository = cast("InMemoryInstrumentRepository", service._instruments)
    instrument_repository._instruments[config.instrument_id] = replace(instrument, is_active=False)

    with pytest.raises(ValueError, match="instrument"):
        await service.run(config)


@pytest.mark.asyncio
async def test_service_marks_strategy_failure_failed_with_bounded_metadata() -> None:
    service, config, repository, candles, candles_to_save = _setup(FailingStrategy)
    await candles.save_many(candles_to_save)

    run = await service.run(config)

    assert run.status is BacktestStatus.FAILED
    assert run.error_message is not None
    assert len(run.error_message) <= 1000
    assert run.last_processed_timestamp == candles_to_save[0].open_time
    assert run.completed_at is not None
    assert (await repository.get_run(run.id)).status is BacktestStatus.FAILED  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_service_projects_protective_trade() -> None:
    service, config, repository, candles, candles_to_save = _setup(ProtectiveStrategy)
    protective_candles = [
        replace(candles_to_save[0], high=Decimal("100"), low=Decimal("100")),
        replace(
            candles_to_save[1],
            high=Decimal("101"),
            low=Decimal("98"),
            close=Decimal("98"),
        ),
        candles_to_save[2],
    ]
    await candles.save_many(protective_candles)
    config = replace(
        config,
        risk_config={"per_trade_risk": Decimal("0.01"), "stop_percentage": Decimal("0.02")},
    )

    run = await service.run(config)

    trades = await repository.get_trades(run.id)
    assert run.status is BacktestStatus.COMPLETED
    assert len(trades) == 1
    assert trades[0].exit_time == protective_candles[1].open_time


@pytest.mark.asyncio
async def test_service_rethrows_finalize_failure_after_failed_fallback() -> None:
    service, config, _, candles, candles_to_save = _setup()
    await candles.save_many(candles_to_save)

    class FailingFinalizeRepository(InMemoryBacktestRepository):
        async def finalize_run(
            self, run: BacktestRun, trades: list[BacktestTrade]
        ) -> BacktestRun:
            raise RuntimeError("database connection lost")

    failing_repository = FailingFinalizeRepository()
    service._backtests = failing_repository

    with pytest.raises(RuntimeError, match="database connection lost"):
        await service.run(config)

    runs = await failing_repository.list_runs()
    assert runs[0].status is BacktestStatus.FAILED
    assert runs[0].error_message is not None
    assert len(runs[0].error_message) <= 1000
    assert runs[0].completed_at is not None
