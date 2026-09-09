from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from backend.api.local_authority import LocalAuthorityMiddleware
from backend.api.paper import create_paper_router
from backend.domain.market_data import Provider
from backend.integrations.oanda.account import OandaPracticeAccountIdentity
from backend.integrations.oanda.source import (
    OandaConfigurationError,
    OandaNormalizationError,
    OandaRequestError,
)
from backend.integrations.oanda.trades import (
    OandaPracticeOpenTrade,
    OandaPracticeOpenTradeInventory,
)


def _identity() -> OandaPracticeAccountIdentity:
    return OandaPracticeAccountIdentity(
        provider=Provider.OANDA,
        environment="PRACTICE",
        provider_account_id="001-011-5838423-001",
        alias="Research Practice",
        base_currency="USD",
    )


def _trade(
    trade_id: str = "20",
    instrument: str = "EUR_USD",
    open_time: str = "2026-01-05T08:00:00.123456Z",
    price: str = "1.16188",
    current_units: str = "1000",
    state: str = "OPEN",
    unrealized_pl: str = "12.34",
) -> OandaPracticeOpenTrade:
    return OandaPracticeOpenTrade(
        provider_trade_id=trade_id,
        provider_instrument=instrument,
        open_time=datetime.fromisoformat(open_time.replace("Z", "+00:00")).astimezone(
            UTC
        ),
        open_price=Decimal(price),
        current_units=Decimal(current_units),
        state=state,  # type: ignore[arg-type]
        unrealized_pl=Decimal(unrealized_pl),
    )


def _inventory(trades: list[OandaPracticeOpenTrade]) -> OandaPracticeOpenTradeInventory:
    return OandaPracticeOpenTradeInventory(
        identity=_identity(),
        trades=tuple(trades),
        last_transaction_id="99",
    )


class _StubService:
    def capability(self):  # pragma: no cover - not exercised here
        from types import SimpleNamespace

        return SimpleNamespace(
            to_json=lambda: {
                "provider": "OANDA",
                "environment": "PRACTICE",
                "base_currency": "USD",
                "instrument": "EUR_USD",
                "analytical_resolution": "M15",
                "analytical_price_component": "MID",
                "poll_interval_seconds": 15,
                "token_configured": True,
                "account_configured": True,
                "configured_account_id": "001-011-5838423-001",
                "available": True,
                "reason_code": None,
                "activation_required": True,
            }
        )

    def get_active(self):  # pragma: no cover
        return None


def _app(
    broker_reader: Callable[[], Any] | None, *, peer: str = "127.0.0.1"
) -> FastAPI:
    app = FastAPI()
    app.add_middleware(LocalAuthorityMiddleware, peer_address_resolver=lambda _: peer)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                    "details": {"fields": []},
                }
            },
        )

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, exc: HTTPException):
        detail = exc.detail
        content = (
            detail
            if isinstance(detail, dict) and "error" in detail
            else {
                "error": {
                    "code": f"HTTP_{exc.status_code}",
                    "message": str(detail),
                    "details": {},
                }
            }
        )
        return JSONResponse(
            status_code=exc.status_code, content=jsonable_encoder(content)
        )

    app.include_router(
        create_paper_router(service=_StubService(), broker_state_reader=broker_reader)
    )
    return app


def test_broker_state_projects_long_with_signed_units() -> None:
    trade = _trade(
        trade_id="7",
        current_units="390663",
        price="1.16188",
        unrealized_pl="410.20",
        state="OPEN",
    )
    inventory = _inventory([trade])
    with TestClient(_app(lambda: inventory), base_url="http://localhost") as client:
        resp = client.get("/api/v1/paper/broker-state")
    assert resp.status_code == 200
    data = resp.json()
    assert data["provider"] == "OANDA"
    assert data["environment"] == "PRACTICE"
    assert data["accountCurrency"] == "USD"
    assert "accountId" not in resp.text
    assert "providerAccountId" not in data
    assert len(data["openTrades"]) == 1  # type: ignore[arg-type]
    t = data["openTrades"][0]
    assert t["tradeId"] == "7"
    assert t["instrument"] == "EUR_USD"
    assert t["openPrice"] == "1.16188"
    assert t["currentUnits"] == "390663"
    assert t["state"] == "OPEN"
    assert t["unrealizedPl"] == "410.20"
    assert isinstance(t["currentUnits"], str)
    assert isinstance(t["unrealizedPl"], str)
    assert isinstance(t["openPrice"], str)


