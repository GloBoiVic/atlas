from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from backend.config import Settings
from backend.domain.market_data import PriceComponent, Timeframe
from backend.integrations.oanda import (
    OandaAuthError,
    OandaConfigurationError,
    OandaHistoricalBarSource,
    OandaNormalizationError,
    OandaRequestError,
)

TEST_TOKEN = "unit" + "-credential"


def moment(minute: int) -> datetime:
    return datetime(2026, 1, 5, 10, minute, tzinfo=UTC)


def candle(
    start: datetime, *, complete: bool = True, value: str = "1.1000"
) -> dict[str, Any]:
    prices = {"o": value, "h": "1.2000", "l": "1.0000", "c": "1.1500"}
    return {
        "time": start.isoformat().replace("+00:00", "Z"),
        "complete": complete,
        "volume": 4,
        "mid": prices.copy(),
        "bid": prices.copy(),
        "ask": prices.copy(),
    }


def source(
    handler: Callable[[httpx.Request], httpx.Response],
) -> OandaHistoricalBarSource:
    return OandaHistoricalBarSource(
        SecretStr(TEST_TOKEN),
        transport=httpx.MockTransport(handler),
    )


def test_exact_practice_request_and_all_components() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"candles": [candle(moment(0))]})

    result = source(handler).fetch(moment(0), moment(1))
    request = requests[0]
    assert str(request.url) == (
        "https://api-fxpractice.oanda.com/v3/instruments/EUR_USD/candles"
        "?from=2026-01-05T10%3A00%3A00Z&to=2026-01-05T10%3A01%3A00Z"
        "&price=MBA&granularity=M1&smooth=false"
    )
    assert request.headers["Authorization"] == f"Bearer {TEST_TOKEN}"
    assert request.headers["Accept-Datetime-Format"] == "RFC3339"
    assert [bar.price_component for bar in result.bars] == [
        PriceComponent.MID,
        PriceComponent.BID,
        PriceComponent.ASK,
    ]
    assert result.bars[0].open == Decimal("1.1000")


def test_native_m15_contract_requests_mid_and_aligned_complete_candles() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={"candles": [candle(moment(0)) | {"time": "2026-01-05T10:00:00Z"}]},
        )

    result = source(handler).fetch_native_m15(moment(0), moment(15))
    assert requests[0].url.params["price"] == "M"
    assert requests[0].url.params["granularity"] == "M15"
    assert requests[0].url.params["smooth"] == "false"
    assert len(result.bars) == 1
    assert result.bars[0].timeframe is Timeframe.M15
    assert result.bars[0].price_component is PriceComponent.MID


def test_native_m15_rejects_non_quarter_hour_alignment() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"candles": [candle(moment(1))]})

    with pytest.raises(OandaNormalizationError, match="quarter-hour"):
        source(handler).fetch_native_m15(moment(0), moment(15))


def test_m1_rejects_provider_timestamp_with_seconds() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"candles": [candle(moment(0)) | {"time": "2026-01-05T10:00:30Z"}]},
        )

    with pytest.raises(OandaNormalizationError, match="minute aligned"):
        source(handler).fetch_execution_m1(moment(0), moment(1))


def test_execution_m1_requests_sparse_bid_ask_without_mid() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"candles": [candle(moment(0))]})

    result = source(handler).fetch_execution_m1(moment(0), moment(1))
    assert [bar.price_component for bar in result.bars] == [
        PriceComponent.BID,
        PriceComponent.ASK,
    ]


def test_execution_m1_omits_provider_closure_boundaries_without_splitting_request() -> (
    None
):
    closure_start = datetime(2026, 1, 9, 21, 59, tzinfo=UTC)
    closure_end = datetime(2026, 1, 11, 22, 5, tzinfo=UTC)
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "candles": [
                    candle(closure_start - timedelta(minutes=1)),
                    candle(closure_start),
                    candle(closure_end - timedelta(minutes=1)),
                    candle(closure_end),
                ]
            },
        )

    result = source(handler).fetch_execution_m1(
        closure_start - timedelta(minutes=1), closure_end + timedelta(minutes=1)
    )

    assert len(requests) == 1
    assert [bar.start_time for bar in result.bars[::2]] == [
        closure_start - timedelta(minutes=1),
        closure_end,
    ]


