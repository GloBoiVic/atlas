"""Backtest result repositories with SQLAlchemy and in-memory implementations."""

import asyncio
from collections.abc import Mapping
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.backtester.models import BacktestRun, BacktestTrade
from backend.persistence.backtest_conversions import (
    backtest_run_from_orm,
    backtest_run_to_orm,
    backtest_trade_from_orm,
    backtest_trade_to_orm,
)
from backend.persistence.models import BacktestRunModel, BacktestTradeModel


class InMemoryBacktestRepository:
    """Concurrency-safe, deterministic repository used by tests and local runs."""

    def __init__(
        self,
        runs: list[BacktestRun] | None = None,
        trades: list[BacktestTrade] | None = None,
    ) -> None:
        self._runs = {run.id: run for run in runs or []}
        self._trades = {trade.id: trade for trade in trades or []}
        self._lock = asyncio.Lock()

    async def create_run(self, run: BacktestRun) -> BacktestRun:
        async with self._lock:
            return self._runs.setdefault(run.id, run)

    async def update_run(self, run: BacktestRun) -> BacktestRun | None:
        async with self._lock:
            if run.id not in self._runs:
                return None
            self._runs[run.id] = run
            return run

    async def get_run(self, run_id: UUID) -> BacktestRun | None:
        async with self._lock:
            return self._runs.get(run_id)

    async def list_runs(self) -> list[BacktestRun]:
        async with self._lock:
            return sorted(self._runs.values(), key=lambda run: (run.created_at, run.id))

    async def save_trade(self, trade: BacktestTrade) -> BacktestTrade:
        async with self._lock:
            return self._trades.setdefault(trade.id, trade)

    async def get_trades(self, run_id: UUID) -> list[BacktestTrade]:
        async with self._lock:
            return sorted(
                (trade for trade in self._trades.values() if trade.backtest_run_id == run_id),
                key=lambda trade: (trade.entry_time, trade.id),
            )

    async def finalize_run(
        self, run: BacktestRun, trades: list[BacktestTrade]
    ) -> BacktestRun:
        async with self._lock:
            if run.id not in self._runs:
                raise RuntimeError("backtest run does not exist")
            self._runs[run.id] = run
            for trade in trades:
                self._trades.setdefault(trade.id, trade)
            return run


class SqlAlchemyBacktestRepository:
    """SQLAlchemy repository owning read sessions and write transactions."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    @staticmethod
    def _insert(
        model: type[BacktestRunModel] | type[BacktestTradeModel],
        values: Mapping[str, object],
        dialect: str,
    ) -> object:
        statement = sqlite_insert(model) if dialect == "sqlite" else postgres_insert(model)
        return statement.values(values).on_conflict_do_nothing(
            index_elements=[model.id]
        ).returning(model)

    @staticmethod
    def _values(row: BacktestRunModel | BacktestTradeModel) -> dict[str, object]:
        values = {column.name: getattr(row, column.name) for column in row.__table__.columns}
        if values.get("created_at") is None:
            values.pop("created_at")
        return values

    async def create_run(self, run: BacktestRun) -> BacktestRun:
        async with self._session_factory.begin() as session:
            statement = self._insert(
                BacktestRunModel,
                self._values(backtest_run_to_orm(run)),
                session.get_bind().dialect.name,
            )
            result = await session.execute(statement)  # type: ignore[call-overload]
            row = result.scalar_one_or_none()
            if row is None:
                row = await session.get(BacktestRunModel, run.id)
            if row is None:
                raise RuntimeError("backtest run insert did not produce a row")
            return backtest_run_from_orm(row)

    async def update_run(self, run: BacktestRun) -> BacktestRun | None:
        async with self._session_factory.begin() as session:
            row = await session.get(BacktestRunModel, run.id)
            if row is None:
                return None
            replacement = backtest_run_to_orm(run)
            for column in (
                "strategy_name", "strategy_version", "strategy_commit_sha", "strategy_parameters",
                "instrument_id", "symbol", "timeframe", "data_source", "dataset_id",
                "start_date", "end_date", "risk_config", "execution_config", "fill_model",
                "status", "total_return", "total_pnl", "starting_equity", "ending_equity",
                "win_rate", "sharpe_ratio", "max_drawdown", "profit_factor", "total_trades",
                "winning_trades", "losing_trades", "error_message", "last_processed_timestamp",
                "completed_at",
            ):
                setattr(row, column, getattr(replacement, column))
            await session.flush()
            return backtest_run_from_orm(row)

    async def get_run(self, run_id: UUID) -> BacktestRun | None:
        async with self._session_factory() as session:
            row = await session.get(BacktestRunModel, run_id)
            return backtest_run_from_orm(row) if row is not None else None

    async def list_runs(self) -> list[BacktestRun]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(BacktestRunModel).order_by(BacktestRunModel.created_at, BacktestRunModel.id)
            )
            return [backtest_run_from_orm(row) for row in result.scalars().all()]

    async def save_trade(self, trade: BacktestTrade) -> BacktestTrade:
        async with self._session_factory.begin() as session:
            statement = self._insert(
                BacktestTradeModel,
                self._values(backtest_trade_to_orm(trade)),
                session.get_bind().dialect.name,
            )
            result = await session.execute(statement)  # type: ignore[call-overload]
            row = result.scalar_one_or_none()
            if row is None:
                row = await session.get(BacktestTradeModel, trade.id)
            if row is None:
                raise RuntimeError("backtest trade insert did not produce a row")
            return backtest_trade_from_orm(row)

    async def get_trades(self, run_id: UUID) -> list[BacktestTrade]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(BacktestTradeModel)
                .where(BacktestTradeModel.backtest_run_id == run_id)
                .order_by(BacktestTradeModel.entry_time, BacktestTradeModel.id)
            )
            return [backtest_trade_from_orm(row) for row in result.scalars().all()]

    async def finalize_run(
        self, run: BacktestRun, trades: list[BacktestTrade]
    ) -> BacktestRun:
        """Commit the terminal run and all projected trades in one transaction."""
        async with self._session_factory.begin() as session:
            row = await session.get(BacktestRunModel, run.id)
            if row is None:
                raise RuntimeError("backtest run does not exist")
            replacement = backtest_run_to_orm(run)
            for column in (
                "dataset_id", "status", "total_return", "total_pnl", "starting_equity",
                "ending_equity",
                "win_rate", "sharpe_ratio", "max_drawdown", "profit_factor", "total_trades",
                "winning_trades", "losing_trades", "error_message", "last_processed_timestamp",
                "completed_at",
            ):
                setattr(row, column, getattr(replacement, column))
            for trade in trades:
                statement = self._insert(
                    BacktestTradeModel,
                    self._values(backtest_trade_to_orm(trade)),
                    session.get_bind().dialect.name,
                )
                await session.execute(statement)  # type: ignore[call-overload]
            await session.flush()
            return backtest_run_from_orm(row)
