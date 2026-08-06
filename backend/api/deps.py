"""FastAPI dependencies and application-service composition."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.analytics.service import AnalyticsService
from backend.backtester.service import BacktestService, StrategyVersionRecord
from backend.bot.service import BotService
from backend.config import settings
from backend.core.account_mode import AccountMode
from backend.core.clock import LiveClock
from backend.core.events import EventBus
from backend.dashboard.service import DashboardReadService
from backend.journal.service import JournalReadService
from backend.persistence.database import async_session
from backend.persistence.models import Strategy, StrategyVersion
from backend.persistence.repositories.backtest import SqlAlchemyBacktestRepository
from backend.persistence.repositories.dashboard import SqlAlchemyDashboardReadRepository
from backend.persistence.repositories.execution import SqlAlchemyExecutionRepository
from backend.persistence.repositories.journal import SqlAlchemyJournalRepository
from backend.persistence.repositories.sqlalchemy import (
    SqlAlchemyCandleRepository,
    SqlAlchemyInstrumentRepository,
    SqlAlchemySupervisorRepositories,
)
from backend.strategy.registry import StrategyRegistry
from backend.worker.protocols import ReconciliationResult, ReconciliationStatus
from backend.worker.supervisor import BotSupervisor

__all__ = [
    "AnalyticsScope",
    "AnalyticsScopeDep",
    "AnalyticsServiceDep",
    "DashboardReadServiceDep",
    "BotServiceDep",
    "get_dashboard_read_service",
    "BacktestServiceDep",
    "JournalReadServiceDep",
    "get_backtest_service",
    "get_analytics_scope",
    "get_analytics_service",
    "get_journal_read_service",
]


@dataclass(frozen=True, slots=True)
class AnalyticsScope:
    """Server-selected account and starting equity for canonical analytics."""

    account_id: UUID
    starting_equity: Decimal
    mode: AccountMode = AccountMode.PAPER


def get_analytics_scope() -> AnalyticsScope | None:
    """Return configured analytics scope, when the deployment supplies one.

    Both values must be supplied by the deployment.  An incomplete configuration remains
    unavailable rather than inventing an account or an equity baseline.
    """
    if settings.ANALYTICS_ACCOUNT_ID is None or settings.ANALYTICS_STARTING_EQUITY is None:
        return None
    return AnalyticsScope(
        account_id=settings.ANALYTICS_ACCOUNT_ID,
        starting_equity=settings.ANALYTICS_STARTING_EQUITY,
        mode=AccountMode(settings.ATLAS_ENVIRONMENT.value),
    )


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


def get_journal_read_service() -> JournalReadService:
    return JournalReadService(SqlAlchemyJournalRepository(async_session))


def get_analytics_service() -> AnalyticsService:
    return AnalyticsService(SqlAlchemyExecutionRepository(async_session))


def get_dashboard_read_service() -> DashboardReadService:
    """Compose read models over repositories that own database sessions."""
    return DashboardReadService(SqlAlchemyDashboardReadRepository(async_session))


class _UnavailablePipeline:
    execution_enabled = False

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    def set_execution_enabled(self, enabled: bool) -> None:
        return None


class _UnavailableFactory:
    def create_pipeline(self, bot: object) -> _UnavailablePipeline:
        return _UnavailablePipeline()


class _UnavailableReconciler:
    async def reconcile(self, bot: object) -> ReconciliationResult:
        return ReconciliationResult(
            status=ReconciliationStatus.FAILED,
            error="runtime pipeline is not configured",
        )


def get_bot_service(
    registry: Annotated[StrategyRegistry, Depends(get_strategy_registry)],
) -> BotService:
    """Compose the bot application service with a fail-closed default runtime.

    The worker deployment supplies the real pipeline factory and reconciler.  The API default
    intentionally cannot start orders when that runtime wiring is absent.
    """
    event_bus = EventBus()
    repositories = SqlAlchemySupervisorRepositories(async_session)
    supervisor = BotSupervisor(
        repositories=repositories,
        factory=_UnavailableFactory(),
        reconciler=_UnavailableReconciler(),
        clock=LiveClock(),
        event_bus=event_bus,
    )
    return BotService(
        event_bus=event_bus,
        supervisor=supervisor,
        repository=repositories,
        strategy_repository=SqlAlchemyStrategyVersionRepository(async_session),
        strategy_registry=registry,
        clock=LiveClock(),
    )


BacktestServiceDep = Annotated[BacktestService, Depends(get_backtest_service)]
JournalReadServiceDep = Annotated[JournalReadService, Depends(get_journal_read_service)]
AnalyticsServiceDep = Annotated[AnalyticsService, Depends(get_analytics_service)]
AnalyticsScopeDep = Annotated[AnalyticsScope | None, Depends(get_analytics_scope)]
DashboardReadServiceDep = Annotated[DashboardReadService, Depends(get_dashboard_read_service)]
BotServiceDep = Annotated[BotService, Depends(get_bot_service)]
