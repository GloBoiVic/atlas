"""FastAPI dependencies and application-service composition."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.backtester.service import BacktestService, StrategyVersionRecord
from backend.persistence.database import async_session
from backend.persistence.models import Strategy, StrategyVersion
from backend.persistence.repositories.backtest import SqlAlchemyBacktestRepository
from backend.persistence.repositories.sqlalchemy import (
    SqlAlchemyCandleRepository,
    SqlAlchemyInstrumentRepository,
)
from backend.strategy.registry import StrategyRegistry

__all__ = [
    "BacktestServiceDep",
    "get_backtest_service",
]


class SqlAlchemyStrategyVersionRepository:
    """Read active, persisted strategy identities for trusted service resolution."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get(self, strategy_version_id: UUID) -> StrategyVersionRecord | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(StrategyVersion, Strategy)
                .join(Strategy, Strategy.id == StrategyVersion.strategy_id)
                .where(
                    StrategyVersion.id == strategy_version_id,
                    Strategy.is_active.is_(True),
                )
            )
            row = result.one_or_none()
            if row is None:
                return None
            version, strategy = row
            return StrategyVersionRecord(
                id=version.id,
                name=strategy.name,
                version=strategy.version,
                commit_sha=version.commit_sha,
            )


def get_strategy_registry() -> StrategyRegistry:
    """Return the deployment-owned trusted strategy allow-list.

    Deployments may override this dependency to register their pinned strategies.  The
    empty default fails closed rather than accepting an API-supplied import path.
    """
    return StrategyRegistry()


def get_backtest_service(
    registry: Annotated[StrategyRegistry, Depends(get_strategy_registry)],
) -> BacktestService:
    """Compose a backtest service from repositories that own the session factory."""
    return BacktestService(
        candle_repository=SqlAlchemyCandleRepository(async_session),
        backtest_repository=SqlAlchemyBacktestRepository(async_session),
        instrument_repository=SqlAlchemyInstrumentRepository(async_session),
        strategy_version_repository=SqlAlchemyStrategyVersionRepository(async_session),
        strategy_registry=registry,
    )


BacktestServiceDep = Annotated[BacktestService, Depends(get_backtest_service)]
