from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest

from backend.backtester.engine import BacktesterEngine
from backend.backtester.models import BacktestConfig
from backend.core.account_mode import AccountMode
from backend.core.clock import SimulationClock
from backend.data.models import Candle, Instrument
from backend.execution.broker import OrderResult
from backend.execution.paper_broker import PaperBroker
from backend.persistence.repositories.memory import InMemoryCandleRepository
from backend.strategy.base import Strategy
from backend.strategy.contracts import DataRequirement, DataType, SignalDirection, StrategyDecision


class BuyThenCloseStrategy(Strategy):
    def __init__(self, config: dict[str, object]) -> None:
        super().__init__(config)
        self.calls = 0

    def required_data(self) -> DataRequirement:
        return DataRequirement(DataType.CANDLE, "1m", warmup_candles=1)

    def on_candle(self, candle: Candle) -> StrategyDecision | None:
        self.calls += 1
        if self.calls == 2:
            return StrategyDecision(SignalDirection.BUY, Decimal("1"), {"reason": "entry"})
        if self.calls == 3:
            return StrategyDecision(SignalDirection.CLOSE, Decimal("1"), {"reason": "exit"})
        return None


class FailingStrategy(Strategy):
    def required_data(self) -> DataRequirement:
        return DataRequirement(DataType.CANDLE, "1m")

    def on_candle(self, candle: Candle) -> StrategyDecision:
        raise RuntimeError("strategy failed")


class ProtectiveStopStrategy(Strategy):
    def required_data(self) -> DataRequirement:
        return DataRequirement(DataType.CANDLE, "1m")

    def on_candle(self, candle: Candle) -> StrategyDecision | None:
        if candle.open == Decimal("100"):
            return StrategyDecision(SignalDirection.BUY, Decimal("1"), {"reason": "stop-test"})
        return None


def _instrument(instrument_id: UUID) -> Instrument:
    return Instrument(
        id=instrument_id,
        symbol="BTCUSDT",
        provider="csv",
        asset_type="crypto",
        constraints={"tick_size": "0.01", "step_size": "0.001", "min_qty": "0.001"},
    )


def _candles(instrument_id: UUID) -> list[Candle]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    prices = [(100, 100), (101, 101), (102, 102), (103, 103)]
    return [
        Candle(
            instrument_id=instrument_id,
            provider="csv",
            timeframe="1m",
            open_time=start + timedelta(minutes=index),
            open=Decimal(str(open_price)),
            high=Decimal(str(close_price)),
            low=Decimal(str(open_price)),
            close=Decimal(str(close_price)),
        )
        for index, (open_price, close_price) in enumerate(prices)
    ]


def _config(instrument_id: UUID, account_id: UUID, strategy_id: UUID) -> BacktestConfig:
    return BacktestConfig(
        instrument_id=instrument_id,
        account_id=account_id,
        strategy_version_id=strategy_id,
        timeframe="1m",
        start_date=datetime(2026, 1, 1, tzinfo=UTC),
        end_date=datetime(2026, 1, 1, 0, 3, tzinfo=UTC),
        strategy_parameters={},
        risk_config={"per_trade_risk": Decimal("0.01"), "stop_percentage": Decimal("0.02")},
        execution_config={
            "fee_rate": Decimal("0"),
            "slippage_rate": Decimal("0"),
            "fill_model": "next_candle_open",
            "protective_trigger_rule": "stop_loss_first",
        },
        initial_balance=Decimal("10000"),
    )


@pytest.mark.asyncio
async def test_replay_warms_without_signal_and_fills_at_next_open() -> None:
    instrument_id, account_id, strategy_id = uuid4(), uuid4(), uuid4()
    candles = _candles(instrument_id)
    repository = InMemoryCandleRepository()
    await repository.save_many(candles)
    strategy = BuyThenCloseStrategy({})
    engine = BacktesterEngine(
        candle_repository=repository,
        instrument=_instrument(instrument_id),
        strategy=strategy,
        strategy_version_id=strategy_id,
        strategy_name="test",
        strategy_commit_sha="test-commit",
    )

    result = await engine.run(_config(instrument_id, account_id, strategy_id), run_id=uuid4())

    assert len(result.trades) == 1
    assert result.trades[0].entry_price == Decimal("102")
    assert result.trades[0].exit_price == Decimal("103")
    assert result.result.total_pnl == Decimal("49.504")
    assert result.result.total_return == Decimal("0.0049504")
    assert result.result.starting_equity == Decimal("10000")
    assert result.result.ending_equity == Decimal("10049.504")
    assert result.result.max_drawdown == Decimal("0")
    assert result.result.win_rate == 1.0
    assert result.result.profit_factor is None
    assert result.result.sharpe_ratio is None
    assert result.result.trade_count == 1
    assert result.result.winning_trade_count == 1
    assert result.result.losing_trade_count == 0
    assert strategy.calls == 0
    assert engine.last_run_event_bus is not None
    assert engine.last_run_event_bus.stats["subscribed_events"] == 0


