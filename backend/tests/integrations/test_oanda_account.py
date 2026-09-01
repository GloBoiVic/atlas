from collections.abc import Callable
from dataclasses import FrozenInstanceError, fields
from decimal import Decimal
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from backend.config import Settings
from backend.domain.market_data import Provider
from backend.integrations.oanda import (
    OandaAccountNormalizationError,
    OandaAuthError,
    OandaConfigurationError,
    OandaPracticeAccountIdentity,
    OandaPracticeAccountSummarySnapshot,
    OandaPracticeAccountValidator,
    OandaRequestError,
    bind_oanda_practice_account,
    read_oanda_practice_account_summary,
)

TEST_TOKEN = "unit" + "-credential"
ACCOUNT_ID = "001-011-5838423-001"


def account_payload(
    *,
    account_id: str = ACCOUNT_ID,
    currency: str = "USD",
    alias: str | None = "Research Practice",
) -> dict[str, Any]:
    account: dict[str, Any] = {
        "id": account_id,
        "currency": currency,
        "balance": "100000.00",
        "NAV": "100000.00",
        "unrealizedPL": "0.00",
        "marginUsed": "0.00",
        "marginAvailable": "100000.00",
        "openTradeCount": 0,
        "openPositionCount": 0,
        "pendingOrderCount": 0,
        "orders": [{"id": "must-not-leak"}],
        "trades": [{"id": "must-not-leak"}],
        "positions": [{"instrument": "EUR_USD"}],
        "lastTransactionID": "42",
    }
    if alias is not None:
        account["alias"] = alias
    return {"account": account, "lastTransactionID": "42"}


def validator(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    account_id: str | None = ACCOUNT_ID,
) -> OandaPracticeAccountValidator:
    return OandaPracticeAccountValidator(
        SecretStr(TEST_TOKEN),
        account_id,
        transport=httpx.MockTransport(handler),
    )


def test_requests_only_configured_practice_summary_and_normalizes_five_fields() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=account_payload())

    identity = validator(handler).validate()

    assert len(requests) == 1
    request = requests[0]
    assert request.method == "GET"
    assert str(request.url) == (
        "https://api-fxpractice.oanda.com/v3/accounts/001-011-5838423-001/summary"
    )
    assert request.headers["Authorization"] == f"Bearer {TEST_TOKEN}"
    assert request.headers["Accept-Datetime-Format"] == "RFC3339"
    assert identity == OandaPracticeAccountIdentity(
        provider=Provider.OANDA,
        environment="PRACTICE",
        provider_account_id=ACCOUNT_ID,
        alias="Research Practice",
        base_currency="USD",
    )
    assert {field.name for field in fields(identity)} == {
        "provider",
        "environment",
        "provider_account_id",
        "alias",
        "base_currency",
    }
    assert not hasattr(identity, "balance")
    assert not hasattr(identity, "last_transaction_id")


def test_missing_alias_normalizes_to_none_and_list_selection_is_impossible() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.url.path == f"/v3/accounts/{ACCOUNT_ID}/summary"
        assert request.url.path != "/v3/accounts"
        return httpx.Response(200, json=account_payload(alias=None))

    identity = validator(handler).validate()
    assert identity.alias is None
    assert len(requests) == 1


def test_read_summary_normalizes_one_response_to_immutable_selected_snapshot() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=account_payload())

    snapshot = validator(handler).read_summary()

    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert requests[0].url.path == f"/v3/accounts/{ACCOUNT_ID}/summary"
    assert requests[0].headers["Authorization"] == f"Bearer {TEST_TOKEN}"
    assert requests[0].headers["Accept-Datetime-Format"] == "RFC3339"
    assert snapshot == OandaPracticeAccountSummarySnapshot(
        identity=OandaPracticeAccountIdentity(
            provider=Provider.OANDA,
            environment="PRACTICE",
            provider_account_id=ACCOUNT_ID,
            alias="Research Practice",
            base_currency="USD",
        ),
        balance=Decimal("100000.00"),
        nav=Decimal("100000.00"),
        unrealized_pl=Decimal("0.00"),
        margin_used=Decimal("0.00"),
        margin_available=Decimal("100000.00"),
        open_trade_count=0,
        open_position_count=0,
        pending_order_count=0,
        last_transaction_id="42",
    )
    assert {field.name for field in fields(snapshot)} == {
        "identity",
        "balance",
        "nav",
        "unrealized_pl",
        "margin_used",
        "margin_available",
        "open_trade_count",
        "open_position_count",
        "pending_order_count",
        "last_transaction_id",
    }
    assert not hasattr(snapshot, "orders")
    assert not hasattr(snapshot, "trades")
    assert not hasattr(snapshot, "positions")
    assert not hasattr(snapshot, "account")
    with pytest.raises(FrozenInstanceError):
        snapshot.__setattr__("balance", Decimal("0"))


