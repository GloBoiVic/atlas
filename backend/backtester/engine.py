"""Isolated deterministic historical replay for Feature 05."""

from __future__ import annotations

import asyncio
import copy
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID, uuid4

from backend.backtester.metrics import calculate_metrics, project_trade
from backend.backtester.replay_helpers import raise_event_failures, risk_position
from backend.config import RiskConfig
from backend.core.account_mode import AccountMode
from backend.core.clock import SimulationClock
from backend.core.events import (
    CandleClosed,
    EventBus,
    EventHandler,
    InMemoryFailureRecorder,
    TradeClosed,
)
from backend.data.loader import build_dataset_identity
from backend.execution.engine import ExecutionEngine
from backend.execution.paper_broker import ExecutableMarket, PaperBroker, PaperFillMode
from backend.persistence.repositories.memory import InMemoryExecutionRepository
from backend.risk.engine import RiskContext, RiskEngine
from backend.strategy.contracts import DataType
from backend.strategy.engine import StrategyEngine

if TYPE_CHECKING:
    from datetime import datetime

    from backend.backtester.models import BacktestConfig, BacktestResult, BacktestTrade
    from backend.data.models import Candle, Instrument
    from backend.execution.models import Trade
    from backend.persistence.repositories.protocols import CandleRepository
    from backend.strategy.base import Strategy


@dataclass(frozen=True, slots=True)
class BacktestReplayResult:
    """Ephemeral output of one isolated replay."""

    run_id: UUID
    dataset_id: str
    trades: tuple[BacktestTrade, ...]
    result: BacktestResult
    last_processed_timestamp: datetime | None