@pytest.mark.asyncio
async def test_final_candle_signal_is_not_executed() -> None:
    instrument_id, account_id, strategy_id = uuid4(), uuid4(), uuid4()
    repository = InMemoryCandleRepository()
    candles = _candles(instrument_id)[:2]
    await repository.save_many(candles)
    strategy = BuyThenCloseStrategy({})
    engine = BacktesterEngine(
        candle_repository=repository,
        instrument=_instrument(instrument_id),
        strategy=strategy,
        strategy_version_id=strategy_id,
        strategy_name="test",
        strategy_commit_sha="test-commit",
    )

    result = await engine.run(_config(instrument_id, account_id, strategy_id), run_id=uuid4())

    assert result.trades == ()


@pytest.mark.asyncio
async def test_strategy_failure_releases_all_run_subscriptions() -> None:
    instrument_id, account_id, strategy_id = uuid4(), uuid4(), uuid4()
    repository = InMemoryCandleRepository()
    await repository.save_many(_candles(instrument_id))
    engine = BacktesterEngine(
        candle_repository=repository,
        instrument=_instrument(instrument_id),
        strategy=FailingStrategy({}),
        strategy_version_id=strategy_id,
        strategy_name="test",
        strategy_commit_sha="test-commit",
    )

    with pytest.raises(RuntimeError, match="handler failed"):
        await engine.run(_config(instrument_id, account_id, strategy_id), run_id=uuid4())

    assert engine.last_run_event_bus is not None
    assert engine.last_run_event_bus.stats["subscribed_events"] == 0


def test_simulation_clock_does_not_use_wall_time() -> None:
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    clock = SimulationClock(timestamp)

    assert clock.now() == timestamp


@pytest.mark.asyncio
async def test_replay_protective_stop_fills_at_next_open() -> None:
    instrument_id, account_id, strategy_id = uuid4(), uuid4(), uuid4()
    candles = _candles(instrument_id)
    candles[1] = Candle(
        instrument_id=instrument_id,
        provider="csv",
        timeframe="1m",
        open_time=candles[1].open_time,
        open=Decimal("101"),
        high=Decimal("101"),
        low=Decimal("98"),
        close=Decimal("98"),
    )
    repository = InMemoryCandleRepository()
    await repository.save_many(candles)
    engine = BacktesterEngine(
        candle_repository=repository,
        instrument=_instrument(instrument_id),
        strategy=ProtectiveStopStrategy({}),
        strategy_version_id=strategy_id,
        strategy_name="protective-stop",
        strategy_commit_sha="test-commit",
    )

    trigger_results: list[OrderResult | None] = []

    async def observe_trigger(
        broker: PaperBroker,
        instrument: UUID,
        mode: AccountMode = AccountMode.PAPER,
    ) -> OrderResult | None:
        result = await original_trigger(broker, instrument, mode)
        trigger_results.append(result)
        return result

    original_trigger = PaperBroker.check_protective_triggers
    with patch.object(PaperBroker, "check_protective_triggers", new=observe_trigger):
        result = await engine.run(_config(instrument_id, account_id, strategy_id), run_id=uuid4())

    assert len(result.trades) == 1
    assert result.trades[0].exit_price == Decimal("102")
    assert result.result.trade_count == 1
    successful_triggers = [item for item in trigger_results if item is not None and item.success]
    assert len(successful_triggers) == 1
    assert successful_triggers[0].fills[0].price == Decimal("102")


@pytest.mark.asyncio
async def test_same_input_replay_has_same_dataset_and_metrics() -> None:
    instrument_id, account_id, strategy_id = uuid4(), uuid4(), uuid4()
    repository = InMemoryCandleRepository()
    await repository.save_many(_candles(instrument_id))
    engine = BacktesterEngine(
        candle_repository=repository,
        instrument=_instrument(instrument_id),
        strategy=BuyThenCloseStrategy({}),
        strategy_version_id=strategy_id,
        strategy_name="test",
        strategy_commit_sha="test-commit",
    )
    config = _config(instrument_id, account_id, strategy_id)

    first = await engine.run(config, run_id=uuid4())
    second = await engine.run(config, run_id=uuid4())

    assert first.dataset_id == second.dataset_id
    assert first.result == second.result
    assert [
        (trade.entry_price, trade.exit_price, trade.quantity, trade.pnl)
        for trade in first.trades
    ] == [
        (trade.entry_price, trade.exit_price, trade.quantity, trade.pnl)
        for trade in second.trades
    ]
