"""Authenticated operational WebSocket contracts and EventBus projection."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

import structlog
from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.api.dashboard_schemas import DashboardSummaryResponse  # noqa: TC001
from backend.core.account_mode import AccountMode
from backend.core.events import (
    BotStatusChanged,
    ConnectionLost,
    ConnectionRestored,
    DomainEvent,
    EventBus,
    HealthStatusChanged,
    OrderFailed,
    OrderRejected,
    OrderSubmitted,
    PositionClosed,
    PositionOpened,
    PositionUpdated,
    StrategyError,
    Subscription,
    TradeClosed,
)

logger = structlog.get_logger(__name__)

if TYPE_CHECKING:
    from backend.api.deps import AnalyticsScope

PROTOCOL_VERSION = "1"
MAX_PENDING_MESSAGES = 64


class OperationalMessageType(StrEnum):
    SNAPSHOT = "snapshot"
    EVENT = "event"
    STALE = "stale"
    DISCONNECTED = "disconnected"


class OperationalScope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    account_id: UUID
    mode: AccountMode
    bot_id: UUID | None = None


class SnapshotPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot: DashboardSummaryResponse
    sequence: int = Field(ge=0)
    authoritative: bool = True


class EventPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_name: str = Field(min_length=1)
    entity_id: UUID | None = None
    refetch_required: bool = True
    status: str | None = None
    error: str | None = None


class StatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1)
    sequence: int = Field(ge=0)


class OperationalEnvelope(BaseModel):
    """Versioned, JSON-safe envelope for operational facts."""

    model_config = ConfigDict(extra="forbid")

    protocol_version: str = PROTOCOL_VERSION
    message_type: OperationalMessageType
    event_id: UUID
    correlation_id: UUID | None = None
    occurred_at: datetime
    scope: OperationalScope
    payload: SnapshotPayload | EventPayload | StatePayload
    sequence: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_utc(self) -> OperationalEnvelope:
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() != timedelta(0):
            raise ValueError("occurred_at must be UTC")
        return self


class SubscriptionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_type: str = Field(alias="type")
    account_id: UUID
    mode: AccountMode
    bot_id: UUID | None = None
    last_sequence: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_type(self) -> SubscriptionRequest:
        if self.message_type != "subscribe":
            raise ValueError("only subscribe messages are supported")
        if self.mode == AccountMode.PRODUCTION:
            raise ValueError("production mode is not supported")
        return self


class Principal(Protocol):
    subject: str
    account_id: UUID
    modes: frozenset[AccountMode]


class Authenticator(Protocol):
    async def authenticate(self, websocket: WebSocket) -> Principal | None: ...


class ScopeProvider(Protocol):
    def __call__(self) -> AnalyticsScope | None: ...


class SnapshotProvider(Protocol):
    async def __call__(self, scope: AnalyticsScope) -> DashboardSummaryResponse: ...


@dataclass(frozen=True, slots=True)
class OperationalPrincipal:
    """Identity returned by a deployment-owned, verified auth adapter."""

    subject: str
    account_id: UUID
    modes: frozenset[AccountMode]


class DenyByDefaultAuthenticator:
    """Fail-closed placeholder until the deployment wires Cloudflare JWT verification."""

    async def authenticate(self, websocket: WebSocket) -> Principal | None:
        return None


@dataclass(slots=True)
class _Connection:
    websocket: WebSocket
    scope: OperationalScope
    queue: asyncio.Queue[OperationalEnvelope]
    seen_event_ids: set[UUID]


class OperationalConnectionManager:
    """Own scoped queues and lifecycle cleanup for operational clients."""

    def __init__(self) -> None:
        self._connections: set[int] = set()
        self._by_id: dict[int, _Connection] = {}
        self._sequence = 0
        self._lock = asyncio.Lock()

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    @property
    def sequence(self) -> int:
        return self._sequence

    async def add(self, websocket: WebSocket, scope: OperationalScope) -> _Connection:
        connection = _Connection(
            websocket, scope, asyncio.Queue(MAX_PENDING_MESSAGES), set()
        )
        key = id(websocket)
        async with self._lock:
            self._connections.add(key)
            self._by_id[key] = connection
        return connection

    async def remove(self, connection: _Connection) -> None:
        async with self._lock:
            key = id(connection.websocket)
            self._connections.discard(key)
            self._by_id.pop(key, None)

    async def disconnect(self, connection: _Connection) -> None:
        """Remove a client and notify remaining peers that the projection is stale."""
        async with self._lock:
            key = id(connection.websocket)
            self._connections.discard(key)
            self._by_id.pop(key, None)
            self._sequence += 1
            state = _state_envelope(
                OperationalMessageType.DISCONNECTED,
                connection.scope,
                self._sequence,
                "peer disconnected; REST resynchronization may be required",
            )
            for peer in tuple(self._by_id.values()):
                if _scope_matches(peer.scope, connection.scope):
                    try:
                        peer.queue.put_nowait(state)
                    except asyncio.QueueFull:
                        peer.queue.get_nowait()
                        peer.queue.put_nowait(
                            _state_envelope(
                                OperationalMessageType.STALE,
                                peer.scope,
                                self._sequence,
                                "client queue is full; REST resynchronization required",
                            )
                        )

    async def publish(self, envelope: OperationalEnvelope) -> None:
        async with self._lock:
            self._sequence = max(self._sequence, envelope.sequence)
            for connection in tuple(self._by_id.values()):
                if not _scope_matches(connection.scope, envelope.scope):
                    continue
                if envelope.event_id in connection.seen_event_ids:
                    continue
                connection.seen_event_ids.add(envelope.event_id)
                try:
                    connection.queue.put_nowait(envelope)
                except asyncio.QueueFull:
                    connection.queue.get_nowait()
                    stale = _state_envelope(
                        OperationalMessageType.STALE,
                        connection.scope,
                        self._sequence,
                        "client queue is full; REST resynchronization required",
                    )
                    connection.queue.put_nowait(stale)

    async def next(self, connection: _Connection) -> OperationalEnvelope:
        return await connection.queue.get()


class OperationalProjector:
    """Projects only UI-relevant EventBus facts into scoped notifications."""

    _EVENT_TYPES = (
        BotStatusChanged,
        ConnectionLost,
        ConnectionRestored,
        HealthStatusChanged,
        OrderFailed,
        OrderRejected,
        OrderSubmitted,
        PositionClosed,
        PositionOpened,
        PositionUpdated,
        StrategyError,
        TradeClosed,
    )

    def __init__(self, event_bus: EventBus, manager: OperationalConnectionManager) -> None:
        self._manager = manager
        self._subscriptions: list[Subscription] = [
            event_bus.subscribe(event_type, self._on_event) for event_type in self._EVENT_TYPES
        ]
        self._sequence = 0

    async def close(self) -> None:
        for subscription in self._subscriptions:
            subscription.unsubscribe()
        self._subscriptions.clear()

    async def _on_event(self, event: DomainEvent) -> None:
        if event.account_id is None or event.mode is None:
            return
        self._sequence += 1
        scope = OperationalScope(account_id=event.account_id, mode=event.mode, bot_id=event.bot_id)
        payload = EventPayload(
            event_name=type(event).__name__,
            entity_id=_entity_id(event),
            error=getattr(event, "error", None),
            status=getattr(event, "status", None),
        )
        envelope = OperationalEnvelope(
            message_type=OperationalMessageType.EVENT,
            event_id=event.event_id,
            correlation_id=event.correlation_id,
            occurred_at=event.occurred_at,
            scope=scope,
            payload=payload,
            sequence=self._sequence,
        )
        await self._manager.publish(envelope)


async def operational_websocket(
    websocket: WebSocket,
    authenticator: Authenticator,
    scope_provider: ScopeProvider,
    snapshot_provider: SnapshotProvider,
    manager: OperationalConnectionManager,
) -> None:
    """Run one authenticated, read-only operational WebSocket session."""
    principal = await authenticator.authenticate(websocket)
    if principal is None:
        await websocket.close(code=1008, reason="authenticated identity unavailable")
        return
    await websocket.accept()
    try:
        requested = SubscriptionRequest.model_validate(await websocket.receive_json())
    except (ValueError, TypeError):
        await websocket.close(code=1008, reason="invalid subscription message")
        return
    scope = scope_provider()
    if scope is None or not _scope_matches_authority(scope, requested, principal):
        await websocket.close(code=1008, reason="unsupported subscription scope")
        return
    try:
        snapshot = await snapshot_provider(scope)
    except Exception:
        logger.exception("operational_snapshot_failed", subject=principal.subject)
        await websocket.close(code=1011, reason="authoritative snapshot unavailable")
        return
    if requested.bot_id is not None and not any(
        bot.id == requested.bot_id for bot in snapshot.bots
    ):
        await websocket.close(code=1008, reason="unsupported bot scope")
        return
    requested_scope = OperationalScope(
        account_id=requested.account_id, mode=requested.mode, bot_id=requested.bot_id
    )
    connection = await manager.add(websocket, requested_scope)
    sender = asyncio.create_task(_send_loop(manager, connection))
    try:
        snapshot = _filter_snapshot(snapshot, requested.bot_id)
        snapshot_envelope = OperationalEnvelope(
            message_type=OperationalMessageType.SNAPSHOT,
            event_id=UUID(int=0),
            occurred_at=datetime.now(UTC),
            scope=requested_scope,
            payload=SnapshotPayload(snapshot=snapshot, sequence=manager.sequence),
            sequence=manager.sequence,
        )
        connection.queue.put_nowait(snapshot_envelope)
        while True:
            message = await websocket.receive_json()
            request = SubscriptionRequest.model_validate(message)
            if not _scope_matches_authority(scope, request, principal):
                await websocket.close(code=1008, reason="unsupported subscription scope")
                return
    except WebSocketDisconnect:
        return
    except (ValueError, TypeError):
        await websocket.close(code=1008, reason="invalid subscription message")
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("operational_websocket_failed", subject=principal.subject)
        await websocket.close(code=1011, reason="operational stream failure")
    finally:
        sender.cancel()
        with suppress(asyncio.CancelledError):
            await sender
        await manager.disconnect(connection)


async def _send_loop(manager: OperationalConnectionManager, connection: _Connection) -> None:
    try:
        while True:
            envelope = await manager.next(connection)
            await connection.websocket.send_json(envelope.model_dump(mode="json"))
    except asyncio.CancelledError:
        raise


def _scope_matches(left: OperationalScope, right: OperationalScope) -> bool:
    return (
        left.account_id == right.account_id
        and left.mode == right.mode
        and (right.bot_id is None or left.bot_id is None or left.bot_id == right.bot_id)
    )


def _filter_snapshot(
    snapshot: DashboardSummaryResponse, bot_id: UUID | None
) -> DashboardSummaryResponse:
    if bot_id is None:
        return snapshot
    return snapshot.model_copy(
        update={
            "positions": [item for item in snapshot.positions if item.bot_id == bot_id],
            "bots": [item for item in snapshot.bots if item.id == bot_id],
            "recent_trades": [item for item in snapshot.recent_trades if item.bot_id == bot_id],
        }
    )


def _scope_matches_authority(
    scope: object, request: SubscriptionRequest, principal: Principal
) -> bool:
    account_id = getattr(scope, "account_id", None)
    mode = getattr(scope, "mode", None)
    return (
        request.account_id == account_id == principal.account_id
        and request.mode == mode
        and request.mode in principal.modes
        and request.mode != AccountMode.PRODUCTION
    )


def _entity_id(event: DomainEvent) -> UUID | None:
    for name in ("order", "position", "trade"):
        value = getattr(event, name, None)
        if value is not None:
            return getattr(value, "id", None)
    return getattr(event, "order_id", None)


def _state_envelope(
    message_type: OperationalMessageType,
    scope: OperationalScope,
    sequence: int,
    reason: str,
) -> OperationalEnvelope:
    return OperationalEnvelope(
        message_type=message_type,
        event_id=UUID(int=0),
        occurred_at=datetime.now(UTC),
        scope=scope,
        payload=StatePayload(reason=reason, sequence=sequence),
        sequence=sequence,
    )
