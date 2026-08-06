"""Application service for canonical closed-trade analytics."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from backend.analytics.metrics import ClosedTrade, PerformanceMetrics, calculate_metrics

if TYPE_CHECKING:
    from datetime import datetime
    from decimal import Decimal
    from uuid import UUID

    from backend.persistence.repositories.protocols import ExecutionRepository


class AnalyticsService:
    """Read authoritative execution trades and calculate canonical analytics."""

    def __init__(self, repository: ExecutionRepository) -> None:
        self._repository = repository

    async def get_metrics(
        self,
        *,
        account_id: UUID,
        starting_equity: Decimal,
        period_start: datetime,
        period_end: datetime,
    ) -> PerformanceMetrics:
        """Return metrics for closed trades in the inclusive UTC exit-time window."""
        start_offset = period_start.utcoffset()
        if period_start.tzinfo is None or start_offset is None:
            raise ValueError("period_start must be UTC")
        if start_offset.total_seconds() != 0:
            raise ValueError("period_start must be UTC")
        end_offset = period_end.utcoffset()
        if period_end.tzinfo is None or end_offset is None:
            raise ValueError("period_end must be UTC")
        if end_offset.total_seconds() != 0:
            raise ValueError("period_end must be UTC")
        trades = await self._repository.get_closed_trades(
            account_id=account_id,
            start=period_start,
            end=period_end,
        )
        return calculate_metrics(
            starting_equity=starting_equity,
            trades=tuple(cast("tuple[ClosedTrade, ...]", tuple(trades))),
            period_start=period_start,
            period_end=period_end,
        )
