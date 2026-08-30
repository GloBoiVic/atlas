from __future__ import annotations

import asyncio
from typing import Any

import pytest

from backend.api.local_authority import (
    LocalAuthorityMiddleware,
    PeerAddressResolver,
    resolve_peer_address,
)


def _run_request(
    *,
    client: object,
    headers: list[tuple[bytes, bytes]],
    peer_address_resolver: PeerAddressResolver = resolve_peer_address,
) -> tuple[int, bytes, bool]:
    reached = False
    messages: list[dict[str, Any]] = []

    async def downstream(scope: Any, receive: Any, send: Any) -> None:
        nonlocal reached
        reached = True
        if scope["type"] == "http":
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send(
                {
                    "type": "http.response.body",
                    "body": b"routed",
                    "more_body": False,
                }
            )

    middleware = LocalAuthorityMiddleware(downstream, peer_address_resolver)
    scope = {"type": "http", "client": client, "headers": headers}

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, Any]) -> None:
        messages.append(message)

    asyncio.run(middleware(scope, receive, send))
    body = next(
        message["body"]
        for message in messages
        if message["type"] == "http.response.body"
    )
    status = next(
        message["status"]
        for message in messages
        if message["type"] == "http.response.start"
    )
    return status, body, reached


@pytest.mark.parametrize(
    "peer",
    ["127.0.0.1", "127.42.1.9", "::1", "::ffff:127.0.0.1"],
)
def test_loopback_peers_are_admitted(peer: str) -> None:
    status, _, reached = _run_request(
        client=(peer, 8000), headers=[(b"host", b"localhost:8000")]
    )
    assert status == 200
    assert reached


@pytest.mark.parametrize(
    "peer",
    [
        "10.0.0.1",
        "192.168.1.10",
        "2001:db8::1",
        "::ffff:10.0.0.1",
        "not-an-ip",
        "",
    ],
)
def test_non_loopback_or_invalid_peers_are_denied(peer: str) -> None:
    status, body, reached = _run_request(
        client=(peer, 8000), headers=[(b"host", b"localhost")]
    )
    assert status == 403
    assert b'"LOCAL_PEER_REQUIRED"' in body
    assert not reached


@pytest.mark.parametrize(
    "peer",
    [
        "::1%lo0",
        "[::1%lo0]",
        "::1%25lo0",
        "[::1%25lo0]",
    ],
)
def test_scoped_ipv6_peers_are_denied_before_routing(peer: str) -> None:
    status, body, reached = _run_request(
        client=(peer, 8000), headers=[(b"host", b"localhost")]
    )
    assert status == 403
    assert b'"LOCAL_PEER_REQUIRED"' in body
    assert not reached


@pytest.mark.parametrize("client", [None, (), (None, 8000), ("", 8000), "127.0.0.1"])
def test_missing_or_malformed_scope_client_is_denied(client: object) -> None:
    status, _, reached = _run_request(client=client, headers=[(b"host", b"localhost")])
    assert status == 403
    assert not reached


@pytest.mark.parametrize(
    "host",
    ["localhost", "localhost:3000", "127.0.0.1", "127.0.0.1:8000", "[::1]:8000"],
)
def test_local_authorities_are_admitted(host: str) -> None:
    status, _, reached = _run_request(
        client=("127.0.0.1", 8000), headers=[(b"host", host.encode())]
    )
    assert status == 200
    assert reached


@pytest.mark.parametrize(
    "host",
    ["example.com", "10.0.0.1", "[2001:db8::1]", "localhost:bad", "[::1"],
)
def test_external_or_malformed_authorities_are_denied(host: str) -> None:
    status, _, reached = _run_request(
        client=("127.0.0.1", 8000), headers=[(b"host", host.encode())]
    )
    assert status == 403
    assert not reached


@pytest.mark.parametrize("header_name", [b"host", b":authority"])
@pytest.mark.parametrize(
    "host",
    ["::1%lo0", "[::1%lo0]", "::1%25lo0", "[::1%25lo0]"],
)
def test_scoped_ipv6_authorities_are_denied_before_routing(
    header_name: bytes, host: str
) -> None:
    status, body, reached = _run_request(
        client=("127.0.0.1", 8000), headers=[(header_name, host.encode())]
    )
    assert status == 403
    assert b'"LOCAL_PEER_REQUIRED"' in body
    assert not reached


def test_authority_is_required_and_host_and_authority_must_agree() -> None:
    assert _run_request(client=("127.0.0.1", 8000), headers=[])[0] == 403
    assert (
        _run_request(
            client=("127.0.0.1", 8000),
            headers=[(b"host", b"localhost"), (b":authority", b"127.0.0.1")],
        )[0]
        == 403
    )
    assert (
        _run_request(
            client=("127.0.0.1", 8000),
            headers=[(b"host", b"[::1]"), (b":authority", b"::1")],
        )[0]
        == 200
    )


def test_forwarding_headers_cannot_change_peer_authority() -> None:
    status, _, reached = _run_request(
        client=("10.0.0.1", 8000),
        headers=[
            (b"host", b"localhost"),
            (b"forwarded", b"for=127.0.0.1"),
            (b"x-forwarded-for", b"127.0.0.1"),
            (b"x-real-ip", b"127.0.0.1"),
        ],
    )
    assert status == 403
    assert not reached


def test_forwarding_headers_are_ignored_for_a_loopback_peer() -> None:
    status, _, reached = _run_request(
        client=("127.0.0.1", 8000),
        headers=[
            (b"host", b"localhost"),
            (b"forwarded", b"for=10.0.0.1"),
            (b"x-forwarded-for", b"10.0.0.1"),
            (b"x-real-ip", b"10.0.0.1"),
        ],
    )
    assert status == 200
    assert reached


def test_peer_resolver_seam_receives_only_the_scope_client() -> None:
    seen: list[object] = []

    def resolver(client: object) -> str:
        seen.append(client)
        return "127.0.0.1"

    status, _, reached = _run_request(
        client=("testclient", 8000),
        headers=[(b"host", b"localhost")],
        peer_address_resolver=resolver,
    )
    assert status == 200
    assert reached
    assert seen == [("testclient", 8000)]


def test_lifespan_is_passed_through() -> None:
    reached = False

    async def downstream(*_: Any) -> None:
        nonlocal reached
        reached = True

    middleware = LocalAuthorityMiddleware(downstream)

    async def receive() -> dict[str, Any]:
        return {"type": "lifespan.startup"}

    async def send(_: dict[str, Any]) -> None:
        pass

    asyncio.run(middleware({"type": "lifespan"}, receive, send))
    assert reached
