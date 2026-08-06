"""Project completed execution trades into the historical journal."""

from copy import deepcopy
from typing import cast

import structlog

from backend.core.events import EventBus, EventHandler, Subscription, TradeClosed
from backend.execution.models import PositionSide, Trade
from backend.journal.models import JournalDirection, JournalEntry
from backend.persistence.repositories.protocols import (
    InstrumentRepository,
    JournalRepository,
    StrategyVersionRepository,
)

logger = structlog.get_logger(__name__).bind(component="JournalService")


class JournalService:
    """Subscribe to completed trades and persist one immutable journal projection each."""

    def __init__(
        self,
        event_bus: EventBus,
        repository: JournalRepository,
        strategy_version_repository: StrategyVersionRepository,
        instrument_repository: InstrumentRepository,
    ) -> None:
        self._repository = repository
        self._strategy_versions = strategy_version_repository
        self._instruments = instrument_repository
        self._subscription: Subscription = event_bus.subscribe(
            TradeClosed,
            cast("EventHandler", self._on_trade_closed),
        )

    async def _on_trade_closed(self, event: TradeClosed) -> None:
        """Persist a TradeClosed projection, failing closed on incomplete identity."""
        trade = event.trade
        existing = await self._repository.get_by_trade_id(trade.id)
        if existing is not None:
            return

        entry = await self._project(trade)
        await self._repository.create(entry)

    async def _project(self, trade: Trade) -> JournalEntry:
        if trade.strategy_version_id is None:
            raise ValueError("closed trade is missing strategy_version_id")

        strategy_version = await self._strategy_versions.get(trade.strategy_version_id)
        if strategy_version is None or not strategy_version.name:
            raise ValueError("closed trade strategy version is missing")

        instrument_record = await self._instruments.get(trade.instrument_id)
        if instrument_record is None or not instrument_record.symbol:
            raise ValueError("closed trade instrument is missing")

        direction = (
            JournalDirection.LONG
            if trade.direction is PositionSide.LONG
            else JournalDirection.SHORT
        )
        return JournalEntry(
            account_id=trade.account_id,
            trade_id=trade.id,
            bot_id=trade.bot_id,
            strategy_version_id=trade.strategy_version_id,
            instrument_id=trade.instrument_id,
            symbol=instrument_record.symbol,
            direction=direction,
            entry_price=trade.entry_price,
            exit_price=trade.exit_price,
            quantity=trade.quantity,
            pnl=trade.net_pnl,
            strategy_name=strategy_version.name,
            signal=deepcopy(trade.signal_metadata),
            market_conditions=deepcopy(trade.market_context),
            opened_at=trade.entry_time,
            closed_at=trade.exit_time,
        )

    def unsubscribe(self) -> None:
        """Remove this service's TradeClosed subscription."""
        self._subscription.unsubscribe()

    def close(self) -> None:
        """Release the EventBus subscription during worker shutdown."""
        self.unsubscribe()


__all__ = ["JournalService"]
