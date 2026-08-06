"""Deterministic in-memory dashboard repository for service and route tests."""

from uuid import UUID

from backend.core.account_mode import AccountMode
from backend.dashboard.models import (
    AccountRead,
    BotRead,
    PositionRead,
    StrategyRead,
    StrategyVersionRead,
    TradeRead,
)


class InMemoryDashboardReadRepository:
    """Mirror the SQL read repository's scope and ordering semantics."""

    def __init__(
        self,
        *,
        accounts: list[AccountRead] | None = None,
        positions: list[PositionRead] | None = None,
        bots: list[BotRead] | None = None,
        trades: list[TradeRead] | None = None,
        strategies: list[StrategyRead] | None = None,
    ) -> None:
        self._accounts = {item.id: item for item in accounts or []}
        self._positions = positions or []
        self._bots = bots or []
        self._trades = trades or []
        self._strategies = strategies or []

    async def get_account(self, account_id: UUID) -> AccountRead | None:
        return self._accounts.get(account_id)

    async def list_positions(
        self, *, account_id: UUID, mode: AccountMode
    ) -> list[PositionRead]:
        return sorted(
            (
                item
                for item in self._positions
                if item.account_id == account_id and item.mode == mode
            ),
            key=lambda item: (item.opened_at, item.id),
        )

    async def list_bots(self, *, account_id: UUID, mode: AccountMode) -> list[BotRead]:
        return sorted(
            (
                item
                for item in self._bots
                if item.account_id == account_id
                and item.mode == mode
                and (item.desired_status != "stopped" or item.status != "stopped")
            ),
            key=lambda item: (item.updated_at, item.id),
            reverse=True,
        )

    async def list_trades(
        self, *, account_id: UUID, mode: AccountMode, limit: int | None
    ) -> list[TradeRead]:
        items = sorted(
            (item for item in self._trades if item.account_id == account_id and item.mode == mode),
            key=lambda item: (item.entry_time, item.id),
            reverse=True,
        )
        return items if limit is None else items[:limit]

    async def list_strategies(self) -> list[StrategyRead]:
        return sorted(self._strategies, key=lambda item: item.name)

    async def list_strategy_versions(self, strategy_id: UUID) -> list[StrategyVersionRead]:
        for strategy in self._strategies:
            if strategy.id == strategy_id:
                return list(strategy.versions)
        return []
