"""Application service composing truthful dashboard read projections."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from backend.dashboard.models import (
    AccountSummaryRead,
    BotRead,
    DashboardSummaryRead,
    PositionRead,
    StrategyRead,
    StrategyVersionRead,
    TradeRead,
)

if TYPE_CHECKING:
    from uuid import UUID

    from backend.api.deps import AnalyticsScope
    from backend.persistence.repositories.protocols import DashboardReadRepository


class DashboardReadService:
    """Compose scoped dashboard facts from repository interfaces."""

    def __init__(self, repository: DashboardReadRepository) -> None:
        self._repository = repository

    async def get_account_summary(self, scope: AnalyticsScope) -> AccountSummaryRead:
        account = await self._repository.get_account(scope.account_id)
        if account is None:
            raise LookupError("account does not exist")
        positions = await self._repository.list_positions(
            account_id=scope.account_id, mode=scope.mode
        )
        trades = await self._repository.list_trades(
            account_id=scope.account_id, mode=scope.mode, limit=None
        )
        realized = sum(
            (trade.net_pnl for trade in trades if trade.status == "exited" and trade.net_pnl),
            Decimal("0"),
        )
        unrealized = sum((position.unrealized_pnl for position in positions), Decimal("0"))
        now = datetime.now(UTC)
        return AccountSummaryRead(
            account=account,
            starting_equity=scope.starting_equity,
            realized_pnl=realized,
            unrealized_pnl=unrealized,
            equity=scope.starting_equity + realized + unrealized,
            as_of=now,
        )

    async def get_dashboard_summary(
        self, scope: AnalyticsScope, *, trade_limit: int = 10
    ) -> DashboardSummaryRead:
        summary, positions, bots, trades = await self._read_parts(scope, trade_limit)
        return DashboardSummaryRead(summary, tuple(positions), tuple(bots), tuple(trades))

    async def list_positions(self, scope: AnalyticsScope) -> list[PositionRead]:
        return await self._repository.list_positions(account_id=scope.account_id, mode=scope.mode)

    async def list_bots(self, scope: AnalyticsScope) -> list[BotRead]:
        return await self._repository.list_bots(account_id=scope.account_id, mode=scope.mode)

    async def list_trades(self, scope: AnalyticsScope, limit: int) -> list[TradeRead]:
        return await self._repository.list_trades(
            account_id=scope.account_id, mode=scope.mode, limit=limit
        )

    async def list_strategies(self) -> list[StrategyRead]:
        return await self._repository.list_strategies()

    async def list_strategy_versions(self, strategy_id: UUID) -> list[StrategyVersionRead]:
        return await self._repository.list_strategy_versions(strategy_id)

    async def _read_parts(
        self, scope: AnalyticsScope, trade_limit: int
    ) -> tuple[AccountSummaryRead, list[PositionRead], list[BotRead], list[TradeRead]]:
        summary = await self.get_account_summary(scope)
        positions = await self.list_positions(scope)
        bots = await self.list_bots(scope)
        trades = await self.list_trades(scope, trade_limit)
        return summary, positions, bots, trades