def test_native_m15_does_not_apply_m1_closure_filter() -> None:
    closure_boundary = datetime(2026, 1, 9, 22, tzinfo=UTC)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"candles": [candle(closure_boundary)]})

    result = source(handler).fetch_native_m15(
        closure_boundary, closure_boundary + timedelta(minutes=15)
    )

    assert [bar.start_time for bar in result.bars] == [closure_boundary]


def test_paginates_at_4000_minutes_and_filters_boundaries() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        start = datetime.fromisoformat(
            request.url.params["from"].replace("Z", "+00:00")
        )
        end = datetime.fromisoformat(request.url.params["to"].replace("Z", "+00:00"))
        values = [
            candle(start + timedelta(minutes=offset))
            for offset in range(int((end - start).total_seconds() // 60))
        ]
        return httpx.Response(
            200,
            json={
                "candles": [
                    candle(start - timedelta(minutes=1)),
                    *values,
                    candle(end),
                ]
            },
        )

    result = source(handler).fetch(moment(0), moment(0) + timedelta(minutes=4001))
    assert len(requests) == 2
    assert requests[0].url.params["to"] == "2026-01-08T04:40:00Z"
    assert all(
        request.headers["Accept-Datetime-Format"] == "RFC3339" for request in requests
    )
    assert len(result.bars) == 4001 * 3


def test_native_m15_uses_sixty_thousand_minute_windows() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"candles": []})

    start = datetime(2026, 1, 1, tzinfo=UTC)
    source(handler).fetch_native_m15(start, start + timedelta(minutes=60_001))
    assert len(requests) == 2
    assert requests[0].url.params["to"] == "2026-02-11T16:00:00Z"


def test_incomplete_is_reported_and_conflicting_duplicate_fails() -> None:
    def incomplete_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"candles": [candle(moment(0), complete=False)]}
        )

    result = source(incomplete_handler).fetch(moment(0), moment(1))
    assert not result.bars
    assert result.incomplete[0].start_time == moment(0)

    def duplicate_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"candles": [candle(moment(0)), candle(moment(0), value="1.1010")]},
        )

    with pytest.raises(OandaNormalizationError, match="conflicting duplicate"):
        source(duplicate_handler).fetch(moment(0), moment(1))


def test_mixed_complete_state_is_conflicting_before_incomplete_filtering() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"candles": [candle(moment(0)), candle(moment(0), complete=False)]},
        )

    with pytest.raises(OandaNormalizationError, match="conflicting duplicate"):
        source(handler).fetch(moment(0), moment(1))


def test_identical_duplicates_collapse_and_out_of_order_is_sorted() -> None:
    first = candle(moment(1))
    second = candle(moment(0))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"candles": [first, second, first.copy()]})

    result = source(handler).fetch(moment(0), moment(2))
    assert [bar.start_time for bar in result.bars[::3]] == [moment(0), moment(1)]


def test_malformed_complete_candle_fails_without_becoming_a_bar() -> None:
    malformed = candle(moment(0))
    malformed["ask"]["o"] = "not-a-price"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"candles": [malformed]})

    with pytest.raises(OandaNormalizationError):
        source(handler).fetch(moment(0), moment(1))


def test_retry_classes_and_nonretryable_statuses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def no_sleep(seconds: float) -> None:
        pass

    monkeypatch.setattr("backend.integrations.oanda.source.sleep", no_sleep)
    calls = 0

    def retry_handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503, headers={"Retry-After": "999"})

    with pytest.raises(OandaRequestError) as error:
        source(retry_handler).fetch(moment(0), moment(1))
    assert calls == 3
    assert error.value.attempts == 3

    def forbidden_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="token should never be exposed")

    with pytest.raises(OandaAuthError) as auth_error:
        source(forbidden_handler).fetch(moment(0), moment(1))
    assert "token should never be exposed" not in str(auth_error.value)
    assert TEST_TOKEN not in str(auth_error.value)


