from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

import backend.integrations.oanda.request as oanda_request
from backend.integrations.oanda.request import (
    OandaObservationRequester,
    validate_token,
)
from backend.integrations.oanda.source import (
    OandaAuthError,
    OandaConfigurationError,
    OandaRequestError,
)

TEST_TOKEN = "unit" + "-credential"


def requester(
    handler: httpx.MockTransport,
    *,
    token: str | None = TEST_TOKEN,
) -> OandaObservationRequester:
    secret = SecretStr(token) if token is not None else None
    return OandaObservationRequester(secret, transport=handler)


@pytest.mark.parametrize(
    ("connect", "read"),
    [(0, 20), (-1, 20), (30.01, 20), (5, 0), (5, -1), (5, 120.01)],
)
def test_constructor_rejects_timeouts_outside_frozen_bounds(
    connect: float, read: float
) -> None:
    with pytest.raises(
        OandaConfigurationError,
        match="^OANDA timeouts are outside bounded limits$",
    ):
        OandaObservationRequester(
            SecretStr(TEST_TOKEN),
            connect_timeout_seconds=connect,
            read_timeout_seconds=read,
        )


def test_constructor_accepts_timeout_boundaries() -> None:
    OandaObservationRequester(
        SecretStr(TEST_TOKEN),
        connect_timeout_seconds=30,
        read_timeout_seconds=120,
    )


@pytest.mark.parametrize("token", [None, "", " ", " \t\n "])
def test_validate_token_rejects_missing_or_blank_secret(token: str | None) -> None:
    value = SecretStr(token) if token is not None else None

    with pytest.raises(OandaConfigurationError, match="^OANDA API token is required$"):
        validate_token(value)


def test_missing_token_is_rejected_before_owned_client_creation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = 0
    real_client = httpx.Client

    def client_factory(*args: Any, **kwargs: Any) -> httpx.Client:
        nonlocal created
        created += 1
        return real_client(*args, **kwargs)

    monkeypatch.setattr(oanda_request.httpx, "Client", client_factory)

    with pytest.raises(OandaConfigurationError, match="API token is required"):
        OandaObservationRequester(None).get_json(
            "/v3/accounts/example/summary", error_subject="account"
        )

    assert created == 0


def test_get_json_performs_exact_authenticated_practice_get_without_params() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"observation": "accepted"})

    result = requester(httpx.MockTransport(handler)).get_json(
        "/v3/accounts/001-002-3-004/summary", error_subject="account"
    )

    assert result == {"observation": "accepted"}
    assert len(requests) == 1
    request = requests[0]
    assert request.method == "GET"
    assert str(request.url) == (
        "https://api-fxpractice.oanda.com/v3/accounts/001-002-3-004/summary"
    )
    assert request.url.query == b""
    assert request.headers["Authorization"] == f"Bearer {TEST_TOKEN}"
    assert request.headers["Accept-Datetime-Format"] == "RFC3339"


def test_get_json_returns_non_object_without_domain_classification() -> None:
    result = requester(
        httpx.MockTransport(lambda request: httpx.Response(200, json=["value"]))
    ).get_json("/v3/accounts/example/openTrades", error_subject="open Trades")

    assert result == ["value"]


def test_injected_client_remains_open_and_receives_per_request_timeout() -> None:
    timeout_values: list[httpx.Timeout | None] = []
    real_client = httpx.Client

    class RecordingClient(real_client):
        def get(self, *args: Any, **kwargs: Any) -> httpx.Response:
            timeout_values.append(kwargs.get("timeout"))
            return super().get(*args, **kwargs)

    injected = RecordingClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={}))
    )

    class FailingTransport(httpx.BaseTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:
            raise AssertionError("injected client must take precedence")

    try:
        OandaObservationRequester(
            SecretStr(TEST_TOKEN),
            client=injected,
            transport=FailingTransport(),
            connect_timeout_seconds=3,
            read_timeout_seconds=7,
        ).get_json("/v3/accounts/example/summary", error_subject="account")
        assert not injected.is_closed
    finally:
        injected.close()

    assert timeout_values and timeout_values[0] is not None
    timeout = timeout_values[0]
    assert timeout.read == 7
    assert timeout.connect == 3
    assert timeout.write == 3
    assert timeout.pool == 3


def test_owned_client_closes_exactly_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_client = httpx.Client
    created: list[httpx.Client] = []

    class RecordingClient(real_client):
        close_calls = 0

        def close(self) -> None:
            self.close_calls += 1
            super().close()

    def client_factory(*args: Any, **kwargs: Any) -> httpx.Client:
        client = RecordingClient(*args, **kwargs)
        created.append(client)
        return client

    monkeypatch.setattr(oanda_request.httpx, "Client", client_factory)
    OandaObservationRequester(
        SecretStr(TEST_TOKEN),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})),
    ).get_json("/v3/accounts/example/summary", error_subject="account")

    assert len(created) == 1
    assert isinstance(created[0], RecordingClient)
    assert created[0].close_calls == 1
    assert created[0].is_closed


