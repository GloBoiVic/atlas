from datetime import UTC, datetime
from decimal import Decimal
from typing import cast
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.websockets import WebSocket, WebSocketDisconnect

from backend.api.app import create_app
from backend.api.dashboard_schemas import (
    AccountResponse,
    AccountSummaryResponse,
    DashboardSummaryResponse,
)
from backend.api.operational_ws import (
    EventPayload,
    OperationalConnectionManager,
    OperationalEnvelope,
    OperationalMessageType,
    OperationalPrincipal,
    OperationalScope,
    SnapshotPayload,
)
from backend.config import settings
from backend.core.account_mode import AccountMode
from backend.core.events import BotStatusChanged

ACCOUNT_ID = uuid4()
MODE = AccountMode.PAPER


def snapshot() -> DashboardSummaryResponse:
    account = AccountResponse(
        id=ACCOUNT_ID,
        name="paper",
        broker="paper",
        mode=MODE.value,
        updated_at=datetime.now(UTC),
    )
    return DashboardSummaryResponse(
        account=AccountSummaryResponse(
            account=account,
            starting_equity="1000",
            realized_pnl="0",
            unrealized_pnl="0",
            equity="1000",
            as_of=datetime.now(UTC),
        ),
        positions=[],
        bots=[],
        recent_trades=[],
    )


class Authenticator:
    async def authenticate(self, websocket: object) -> OperationalPrincipal:
        return OperationalPrincipal("user@example.test", ACCOUNT_ID, frozenset({MODE}))


class WebSocketStub:
    async def send_json(self, message: object) -> None:
        return None


def test_envelope_rejects_naive_occurred_at() -> None:
    with pytest.raises(ValidationError, match="UTC"):
        OperationalEnvelope(
            message_type=OperationalMessageType.EVENT,
            event_id=uuid4(),
            occurred_at=datetime(2026, 1, 1),
            scope=OperationalScope(account_id=ACCOUNT_ID, mode=MODE),
            payload=EventPayload(event_name="BotStatusChanged"),
            sequence=1,
        )


def test_snapshot_payload_preserves_decimal_wire_strings() -> None:
    payload = SnapshotPayload(snapshot=snapshot(), sequence=0)
    assert payload.snapshot.account.starting_equity == "1000"
    assert Decimal(payload.snapshot.account.equity) == Decimal("1000")


@pytest.mark.asyncio
async def test_connection_manager_deduplicates_event_per_connection() -> None:
    manager = OperationalConnectionManager()
    connection = await manager.add(
        cast("WebSocket", WebSocketStub()), OperationalScope(account_id=ACCOUNT_ID, mode=MODE)
    )
    envelope = OperationalEnvelope(
        message_type=OperationalMessageType.EVENT,
        event_id=uuid4(),
        occurred_at=datetime.now(UTC),
        scope=OperationalScope(account_id=ACCOUNT_ID, mode=MODE),
        payload=EventPayload(event_name="TradeClosed"),
        sequence=1,
    )
    await manager.publish(envelope)
    await manager.publish(envelope)
    assert await manager.next(connection) == envelope
    assert connection.queue.empty()
    await manager.remove(connection)
    assert manager.connection_count == 0


@pytest.mark.asyncio
async def test_connection_manager_does_not_cross_account_scopes() -> None:
    manager = OperationalConnectionManager()
    first = await manager.add(
        cast("WebSocket", WebSocketStub()),
        OperationalScope(account_id=ACCOUNT_ID, mode=MODE),
    )
    other = await manager.add(
        cast("WebSocket", WebSocketStub()),
        OperationalScope(account_id=uuid4(), mode=MODE),
    )
    event = BotStatusChanged(account_id=ACCOUNT_ID, bot_id=uuid4(), mode=MODE)
    envelope = OperationalEnvelope(
        message_type=OperationalMessageType.EVENT,
        event_id=event.event_id,
        correlation_id=event.correlation_id,
        occurred_at=event.occurred_at,
        scope=OperationalScope(account_id=ACCOUNT_ID, mode=MODE, bot_id=event.bot_id),
        payload=EventPayload(event_name="BotStatusChanged", entity_id=event.bot_id),
        sequence=1,
    )
    await manager.publish(envelope)
    assert await manager.next(first) == envelope
    assert other.queue.empty()


def test_default_app_does_not_register_operational_websocket_route() -> None:
    app = create_app()
    assert not any(getattr(route, "path", None) == "/ws/operational" for route in app.routes)
    assert not hasattr(app.state, "operational_projector")


def test_deferred_websocket_route_fails_closed_without_authenticator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ENABLE_DEFERRED_OPERATIONAL_WEBSOCKET", True)
    app = create_app()
    with (
        TestClient(app) as client,
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect("/ws/operational"),
    ):
        pass


def test_deferred_websocket_sends_authoritative_snapshot_and_accepts_only_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ENABLE_DEFERRED_OPERATIONAL_WEBSOCKET", True)
    app = create_app()
    app.state.operational_authenticator = Authenticator()
    app.state.operational_scope_provider = lambda: type(
        "Scope", (), {"account_id": ACCOUNT_ID, "mode": MODE}
    )()
    app.state.operational_snapshot_provider = lambda scope: _snapshot_async()
    with TestClient(app) as client, client.websocket_connect("/ws/operational") as websocket:
        websocket.send_json(
            {"type": "subscribe", "account_id": str(ACCOUNT_ID), "mode": MODE.value}
        )
        message = websocket.receive_json()
        assert message["message_type"] == "snapshot"
        assert message["payload"]["authoritative"] is True


def test_deferred_websocket_rejects_cross_account_subscription(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ENABLE_DEFERRED_OPERATIONAL_WEBSOCKET", True)
    app = create_app()
    app.state.operational_authenticator = Authenticator()
    app.state.operational_scope_provider = lambda: type(
        "Scope", (), {"account_id": ACCOUNT_ID, "mode": MODE}
    )()
    app.state.operational_snapshot_provider = lambda scope: _snapshot_async()
    with TestClient(app) as client, client.websocket_connect("/ws/operational") as websocket:
        websocket.send_json(
            {"type": "subscribe", "account_id": str(uuid4()), "mode": MODE.value}
        )
        with pytest.raises(WebSocketDisconnect):
            websocket.receive_json()


async def _snapshot_async() -> DashboardSummaryResponse:
    return snapshot()