class BacktesterEngine:
    """Replay candles through the shared strategy, risk, and paper execution contracts."""

    def __init__(
        self,
        *,
        candle_repository: CandleRepository,
        instrument: Instrument,
        strategy: Strategy,
        strategy_version_id: UUID,
        strategy_name: str,
        strategy_version: str = "",
        strategy_commit_sha: str = "",
        data_source: str | None = None,
    ) -> None:
        self.candle_repository = candle_repository
        self.instrument = instrument
        self.strategy = strategy
        self.strategy_version_id = strategy_version_id
        self.strategy_name = strategy_name
        self.strategy_version = strategy_version
        self.strategy_commit_sha = strategy_commit_sha
        self.data_source = data_source or instrument.provider
        self.last_run_event_bus: EventBus | None = None
        self.last_execution_repository: InMemoryExecutionRepository | None = None
        self.last_processed_timestamp: datetime | None = None

    async def run(
        self, config: BacktestConfig, *, run_id: UUID | None = None
    ) -> BacktestReplayResult:
        """Run one replay, releasing every run-local subscription on every exit path.

        Args:
            config: Validated immutable backtest configuration.
            run_id: Optional stable correlation identity for deterministic callers.

        Returns:
            Closed-trade projections and canonical run metrics.

        Raises:
            asyncio.CancelledError: If the caller cancels the replay.
            ValueError: If the loaded dataset cannot be replayed safely.
            RuntimeError: If a trading-critical event handler fails.
        """
        replay_id = run_id or uuid4()
        if config.instrument_id != self.instrument.id:
            raise ValueError("backtest instrument does not match the resolved instrument")
        if config.strategy_version_id != self.strategy_version_id:
            raise ValueError("backtest strategy version does not match the resolved strategy")
        candles = await self.candle_repository.get_candles(
            instrument_id=config.instrument_id,
            timeframe=config.timeframe,
            start=config.start_date,
            end=config.end_date,
            price_basis="trade",
        )
        self._validate_candles(candles, config, self.instrument.provider)
        if not candles:
            raise ValueError("backtest dataset is empty")
        dataset_id = build_dataset_identity(
            instrument_id=config.instrument_id,
            timeframe=config.timeframe,
            start=config.start_date,
            end=config.end_date,
            source=self.data_source,
            candles=candles,
        ).id

        failure_recorder = InMemoryFailureRecorder()
        event_bus = EventBus(failure_recorder=failure_recorder)
        clock = SimulationClock(candles[0].open_time)
        execution_repository = InMemoryExecutionRepository()
        broker = PaperBroker(
            account_id=config.account_id,
            initial_balance=config.initial_balance,
            fee_rate=_decimal_config(config.execution_config, "fee_rate", "0.0005"),
            slippage_rate=_decimal_config(config.execution_config, "slippage_rate", "0.0005"),
            maintenance_margin_rate=_decimal_config(
                config.execution_config, "maintenance_margin_rate", "0.005"
            ),
            leverage=_decimal_config(config.execution_config, "leverage", "1"),
            fill_mode=PaperFillMode.BACKTEST,
            clock=clock.now,
        )
        bot_id = replay_id
        strategy_engine: StrategyEngine | None = None
        risk_engine: RiskEngine | None = None
        execution_engine: ExecutionEngine | None = None
        collector_subscription = None
        closed_trades: list[Trade] = []
        last_processed: datetime | None = None
        self.last_processed_timestamp = None
        try:
            strategy = copy.deepcopy(self.strategy)
            current_market: ExecutableMarket | None = None
            data_requirement = strategy.required_data()
            strategy_engine = StrategyEngine(
                event_bus,
                bot_id,
                config.account_id,
                config.instrument_id,
                strategy,
                self.strategy_version_id,
                self.strategy_name,
                self.strategy_commit_sha,
                data_requirement,
            )
            if data_requirement.data_type is not DataType.CANDLE:
                raise ValueError("backtest strategy must require candle data")
            if data_requirement.timeframe != config.timeframe:
                raise ValueError("strategy timeframe does not match backtest timeframe")

            async def context_provider(signal: Any) -> RiskContext:
                if current_market is None:
                    raise RuntimeError("market context is not initialized")
                account = await broker.get_account()
                positions = await broker.get_positions()
                return RiskContext(
                    equity=account.equity,
                    available_balance=account.available_balance,
                    open_positions=tuple(risk_position(position) for position in positions),
                    entry_price=current_market.mark_price,
                    instrument=self.instrument,
                    bot_id=bot_id,
                    account_id=config.account_id,
                    mode=AccountMode.PAPER,
                    clock_timestamp=clock.now(),
                )

            risk_engine = RiskEngine(
                event_bus,
                bot_id,
                config.account_id,
                AccountMode.PAPER,
                RiskConfig.model_validate(dict(config.risk_config)),
                context_provider,
            )
            execution_engine = ExecutionEngine(
                event_bus, broker, execution_repository, bot_id=bot_id
            )

            async def collect(event: TradeClosed) -> None:
                closed_trades.append(event.trade)

            collector_subscription = event_bus.subscribe(
                TradeClosed, cast("EventHandler", collect)
            )
            warmup_count = data_requirement.warmup_candles
            if warmup_count > len(candles):
                raise ValueError("strategy warm-up exceeds loaded dataset")
            await strategy_engine.warm_up(candles[:warmup_count])

            for index in range(warmup_count, len(candles)):
                candle = candles[index]
                last_processed = candle.open_time
                self.last_processed_timestamp = last_processed
                clock.advance(candle.open_time)
                is_final = index == len(candles) - 1
                if is_final:
                    # The final candle completes strategy state but has no executable next open.
                    risk_engine.close()
                    execution_engine.close()
                current_market = ExecutableMarket(
                    instrument_id=config.instrument_id,
                    bid=candle.close,
                    ask=candle.close,
                    mark_price=candle.close,
                    as_of=clock.now(),
                    next_candle_open=None if is_final else candles[index + 1].open,
                )
                broker.set_market(current_market)
                await event_bus.publish(
                    CandleClosed(
                        candle=candle,
                        account_id=config.account_id,
                        bot_id=bot_id,
                        mode=AccountMode.PAPER,
                        occurred_at=clock.now(),
                        correlation_id=replay_id,
                    )
                )
                raise_event_failures(failure_recorder)
                if not is_final:
                    await broker.check_protective_triggers(config.instrument_id)
                    await broker.check_liquidation(config.instrument_id)
                    closed_trades.extend(broker.consume_protective_trades())
                    raise_event_failures(failure_recorder)

            projected = tuple(
                project_trade(replay_id, self.instrument, trade) for trade in closed_trades
            )
            metrics = calculate_metrics(config.initial_balance, projected)
            return BacktestReplayResult(replay_id, dataset_id, projected, metrics, last_processed)
        except asyncio.CancelledError:
            raise
        finally:
            if collector_subscription is not None:
                collector_subscription.unsubscribe()
            if execution_engine is not None:
                execution_engine.close()
            if risk_engine is not None:
                risk_engine.close()
            if strategy_engine is not None:
                strategy_engine.close()
            self.last_run_event_bus = event_bus
            self.last_execution_repository = execution_repository

    @staticmethod
    def _validate_candles(
        candles: list[Candle], config: BacktestConfig, expected_provider: str
    ) -> None:
        previous: tuple[UUID, str, str, datetime, str] | None = None
        for candle in candles:
            if not candle.is_complete:
                raise ValueError("backtest dataset contains an incomplete candle")
            if candle.instrument_id != config.instrument_id or candle.timeframe != config.timeframe:
                raise ValueError("backtest dataset identity does not match configuration")
            if candle.provider != expected_provider:
                raise ValueError("backtest candle provider does not match instrument identity")
            key = (
                candle.instrument_id,
                candle.provider,
                candle.timeframe,
                candle.open_time,
                candle.price_basis,
            )
            if previous is not None and key <= previous:
                raise ValueError("backtest candles must be strictly chronological and unique")
            previous = key


def _decimal_config(config: dict[str, object], name: str, default: str) -> Decimal:
    value = config.get(name, Decimal(default))
    if not isinstance(value, Decimal):
        raise TypeError(f"execution_config.{name} must be a Decimal")
    return value