def test_read_summary_accepts_finite_adverse_facts_and_nonzero_counts() -> None:
    payload = account_payload()
    payload["account"].update(
        {
            "balance": "-1.25",
            "NAV": "-0.50",
            "unrealizedPL": "-10.75",
            "marginUsed": "5.00",
            "marginAvailable": "0",
            "openTradeCount": 1,
            "openPositionCount": 2,
            "pendingOrderCount": 3,
        }
    )

    snapshot = validator(
        lambda request: httpx.Response(200, json=payload)
    ).read_summary()

    assert snapshot.balance == Decimal("-1.25")
    assert snapshot.nav == Decimal("-0.50")
    assert snapshot.unrealized_pl == Decimal("-10.75")
    assert snapshot.margin_used == Decimal("5.00")
    assert snapshot.margin_available == Decimal("0")
    assert snapshot.open_trade_count == 1
    assert snapshot.open_position_count == 2
    assert snapshot.pending_order_count == 3


def test_read_summary_helper_uses_explicit_settings_and_one_request() -> None:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        database_url="postgresql+psycopg://user@localhost/atlas",
        oanda_api_token=SecretStr(TEST_TOKEN),
        oanda_account_id=ACCOUNT_ID,
    )
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=account_payload())

    snapshot = read_oanda_practice_account_summary(
        settings, transport=httpx.MockTransport(handler)
    )

    assert snapshot.identity.provider_account_id == ACCOUNT_ID
    assert len(requests) == 1


def test_settings_factory_uses_account_and_existing_timeouts() -> None:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        database_url="postgresql+psycopg://user@localhost/atlas",
        oanda_api_token=SecretStr(TEST_TOKEN),
        oanda_account_id=ACCOUNT_ID,
        oanda_connect_timeout_seconds=2,
        oanda_read_timeout_seconds=7,
    )
    identity = bind_oanda_practice_account(
        settings,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=account_payload())
        ),
    )
    assert identity.provider_account_id == ACCOUNT_ID


@pytest.mark.parametrize(
    "account_id",
    [None, "", "001-011-5838423", "001-011-5838423-001/other"],
)
def test_missing_or_malformed_account_selection_fails_without_network(
    account_id: str | None,
) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=account_payload())

    with pytest.raises(OandaConfigurationError, match="account ID"):
        validator(handler, account_id=account_id).validate()
    assert calls == 0


def test_missing_or_blank_token_fails_without_network() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=account_payload())

    account_validator = OandaPracticeAccountValidator(
        SecretStr(" "),
        ACCOUNT_ID,
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(OandaConfigurationError, match="API token is required"):
        account_validator.validate()
    assert calls == 0


def test_deterministic_rejection_is_sanitized_and_not_retried() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(403, text=f"provider body {TEST_TOKEN}")

    with pytest.raises(OandaAuthError) as error:
        validator(handler).validate()
    assert error.value.status_code == 403
    assert error.value.attempts == 1
    assert calls == 1
    assert TEST_TOKEN not in str(error.value)
    assert "provider body" not in str(error.value)


def test_transient_provider_failure_is_bounded_and_sanitized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503, headers={"Retry-After": "999"})

    monkeypatch.setattr("backend.integrations.oanda.account.sleep", sleeps.append)
    with pytest.raises(OandaRequestError) as error:
        validator(handler).validate()
    assert calls == 3
    assert sleeps == [30.0, 30.0]
    assert error.value.status_code == 503
    assert error.value.attempts == 3


def test_transport_failure_is_bounded_and_has_no_provider_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout(f"slow {TEST_TOKEN}")

    monkeypatch.setattr("backend.integrations.oanda.account.sleep", sleeps.append)
    with pytest.raises(OandaRequestError) as error:
        validator(handler).validate()
    assert calls == 3
    assert sleeps == [0.25, 0.5]
    assert error.value.status_code is None
    assert TEST_TOKEN not in str(error.value)


def test_summary_retry_repeats_only_the_same_safe_get(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, headers={"Retry-After": "0"})
        return httpx.Response(200, json=account_payload())

    monkeypatch.setattr("backend.integrations.oanda.account.sleep", sleeps.append)
    snapshot = validator(handler).read_summary()

    assert snapshot.last_transaction_id == "42"
    assert calls == 2
    assert sleeps == [0.25]


