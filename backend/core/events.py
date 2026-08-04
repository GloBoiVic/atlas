from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from inspect import isawaitable
from typing import TYPE_CHECKING, Protocol
from uuid import UUID, uuid4

import structlog

from backend.core.account_mode import AccountMode

if TYPE_CHECKING:
    from backend.data.models import Candle as CandleModel
    from backend.data.models import Tick as TickModel
    from backend.execution.models import Fill, Order, Position, Trade
    from backend.strategy.contracts import Signal

logger = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """Base metadata shared by all in-process domain events."""

    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: UUID = field(default_factory=uuid4)
    account_id: UUID | None = None
    bot_id: UUID | None = None
    mode: AccountMode | None = None

    def __post_init__(self) -> None:
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() != timedelta(0):
            raise ValueError("occurred_at must be UTC")


@dataclass(frozen=True, slots=True)
class CandleClosed(DomainEvent):
    candle: "CandleModel" = field(kw_only=True)


@dataclass(frozen=True, slots=True)
class TickReceived(DomainEvent):
    tick: "TickModel" = field(kw_only=True)


@dataclass(frozen=True, slots=True)
class SignalGenerated(DomainEvent):
    signal: "Signal" = field(kw_only=True)


@dataclass(frozen=True, slots=True)
class RiskApproved(DomainEvent):
    signal: "Signal" = field(kw_only=True)
    position_size: Decimal = field(kw_only=True)
    stop_loss: Decimal = field(kw_only=True)
    take_profit: Decimal = field(kw_only=True)


@dataclass(frozen=True, slots=True)
class RiskRejected(DomainEvent):
    signal: "Signal" = field(kw_only=True)
    reason: str = field(kw_only=True)


@dataclass(frozen=True, slots=True)
class OrderSubmitted(DomainEvent):
    order: "Order" = field(kw_only=True)
    broker_order_id: str = field(kw_only=True)


@dataclass(frozen=True, slots=True)
class OrderFilled(DomainEvent):
    order: "Order" = field(kw_only=True)
    fill: "Fill" = field(kw_only=True)


@dataclass(frozen=True, slots=True)
class PositionOpened(DomainEvent):
    position: "Position" = field(kw_only=True)


@dataclass(frozen=True, slots=True)
class PositionUpdated(DomainEvent):
    position: "Position" = field(kw_only=True)


@dataclass(frozen=True, slots=True)
class PositionClosed(DomainEvent):
    position: "Position" = field(kw_only=True)


@dataclass(frozen=True, slots=True)
class TradeClosed(DomainEvent):
    trade: "Trade" = field(kw_only=True)


@dataclass(frozen=True, slots=True)
class ApiError(DomainEvent):
    pass


@dataclass(frozen=True, slots=True)
class DataFeedError(DomainEvent):
    pass


@dataclass(frozen=True, slots=True)
class OrderRejected(DomainEvent):
    order_id: UUID = field(kw_only=True)
    reason: str = field(kw_only=True)


@dataclass(frozen=True, slots=True)
class OrderFailed(DomainEvent):
    order_id: UUID = field(kw_only=True)
    error: str = field(kw_only=True)


@dataclass(frozen=True, slots=True)
class StrategyError(DomainEvent):
    error: str = field(kw_only=True)


@dataclass(frozen=True, slots=True)
class ConnectionLost(DomainEvent):
    pass


@dataclass(frozen=True, slots=True)
class ConnectionRestored(DomainEvent):
    pass


@dataclass(frozen=True, slots=True)
class CircuitBreakerOpen(DomainEvent):
    pass


@dataclass(frozen=True, slots=True)
class CircuitBreakerClosed(DomainEvent):
    pass


@dataclass(frozen=True, slots=True)
class BotStatusChanged(DomainEvent):
    pass


@dataclass(frozen=True, slots=True)
class HealthStatusChanged(DomainEvent):
    pass


@dataclass(frozen=True, slots=True)
class EventFailure:
    event: DomainEvent
    handler: str
    exception: Exception


class FailureRecorder(Protocol):
    def record(self, failure: EventFailure) -> Awaitable[None] | None:
        """Record a failed event handler."""


class InMemoryFailureRecorder:
    """Store event handler failures for inspection by the runtime and tests."""

    def __init__(self) -> None:
        self.failures: list[EventFailure] = []

    async def record(self, failure: EventFailure) -> None:
        self.failures.append(failure)


EventHandler = Callable[[DomainEvent], Awaitable[None]]
CallbackResult = Awaitable[None] | None
BotPauseCallback = Callable[[UUID], CallbackResult]


class Subscription:
    """Handle that removes one event handler registration when called."""

    def __init__(self, unsubscribe: Callable[[], None]) -> None:
        self._unsubscribe = unsubscribe
        self._active = True

    def unsubscribe(self) -> None:
        if self._active:
            self._unsubscribe()
            self._active = False

    def __call__(self) -> None:
        self.unsubscribe()


class EventBus:
    """Typed, in-process pub/sub with sequential awaited delivery."""

    def __init__(
        self,
        failure_recorder: FailureRecorder | None = None,
        pause_bot: BotPauseCallback | None = None,
    ) -> None:
        self._handlers: dict[type[DomainEvent], list[EventHandler]] = {}
        self.failure_recorder = failure_recorder or InMemoryFailureRecorder()
        self.pause_bot = pause_bot

    def subscribe(self, event_type: type[DomainEvent], handler: EventHandler) -> Subscription:
        """Register a handler for exactly ``event_type``."""
        handlers = self._handlers.setdefault(event_type, [])
        handlers.append(handler)

        def remove_handler() -> None:
            if handler in handlers:
                handlers.remove(handler)
            if not handlers:
                self._handlers.pop(event_type, None)

        return Subscription(remove_handler)

    async def publish(self, event: DomainEvent) -> None:
        """Await matching handlers in registration order, continuing after failures."""
        for handler in tuple(self._handlers.get(type(event), ())):
            try:
                await handler(event)
            except Exception as exception:
                failure = EventFailure(
                    event,
                    getattr(handler, "__qualname__", repr(handler)),
                    exception,
                )
                logger.exception(
                    "event_handler_failed",
                    event_type=type(event).__name__,
                    event_id=str(event.event_id),
                    correlation_id=str(event.correlation_id),
                    account_id=str(event.account_id) if event.account_id else None,
                    bot_id=str(event.bot_id) if event.bot_id else None,
                    mode=event.mode.value if event.mode else None,
                    handler=failure.handler,
                )
                await self._record_failure(failure)
                if event.bot_id is not None and self.pause_bot is not None:
                    await self._pause_bot(event.bot_id)

    async def _record_failure(self, failure: EventFailure) -> None:
        try:
            result = self.failure_recorder.record(failure)
            if isawaitable(result):
                await result
        except Exception:
            logger.exception(
                "event_failure_recording_failed",
                event_id=str(failure.event.event_id),
                correlation_id=str(failure.event.correlation_id),
                account_id=str(failure.event.account_id) if failure.event.account_id else None,
                bot_id=str(failure.event.bot_id) if failure.event.bot_id else None,
                handler=failure.handler,
            )

    async def _pause_bot(self, bot_id: UUID) -> None:
        try:
            result = self.pause_bot(bot_id) if self.pause_bot is not None else None
            if isawaitable(result):
                await result
        except Exception:
            logger.exception(
                "bot_pause_failed",
                bot_id=str(bot_id),
            )

    @property
    def stats(self) -> dict[str, int]:
        """Return subscription counts without exposing mutable handler state."""
        return {
            "subscribed_events": sum(bool(handlers) for handlers in self._handlers.values()),
        }
