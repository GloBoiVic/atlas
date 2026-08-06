"""Authenticated operational WebSocket route."""

from fastapi import APIRouter, WebSocket

from backend.api.operational_ws import operational_websocket

router = APIRouter(tags=["operational"])


@router.websocket("/ws/operational")
async def operational_socket(websocket: WebSocket) -> None:
    """Stream scoped operational facts; this route cannot issue trading commands."""
    state = websocket.app.state
    await operational_websocket(
        websocket,
        state.operational_authenticator,
        state.operational_scope_provider,
        state.operational_snapshot_provider,
        state.operational_connection_manager,
    )