@pytest.mark.parametrize("status", [400, 401, 404])
def test_nonretryable_statuses_are_single_attempt(status: int) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status, text="provider body with secret")

    error_type = OandaAuthError if status == 401 else OandaRequestError
    with pytest.raises(error_type) as error:
        source(handler).fetch(moment(0), moment(1))
    assert calls == 1
    assert "provider body with secret" not in str(error.value)
    assert TEST_TOKEN not in str(error.value)


@pytest.mark.parametrize(
    "failure", [httpx.ConnectError("nope"), httpx.ReadTimeout("slow")]
)
def test_connection_and_timeout_failures_retry_three_times(
    failure: httpx.RequestError,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleeps: list[float] = []
    calls = 0

    def no_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr("backend.integrations.oanda.source.sleep", no_sleep)

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise failure

    with pytest.raises(OandaRequestError) as error:
        source(handler).fetch(moment(0), moment(1))
    assert calls == 3
    assert sleeps == [0.25, 0.5]
    assert error.value.status_code is None


@pytest.mark.parametrize("retry_after", ["1.5", "NaN", "-2", "999999999"])
def test_retry_after_delta_is_finite_nonnegative_and_capped(
    retry_after: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr("backend.integrations.oanda.source.sleep", sleeps.append)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": retry_after})

    with pytest.raises(OandaRequestError):
        source(handler).fetch(moment(0), moment(1))
    assert all(0 <= value <= 30 and value == value for value in sleeps)
    if retry_after == "1.5":
        assert sleeps[0] == 1.5
    elif retry_after == "999999999":
        assert sleeps[0] == 30
    else:
        assert sleeps[0] == 0.25


def test_retry_after_http_date_and_missing_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from email.utils import format_datetime

    retry_at = datetime.now(UTC) + timedelta(seconds=2)
    sleeps: list[float] = []
    monkeypatch.setattr("backend.integrations.oanda.source.sleep", sleeps.append)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            503, headers={"Retry-After": format_datetime(retry_at, usegmt=True)}
        )

    with pytest.raises(OandaRequestError):
        OandaHistoricalBarSource(
            SecretStr(TEST_TOKEN),
            transport=httpx.MockTransport(handler),
        ).fetch(moment(0), moment(1))
    assert 0 < sleeps[0] <= 30
    with pytest.raises(OandaConfigurationError, match="API token is required"):
        OandaHistoricalBarSource(None).fetch(moment(0), moment(1))


def test_optional_configured_token_is_secret_and_respects_loaded_environment() -> None:
    import os

    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        database_url=SecretStr("postgresql+psycopg://user@localhost/atlas"),
    )
    environment_token = os.environ.get("ATLAS_OANDA_API_TOKEN")
    if environment_token is None:
        assert settings.oanda_api_token is None
    else:
        assert settings.oanda_api_token is not None
        assert environment_token not in repr(settings)
    configured = Settings(
        _env_file=None,  # type: ignore[call-arg]
        database_url=SecretStr("postgresql+psycopg://user@localhost/atlas"),
        oanda_api_token=SecretStr(TEST_TOKEN),
    )
    assert configured.oanda_api_token is not None
    assert TEST_TOKEN not in repr(configured)


def test_internal_client_disables_environment_and_injected_client_gets_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import backend.integrations.oanda.source as oanda_source

    captured: dict[str, Any] = {}
    real_client = httpx.Client

    def client_factory(*args: Any, **kwargs: Any) -> httpx.Client:
        captured.update(kwargs)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(oanda_source.httpx, "Client", client_factory)
    source(lambda request: httpx.Response(200, json={"candles": []})).fetch(
        moment(0), moment(1)
    )
    assert captured["trust_env"] is False

    timeout_values: list[httpx.Timeout | None] = []

    class RecordingClient(real_client):
        def get(self, *args: Any, **kwargs: Any) -> httpx.Response:
            timeout_values.append(kwargs.get("timeout"))
            return super().get(*args, **kwargs)

    injected = RecordingClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"candles": []})
        )
    )
    try:
        OandaHistoricalBarSource(
            SecretStr(TEST_TOKEN), client=injected, read_timeout_seconds=7
        ).fetch(moment(0), moment(1))
    finally:
        injected.close()
    assert timeout_values and timeout_values[0] is not None
    assert timeout_values[0].read == 7
