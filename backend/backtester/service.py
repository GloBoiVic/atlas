"""Application orchestration for isolated backtest runs."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import structlog

from backend.backtester.engine import BacktesterEngine
from backend.backtester.models import BacktestConfig, BacktestRun, BacktestStatus
from backend.data.models import Instrument
from backend.persistence.repositories.protocols import StrategyVersionRecord

if TYPE_CHECKING:
    from backend.backtester.models import BacktestTrade
    from backend.persistence.repositories.protocols import (
        BacktestRepository,
        CandleRepository,
        InstrumentRepository,
        StrategyVersionRepository,
    )
    from backend.strategy.registry import StrategyRegistry

logger = structlog.get_logger(__name__).bind(component="BacktestService")
MAX_ERROR_LENGTH = 1000

__all__ = ["BacktestRunConflict", "BacktestService", "StrategyVersionRecord"]


class BacktestRunConflict(RuntimeError):
    """Raised when a caller attempts to reuse a non-terminal run ID."""


class BacktestService:
    """Resolve trusted inputs, execute one replay, and persist its terminal result."""

    def __init__(
        self,
        *,
        candle_repository: CandleRepository,
        backtest_repository: BacktestRepository,
        instrument_repository: InstrumentRepository,
        strategy_version_repository: StrategyVersionRepository,
        strategy_registry: StrategyRegistry,
    ) -> None:
        self._candles = candle_repository
        self._backtests = backtest_repository
        self._instruments = instrument_repository
        self._versions = strategy_version_repository
        self._registry = strategy_registry

    async def run(self, config: BacktestConfig, *, run_id: UUID | None = None) -> BacktestRun:
        """Run a validated backtest and return its persisted terminal record.

        Args:
            config: Immutable, transport-independent backtest configuration.
            run_id: Optional stable ID for idempotent callers and cancellation tests.

        Returns:
            The completed, failed, or cancelled durable run projection.

        Raises:
            BacktestRunConflict: If ``run_id`` already identifies an active run.
            asyncio.CancelledError: After cancellation has been persisted as cancelled.
            RuntimeError: If terminal status persistence fails.
        """
        replay_id = run_id or uuid4()
        existing = await self._backtests.get_run(replay_id)
        if existing is not None:
            if existing.status in {
                BacktestStatus.COMPLETED,
                BacktestStatus.FAILED,
                BacktestStatus.CANCELLED,
            }:
                return existing
            raise BacktestRunConflict(f"backtest run {replay_id} is already active")

        version = await self._versions.get(config.strategy_version_id)
        if version is None:
            raise ValueError("strategy version is not registered in persistence")
        instrument_record = await self._instruments.get(config.instrument_id)
        if instrument_record is None or not instrument_record.is_active:
            raise ValueError("instrument is missing or inactive")
        instrument = Instrument(
            id=instrument_record.id,
            symbol=instrument_record.symbol,
            provider=instrument_record.provider,
            asset_type=instrument_record.asset_type,
            base_currency=instrument_record.base_currency,
            quote_currency=instrument_record.quote_currency,
            price_precision=instrument_record.price_precision,
            quantity_precision=instrument_record.quantity_precision,
            is_active=instrument_record.is_active,
            constraints=instrument_record.constraints,
        )
        strategy = self._registry.resolve(
            version.id,
            version.name,
            version.commit_sha,
            dict(config.strategy_parameters),
        )
        created_at = datetime.now(UTC)
        run = BacktestRun(
            id=replay_id,
            strategy_name=version.name,
            strategy_version=version.version,
            strategy_commit_sha=version.commit_sha,
            strategy_parameters=dict(config.strategy_parameters),
            instrument_id=instrument.id,
            symbol=instrument.symbol,
            timeframe=config.timeframe,
            data_source=instrument.provider,
            dataset_id="pending",
            start_date=config.start_date,
            end_date=config.end_date,
            risk_config=dict(config.risk_config),
            execution_config=dict(config.execution_config),
            fill_model="next_candle_open",
            status=BacktestStatus.PENDING,
            created_at=created_at,
        )
        persisted = await self._backtests.create_run(run)
        if persisted.id != run.id:
            return persisted
        running = replace(run, status=BacktestStatus.RUNNING)
        persisted_running = await self._backtests.update_run(running)
        if persisted_running is None:
            raise RuntimeError("backtest run disappeared before execution")

        engine = BacktesterEngine(
            candle_repository=self._candles,
            instrument=instrument,
            strategy=strategy,
            strategy_version_id=version.id,
            strategy_name=version.name,
            strategy_version=version.version,
            strategy_commit_sha=version.commit_sha,
            data_source=instrument.provider,
        )
        try:
            replay = await engine.run(config, run_id=replay_id)
        except asyncio.CancelledError:
            cancelled = replace(
                running,
                status=BacktestStatus.CANCELLED,
                error_message="backtest execution was cancelled",
                completed_at=datetime.now(UTC),
            )
            await self._update_terminal(cancelled)
            raise

        except Exception as error:
            failed = replace(
                running,
                status=BacktestStatus.FAILED,
                error_message=_bounded_error(error),
                last_processed_timestamp=engine_last_timestamp(engine),
                completed_at=datetime.now(UTC),
            )
            await self._update_terminal(failed)
            return failed
        completed = replace(
            running,
            dataset_id=replay.dataset_id,
            status=BacktestStatus.COMPLETED,
            result=replay.result,
            last_processed_timestamp=replay.last_processed_timestamp,
            completed_at=datetime.now(UTC),
        )
        try:
            return await self._finalize(completed, list(replay.trades))
        except Exception as error:
            fallback = replace(
                running,
                status=BacktestStatus.FAILED,
                error_message=_bounded_error(
                    RuntimeError(f"terminal result persistence failed: {error}")
                ),
                last_processed_timestamp=completed.last_processed_timestamp,
                completed_at=datetime.now(UTC),
            )
            try:
                await self._update_terminal(fallback)
            except (Exception, asyncio.CancelledError):
                # Preserve the infrastructure error that caused finalization to fail.
                logger.exception("backtest_failure_fallback_persistence_failed", run_id=str(run.id))
            raise

    async def list_runs(self) -> list[BacktestRun]:
        """Return persisted runs in repository-defined deterministic order."""
        return await self._backtests.list_runs()

    async def get_run(self, run_id: UUID) -> BacktestRun | None:
        """Return one persisted run without exposing repository details to routes."""
        return await self._backtests.get_run(run_id)

    async def get_trades(self, run_id: UUID) -> list[BacktestTrade]:
        """Return projected trades for a persisted run."""
        return await self._backtests.get_trades(run_id)

    async def _finalize(self, run: BacktestRun, trades: list[BacktestTrade]) -> BacktestRun:
        return await self._backtests.finalize_run(run, trades)

    async def _update_terminal(self, run: BacktestRun) -> None:
        try:
            updated = await self._backtests.update_run(run)
            if updated is None:
                raise RuntimeError("backtest run disappeared during terminal update")
        except Exception:
            logger.exception("backtest_terminal_persistence_failed", run_id=str(run.id))
            raise


def _bounded_error(error: Exception) -> str:
    message = str(error).strip() or error.__class__.__name__
    return message[:MAX_ERROR_LENGTH]


def engine_last_timestamp(engine: BacktesterEngine) -> datetime | None:
    """Read progress without making the replay engine responsible for persistence."""
    # This is only a best-effort diagnostic hook for failures before the replay result exists.
    return engine.last_processed_timestamp
