"""Feature 09 paper-pipeline assembly around the existing trading contracts."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, cast

from backend.core.account_mode import AccountMode
from backend.core.events import EventBus, EventHandler, MarketContextUpdated, Subscription
from backend.execution.paper_broker import PaperBroker, executable_market_from_context
from backend.risk.engine import PositionInfo, PositionStatus, RiskContext
from backend.strategy.contracts import SignalDirection

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from uuid import UUID

    from backend.data.live_feed_runner import LiveFeedSession
    from backend.data.models import Instrument, MarketContext
    from backend.execution.engine import ExecutionEngine
    from backend.execution.paper_broker import ExecutableMarket
    from backend.persistence.repositories.protocols import ExecutionRepository
    from backend.risk.engine import RiskEngine
    from backend.strategy.engine import StrategyEngine


class LivePaperPipeline:
    """One bot's isolated strategy/risk/feed state over shared account execution state."""

    def __init__(
        self,
        *,
        event_bus: EventBus,
        session: LiveFeedSession,
        strategy_engine: StrategyEngine,
        risk_engine: RiskEngine,
        execution_engine: ExecutionEngine,
        broker: PaperBroker,
        repository: ExecutionRepository,
        instrument: Instrument,
        account_id: UUID,
        bot_id: UUID,
        mode: AccountMode = AccountMode.PAPER,
        mark_persistence_interval: timedelta = timedelta(seconds=5),
        stale_after: timedelta = timedelta(seconds=5),
    ) -> None:
        if mode is not AccountMode.PAPER:
            raise ValueError("LivePaperPipeline only supports paper mode")
        if mark_persistence_interval <= timedelta(0):
            raise ValueError("mark_persistence_interval must be positive")
        self._event_bus = event_bus
        self._session = session
        self._strategy = strategy_engine
        self._risk = risk_engine
        self._execution = execution_engine
        self._broker = broker
        self._repository = repository
        self._instrument = instrument
        self._account_id = account_id
        self._bot_id = bot_id
        self._mode = mode
        self._mark_interval = mark_persistence_interval
        self._stale_after = stale_after
        self._last_mark_persisted: datetime | None = None
        self._subscription: Subscription = event_bus.subscribe(
            MarketContextUpdated,
            cast("EventHandler", self._on_market_context),
        )
        self._closed = False

    @property
    def execution_enabled(self) -> bool:
        return self._execution.execution_enabled

    def set_execution_enabled(self, enabled: bool) -> None:
        self._execution.set_execution_enabled(enabled)

    async def start(self) -> None:
        """Restore durable paper state and start this bot's feed session."""
        await self._broker.restore(mode=self._mode)
        await self._session.start()

    async def stop(self) -> None:
        """Stop feed processing, persist final state, and release subscriptions."""
        if self._closed:
            return
        try:
            await self._session.stop()
            await self._persist_positions()
        finally:
            self._subscription.unsubscribe()
            self._strategy.close()
            self._risk.close()
            self._execution.close()
            self._closed = True

    async def _on_market_context(self, event: MarketContextUpdated) -> None:
        if (
            event.account_id != self._account_id
            or event.bot_id != self._bot_id
            or event.mode is not self._mode
        ):
            return
        market = executable_market_from_context(
            event.context,
            self._instrument,
            stale_after=self._stale_after,
        )
        self._broker.set_market(market)
        # The order is intentional and shared by live paper and future adapters:
        # mark, protective trigger, liquidation, then funding settlement.
        await self._broker.check_protective_triggers(self._instrument.id, self._mode)
        await self._broker.check_liquidation(self._instrument.id, self._mode)
        await self._apply_funding(event.context)
        if self._should_persist_mark(event.context.as_of):
            await self._persist_positions()

    async def _apply_funding(self, context: MarketContext) -> None:
        if context.as_of < context.next_funding_time:
            return
        position = next(
            (
                item
                for item in await self._broker.get_positions()
                if item.instrument_id == self._instrument.id and item.mode is self._mode
            ),
            None,
        )
        if position is None:
            return
        notional = context.mark_price * position.quantity
        amount = (
            -notional * context.funding_rate
            if position.side.value == "long"
            else notional * context.funding_rate
        )
        await self._broker.apply_funding(
            amount,
            instrument_id=self._instrument.id,
            mode=self._mode,
            funding_timestamp=context.next_funding_time,
            applied_at=context.as_of,
        )

    def _should_persist_mark(self, as_of: datetime) -> bool:
        if self._last_mark_persisted is None:
            self._last_mark_persisted = as_of
            return True
        if as_of - self._last_mark_persisted >= self._mark_interval:
            self._last_mark_persisted = as_of
            return True
        return False

    async def _persist_positions(self) -> None:
        positions = await self._broker.get_positions()
        for position in positions:
            await self._repository.save_position(position)


def risk_context_provider(
    broker: PaperBroker,
    instrument: Instrument,
    *,
    account_id: UUID,
    bot_id: UUID,
    mode: AccountMode,
    market: dict[UUID, ExecutableMarket],
) -> Callable[[object], Awaitable[RiskContext]]:
    """Create the pipeline-owned fresh RiskContext provider for live paper mode."""

    async def provide(_signal: object) -> RiskContext:
        current = market.get(instrument.id)
        if current is None:
            raise RuntimeError("market context is not initialized")
        account = await broker.get_account()
        positions = await broker.get_positions()
        executable = current
        return RiskContext(
            equity=account.equity,
            available_balance=account.available_balance,
            open_positions=tuple(
                PositionInfo(
                    account_id=position.account_id,
                    bot_id=position.bot_id,
                    instrument_id=position.instrument_id,
                    direction=(
                        SignalDirection.BUY
                        if position.side.value == "long"
                        else SignalDirection.SELL
                    ),
                    quantity=position.quantity,
                    status=(
                        PositionStatus.OPEN
                        if position.status.value == "open"
                        else PositionStatus.REDUCING
                    ),
                    strategy_version_id=position.strategy_version_id,
                )
                for position in positions
            ),
            entry_price=executable.mark_price,
            instrument=instrument,
            bot_id=bot_id,
            account_id=account_id,
            mode=mode,
            clock_timestamp=executable.as_of,
        )

    return provide


__all__ = ["LivePaperPipeline", "risk_context_provider"]