def test_broker_state_projects_short_negative_units() -> None:
    trade = _trade(
        trade_id="20",
        current_units="-390663",
        price="1.16188",
        unrealized_pl="-410.20",
        state="CLOSE_WHEN_TRADEABLE",
    )
    inventory = _inventory([trade])
    with TestClient(_app(lambda: inventory), base_url="http://localhost") as client:
        resp = client.get("/api/v1/paper/broker-state")
    assert resp.status_code == 200
    t = resp.json()["openTrades"][0]
    assert t["currentUnits"] == "-390663"
    assert t["state"] == "CLOSE_WHEN_TRADEABLE"
    assert t["unrealizedPl"] == "-410.20"


def test_broker_state_preserves_multiple_trades_distinct_and_ordered() -> None:
    trades = [
        _trade(trade_id="100", current_units="10", price="1.1", unrealized_pl="1.00"),
        _trade(trade_id="3", current_units="-20", price="1.2", unrealized_pl="-2.00"),
        _trade(trade_id="20", current_units="30", price="1.3", unrealized_pl="3.00"),
    ]
    inventory = _inventory(trades)
    with TestClient(_app(lambda: inventory), base_url="http://localhost") as client:
        resp = client.get("/api/v1/paper/broker-state")
    assert resp.status_code == 200
    ids = [t["tradeId"] for t in resp.json()["openTrades"]]
    # Inventory sorts deterministically by trade id; ensure preservation
    assert ids == ["3", "20", "100"]
    assert len(ids) == 3  # type: ignore[arg-type]
    # No netting
    units = [t["currentUnits"] for t in resp.json()["openTrades"]]  # type: ignore[arg-type]
    assert units == ["-20", "30", "10"]


def test_broker_state_empty_is_explicit_empty_list() -> None:
    inventory = _inventory([])
    with TestClient(_app(lambda: inventory), base_url="http://localhost") as client:
        resp = client.get("/api/v1/paper/broker-state")
    assert resp.status_code == 200
    assert resp.json()["openTrades"] == []
    assert resp.json()["accountCurrency"] == "USD"


def test_broker_state_unavailable_for_known_failures_and_redacts() -> None:
    secret = "super-secret-token-123"
    for exc in [
        OandaConfigurationError(f"missing {secret}"),
        OandaRequestError(503, 1, f"provider body {secret}"),
        OandaNormalizationError(f"bad {secret}"),
    ]:

        def failing(exc: Exception = exc) -> Any:
            raise exc

        with TestClient(_app(failing), base_url="http://localhost") as client:
            resp = client.get("/api/v1/paper/broker-state")
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "PAPER_BROKER_STATE_UNAVAILABLE"
        assert resp.json()["error"]["message"] == "Current broker state is unavailable."
        assert secret not in resp.text
        assert "provider body" not in resp.text.lower()


def test_broker_state_internal_error_distinct_from_runtime() -> None:
    def failing() -> Any:
        raise RuntimeError("unexpected top-secret-token")

    with TestClient(_app(failing), base_url="http://localhost") as client:
        resp = client.get("/api/v1/paper/broker-state")
    assert resp.status_code == 500
    assert resp.json()["error"]["code"] == "PAPER_BROKER_STATE_INTERNAL_ERROR"
    assert resp.json()["error"]["code"] != "PAPER_RUNTIME_INTERNAL_ERROR"
    assert "top-secret-token" not in resp.text


def test_broker_state_is_get_only() -> None:
    inventory = _inventory([])
    with TestClient(_app(lambda: inventory), base_url="http://localhost") as client:
        for method in ["post", "put", "delete", "patch"]:
            resp = getattr(client, method)("/api/v1/paper/broker-state")
            assert resp.status_code == 405, f"{method} should be 405"


def test_broker_state_invoked_per_request_and_no_account_id_exposed() -> None:
    calls: list[int] = []

    def reader() -> Any:
        calls.append(1)
        return _inventory([_trade()])

    with TestClient(_app(reader), base_url="http://localhost") as client:
        r1 = client.get("/api/v1/paper/broker-state")
        r2 = client.get("/api/v1/paper/broker-state")
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert len(calls) == 2  # type: ignore[arg-type]
    for r in (r1, r2):
        body = r.json()  # type: ignore[no-untyped-call]
        assert "providerAccountId" not in str(body)  # type: ignore[arg-type]
        assert "001-011" not in r.text
        # No raw payload keys like closingTransactionIDs
        assert "closingTransactionIDs" not in r.text
        assert "takeProfitOrder" not in r.text


def test_broker_state_decimal_strings_exact() -> None:
    trade = _trade(price="1.00000", current_units="100", unrealized_pl="0.00001")
    inv = _inventory([trade])
    with TestClient(_app(lambda: inv), base_url="http://localhost") as client:
        resp = client.get("/api/v1/paper/broker-state")
    assert resp.json()["openTrades"][0]["openPrice"] == "1.00000"
    assert resp.json()["openTrades"][0]["unrealizedPl"] == "0.00001"
