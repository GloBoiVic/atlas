"""ASGI enforcement for Atlas's local-only HTTP authority boundary."""

from __future__ import annotations

import ipaddress
from collections.abc import Callable, Iterable
from typing import cast

from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

PeerAddressResolver = Callable[[object], str | None]

_LOCAL_PEER_ERROR: dict[str, object] = {
    "error": {
        "code": "LOCAL_PEER_REQUIRED",
        "message": "Atlas API is available only from the local machine.",
        "details": {},
    }
}


def resolve_peer_address(client: object) -> str | None:
    """Return the actual ASGI client address, without consulting request headers."""

    if not isinstance(client, (tuple, list)) or not client:
        return None
    client_items = cast(tuple[object, ...] | list[object], client)
    host = client_items[0]
    return host if isinstance(host, str) and host else None


def _is_loopback_address(host: str) -> bool:
    if "%" in host:
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    if address.version == 6 and address.ipv4_mapped is not None:
        return address.ipv4_mapped.is_loopback
    return address.is_loopback


def _authority_host(value: object) -> str | None:
    """Return a canonical host for a valid HTTP authority value."""

    if isinstance(value, bytes):
        try:
            authority = value.decode("ascii")
        except UnicodeDecodeError:
            return None
    else:
        if not isinstance(value, str):
            return None
        authority = value

    if not authority or any(
        character.isspace() or ord(character) < 32 for character in authority
    ):
        return None
    if "%" in authority:
        return None

    if authority.startswith("["):
        closing = authority.find("]")
        if closing <= 1:
            return None
        host = authority[1:closing]
        suffix = authority[closing + 1 :]
        if suffix and (not suffix.startswith(":") or not _valid_port(suffix[1:])):
            return None
    else:
        if authority.count(":") == 1:
            host, port = authority.rsplit(":", 1)
            if not host or not _valid_port(port):
                return None
        else:
            host = authority

    if host.lower() == "localhost":
        return "localhost"

    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return None
    if not _is_loopback_address(host):
        return None
    return str(address)


def _valid_port(port: str) -> bool:
    if not port.isascii() or not port.isdecimal():
        return False
    try:
        return int(port) <= 65535
    except ValueError:
        return False


def _allowed_authority(headers: Iterable[tuple[bytes, bytes]]) -> bool:
    authorities: list[str] = []
    for name, value in headers:
        if name.lower() not in {b"host", b":authority"}:
            continue
        host = _authority_host(value)
        if host is None:
            return False
        authorities.append(host)
    if not authorities:
        return False
    return all(host == authorities[0] for host in authorities)


def _header_pairs(value: object) -> list[tuple[bytes, bytes]] | None:
    if not isinstance(value, list):
        return None
    headers: list[tuple[bytes, bytes]] = []
    for pair in cast(list[object], value):
        if not isinstance(pair, (tuple, list)):
            return None
        pair_items = cast(tuple[object, ...] | list[object], pair)
        if (
            len(pair_items) != 2
            or not isinstance(pair_items[0], bytes)
            or not isinstance(pair_items[1], bytes)
        ):
            return None
        headers.append((pair_items[0], pair_items[1]))
    return headers


class LocalAuthorityMiddleware:
    """Reject non-local peers/authorities before Starlette routing is reached."""

    def __init__(
        self,
        app: ASGIApp,
        peer_address_resolver: PeerAddressResolver = resolve_peer_address,
    ) -> None:
        self.app = app
        self.peer_address_resolver = peer_address_resolver

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        peer = self.peer_address_resolver(scope.get("client"))
        headers = _header_pairs(scope.get("headers"))
        admitted = (
            peer is not None
            and _is_loopback_address(peer)
            and headers is not None
            and _allowed_authority(headers)
        )
        if not admitted:
            response = JSONResponse(_LOCAL_PEER_ERROR, status_code=403)
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