@pytest.mark.parametrize(
    "payload",
    [
        {"account": {"id": ACCOUNT_ID}},
        {"account": {"currency": "USD"}},
        {"account": []},
        {},
    ],
)
def test_malformed_account_response_fails_closed(
    payload: dict[str, Any],
) -> None:
    with pytest.raises(OandaAccountNormalizationError):
        validator(lambda request: httpx.Response(200, json=payload)).validate()


def test_invalid_json_fails_closed_without_exposing_body() -> None:
    body = f"invalid response {TEST_TOKEN}"
    with pytest.raises(OandaRequestError) as error:
        validator(lambda request: httpx.Response(200, text=body)).validate()
    assert "invalid account JSON" in str(error.value)
    assert body not in str(error.value)
    assert TEST_TOKEN not in str(error.value)


@pytest.mark.parametrize(
    ("account_id", "currency"),
    [("001-011-5838423-002", "USD"), (ACCOUNT_ID, "EUR")],
)
def test_mismatched_account_and_non_usd_currency_fail_closed(
    account_id: str,
    currency: str,
) -> None:
    with pytest.raises(OandaAccountNormalizationError):
        validator(
            lambda request: httpx.Response(
                200,
                json=account_payload(account_id=account_id, currency=currency),
            )
        ).validate()


def test_malformed_optional_alias_fails_closed() -> None:
    payload = account_payload()
    payload["account"]["alias"] = {"unexpected": "object"}
    with pytest.raises(OandaAccountNormalizationError, match="alias"):
        validator(lambda request: httpx.Response(200, json=payload)).validate()


@pytest.mark.parametrize(
    "field,value",
    [
        ("balance", None),
        ("NAV", "not-a-decimal"),
        ("unrealizedPL", "NaN"),
        ("marginUsed", "Infinity"),
        ("marginAvailable", "-Infinity"),
    ],
)
def test_invalid_summary_financial_values_fail_closed(field: str, value: Any) -> None:
    payload = account_payload()
    payload["account"][field] = value

    with pytest.raises(OandaAccountNormalizationError, match=field):
        validator(lambda request: httpx.Response(200, json=payload)).read_summary()


@pytest.mark.parametrize(
    "field",
    ["balance", "NAV", "unrealizedPL", "marginUsed", "marginAvailable"],
)
def test_missing_summary_financial_values_fail_closed(field: str) -> None:
    payload = account_payload()
    payload["account"].pop(field)

    with pytest.raises(OandaAccountNormalizationError, match=field):
        validator(lambda request: httpx.Response(200, json=payload)).read_summary()


@pytest.mark.parametrize(
    "field,value",
    [
        ("openTradeCount", True),
        ("openPositionCount", "1"),
        ("pendingOrderCount", 1.0),
        ("openTradeCount", None),
        ("openPositionCount", -1),
    ],
)
def test_invalid_summary_counts_fail_closed(field: str, value: Any) -> None:
    payload = account_payload()
    payload["account"][field] = value

    with pytest.raises(OandaAccountNormalizationError, match=field):
        validator(lambda request: httpx.Response(200, json=payload)).read_summary()


@pytest.mark.parametrize(
    "top_level,nested",
    [
        (None, "42"),
        ("", ""),
        ("12.0", "12.0"),
        ("-1", "-1"),
        (42, 42),
        ("42", "43"),
    ],
)
def test_invalid_or_contradictory_transaction_provenance_fails_closed(
    top_level: Any, nested: Any
) -> None:
    payload = account_payload()
    payload["lastTransactionID"] = top_level
    payload["account"]["lastTransactionID"] = nested

    with pytest.raises(OandaAccountNormalizationError, match="(?i)transaction"):
        validator(lambda request: httpx.Response(200, json=payload)).read_summary()


@pytest.mark.parametrize("field", ["lastTransactionID"])
def test_missing_nested_transaction_provenance_fails_closed(field: str) -> None:
    payload = account_payload()
    payload["account"].pop(field)

    with pytest.raises(OandaAccountNormalizationError, match="(?i)transaction"):
        validator(lambda request: httpx.Response(200, json=payload)).read_summary()


def test_identity_validation_remains_independent_of_summary_only_fields() -> None:
    payload = account_payload()
    payload["account"]["balance"] = {"provider": "malformed"}
    payload["account"]["openTradeCount"] = -1
    payload["account"]["lastTransactionID"] = "not numerical"
    payload["lastTransactionID"] = "not numerical"

    identity = validator(lambda request: httpx.Response(200, json=payload)).validate()

    assert identity.provider_account_id == ACCOUNT_ID
    with pytest.raises(OandaAccountNormalizationError):
        validator(lambda request: httpx.Response(200, json=payload)).read_summary()