def test_owned_client_closes_exactly_once_on_request_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_client = httpx.Client
    created: list[httpx.Client] = []

    class RecordingClient(real_client):
        close_calls = 0

        def close(self) -> None:
            self.close_calls += 1
            super().close()

    def client_factory(*args: Any, **kwargs: Any) -> httpx.Client:
        client = RecordingClient(*args, **kwargs)
        created.append(client)
        return client

    monkeypatch.setattr(oanda_request.httpx, "Client", client_factory)
    with pytest.raises(OandaAuthError):
        OandaObservationRequester(
            SecretStr(TEST_TOKEN),
            transport=httpx.MockTransport(
                lambda request: httpx.Response(403, text="provider body")
            ),
        ).get_json("/v3/accounts/example/summary", error_subject="account")

    assert len(created) == 1
    assert isinstance(created[0], RecordingClient)
    assert created[0].close_calls == 1
    assert created[0].is_closed


@pytest.mark.parametrize("status", [401, 403])
def test_auth_rejection_is_immediate_and_sanitized(status: int) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status, text=f"provider body {TEST_TOKEN}")

    with pytest.raises(OandaAuthError) as error:
        requester(httpx.MockTransport(handler)).get_json(
            "/v3/accounts/example/summary", error_subject="account"
        )

    assert calls == 1
    assert error.value.status_code == status
    assert error.value.attempts == 1
    assert str(error.value) == "OANDA authorization failed"
    assert TEST_TOKEN not in str(error.value)


@pytest.mark.parametrize("status", [400, 404])
def test_deterministic_rejection_is_immediate_and_subject_specific(status: int) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status, text=f"body {TEST_TOKEN}")

    with pytest.raises(OandaRequestError) as error:
        requester(httpx.MockTransport(handler)).get_json(
            "/v3/accounts/example/openPositions", error_subject="open Positions"
        )

    assert calls == 1
    assert error.value.status_code == status
    assert error.value.attempts == 1
    assert str(error.value) == "OANDA open Positions request was rejected"
    assert "body" not in str(error.value)
    assert TEST_TOKEN not in str(error.value)


@pytest.mark.parametrize("status", [408, 429, 503])
def test_transient_status_exhaustion_is_bounded(
    status: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status)

    monkeypatch.setattr(oanda_request, "sleep", sleeps.append)
    with pytest.raises(OandaRequestError) as error:
        requester(httpx.MockTransport(handler)).get_json(
            "/v3/accounts/example/openTrades", error_subject="open Trades"
        )

    assert calls == 3
    assert sleeps == [0.25, 0.5]
    assert error.value.status_code == status
    assert error.value.attempts == 3
    assert str(error.value) == "OANDA open Trades request failed after retries"


def test_transport_exhaustion_is_bounded_and_hides_exception_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout(f"provider timeout {TEST_TOKEN}")

    monkeypatch.setattr(oanda_request, "sleep", sleeps.append)
    with pytest.raises(OandaRequestError) as error:
        requester(httpx.MockTransport(handler)).get_json(
            "/v3/accounts/example/summary", error_subject="account"
        )

    assert calls == 3
    assert sleeps == [0.25, 0.5]
    assert error.value.status_code is None
    assert error.value.attempts == 3
    assert str(error.value) == "OANDA account request failed after retries"
    assert TEST_TOKEN not in str(error.value)


