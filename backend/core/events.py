import asyncio
import logging
from collections import defaultdict
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)

EventHandler = Callable[["DomainEvent"], Coroutine[Any, Any, None]]


@dataclass(frozen=True, slots=True)
class DomainEvent:
    id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    bot_id: UUID | None = None
    name: str = "domain_event"

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Event name is required")


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._queue: asyncio.Queue[DomainEvent] = asyncio.Queue()

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        self._handlers[event_name].append(handler)

    def unsubscribe(self, event_name: str, handler: EventHandler) -> None:
        if handler in self._handlers[event_name]:
            self._handlers[event_name].remove(handler)

    async def publish(self, event: DomainEvent) -> None:
        await self._queue.put(event)

    async def drain(self) -> None:
        while not self._queue.empty():
            event = await self._queue.get()
            handlers = self._handlers.get(event.name, [])
            for handler in handlers:
                try:
                    await handler(event)
                except Exception:
                    logger.exception(
                        "event_handler_failed event_name=%s event_id=%s",
                        event.name,
                        str(event.id),
                    )
            self._queue.task_done()

    @property
    def stats(self) -> dict[str, int]:
        return {
            "queue_size": self._queue.qsize(),
            "subscribed_events": len(self._handlers),
        }