def test_transient_failure_then_success_repeats_same_get_with_fallback_sleep(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[httpx.Request] = []
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(503, headers={"Retry-After": "0"})
        return httpx.Response(200, json={"ok": True})

    monkeypatch.setattr(oanda_request, "sleep", sleeps.append)
    result = requester(httpx.MockTransport(handler)).get_json(
        "/v3/accounts/example/openTrades", error_subject="open Trades"
    )

    assert result == {"ok": True}
    assert len(requests) == 2
    assert [
        (request.method, request.url.path, request.url.query) for request in requests
    ] == [
        ("GET", "/v3/accounts/example/openTrades", b""),
        ("GET", "/v3/accounts/example/openTrades", b""),
    ]
    assert sleeps == [0.25]


@pytest.mark.parametrize(
    ("retry_after", "expected"),
    [("1.5", 1.5), ("999999999", 30.0), ("-2", 0.25), ("NaN", 0.25)],
)
def test_numeric_retry_after_is_capped_or_uses_fallback(
    retry_after: str, expected: float, monkeypatch: pytest.MonkeyPatch
) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr(oanda_request, "sleep", sleeps.append)

    with pytest.raises(OandaRequestError):
        requester(
            httpx.MockTransport(
                lambda request: httpx.Response(
                    429, headers={"Retry-After": retry_after}
                )
            )
        ).get_json("/v3/accounts/example/summary", error_subject="account")

    if retry_after in ("1.5", "999999999"):
        assert sleeps == [expected, expected]
    else:
        assert sleeps == [0.25, 0.5]


def test_retry_after_http_dates_are_future_aware_and_capped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr(oanda_request, "sleep", sleeps.append)
    retry_at = datetime.now(UTC) + timedelta(seconds=2)

    with pytest.raises(OandaRequestError):
        requester(
            httpx.MockTransport(
                lambda request: httpx.Response(
                    503,
                    headers={"Retry-After": format_datetime(retry_at, usegmt=True)},
                )
            )
        ).get_json("/v3/accounts/example/summary", error_subject="account")

    assert 0 < sleeps[0] <= 30

    sleeps.clear()
    retry_at = datetime.now(UTC) + timedelta(minutes=2)
    with pytest.raises(OandaRequestError):
        requester(
            httpx.MockTransport(
                lambda request: httpx.Response(
                    503,
                    headers={"Retry-After": format_datetime(retry_at, usegmt=True)},
                )
            )
        ).get_json("/v3/accounts/example/summary", error_subject="account")

    assert sleeps == [30.0, 30.0]


@pytest.mark.parametrize(
    "retry_after",
    [
        None,
        "malformed",
        "-1",
        "NaN",
        "inf",
        "Wed, 01 Jan 2030 00:00:00",
        "Wed, 01 Jan 2020 00:00:00 GMT",
    ],
)
def test_invalid_retry_after_values_use_fallback(
    retry_after: str | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr(oanda_request, "sleep", sleeps.append)
    headers = {} if retry_after is None else {"Retry-After": retry_after}

    with pytest.raises(OandaRequestError):
        requester(
            httpx.MockTransport(lambda request: httpx.Response(503, headers=headers))
        ).get_json("/v3/accounts/example/summary", error_subject="account")

    assert sleeps == [0.25, 0.5]


def test_invalid_json_is_not_retried_and_is_sanitized() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, text=f"invalid body {TEST_TOKEN}")

    with pytest.raises(OandaRequestError) as error:
        requester(httpx.MockTransport(handler)).get_json(
            "/v3/accounts/example/openPositions", error_subject="open Positions"
        )

    assert calls == 1
    assert error.value.status_code == 200
    assert error.value.attempts == 1
    assert str(error.value) == "OANDA returned invalid open Positions JSON"
    assert "invalid body" not in str(error.value)
    assert TEST_TOKEN not in str(error.value)


def test_other_non_success_status_is_immediate_and_sanitized() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(418, text=f"provider body {TEST_TOKEN}")

    with pytest.raises(OandaRequestError) as error:
        requester(httpx.MockTransport(handler)).get_json(
            "/v3/accounts/example/summary", error_subject="account"
        )

    assert calls == 1
    assert error.value.status_code == 418
    assert error.value.attempts == 1
    assert str(error.value) == "OANDA account request failed"
