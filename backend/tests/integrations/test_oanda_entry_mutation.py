from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from backend.domain import Direction
from backend.integrations.oanda import OandaPracticeExecutionInstrument
from backend.integrations.oanda.execution import (
    OandaPracticeEntryMutation,
    OandaPracticeEntryMutationNormalizationError,
    OandaPracticeEntryReadbackReader,
)
from backend.integrations.oanda.mutation_request import (
    OandaMutationTransportError,
    OandaPracticeMutationRequester,
)
from backend.paper.execution import PaperExecutionOutcome
from backend.tests.paper.test_execution_contracts import instruction

ACCOUNT_ID = "001-011-5838423-001"
TEST_TOKEN = "unit-credential"
INSTRUMENT = OandaPracticeExecutionInstrument(
    provider_instrument="EUR_USD",
    display_precision=5,
    trade_units_precision=0,
    minimum_trade_size=Decimal("1"),
    maximum_order_units=Decimal("1000000"),
    last_transaction_id="42",
)


def _create_transaction(*, direction: str = "LONG") -> dict[str, Any]:
    value = instruction()
    if direction == "SHORT":
        value = instruction(Direction.SHORT)
    signed_units = "19230" if direction == "LONG" else "-19230"
    bound = "1.10020" if direction == "LONG" else "1.09980"
    trade_id = "7001" if direction == "LONG" else "7002"
    return {
        "id": "1001",
        "accountID": ACCOUNT_ID,
        "type": "MARKET_ORDER",
        "instrument": "EUR_USD",
        "units": signed_units,
        "timeInForce": "FOK",
        "priceBound": bound,
        "positionFill": "OPEN_ONLY",
        "clientOrderID": value.correlation.client_order_id,
        "clientExtensions": {
            "id": value.correlation.client_order_id,
            "tag": "atlas-paper-04",
        },
        "tradeClientExtensions": {"id": value.correlation.client_trade_id},
        "tradeID": trade_id,
    }


def _fill_transaction(
    *,
    price: str = "1.10010",
    direction: str = "LONG",
    order_id: str = "1001",
    fill_id: str = "1002",
    trade_id: str = "7001",
) -> dict[str, Any]:
    signed_units = "19230" if direction == "LONG" else "-19230"
    return {
        "id": fill_id,
        "accountID": ACCOUNT_ID,
        "type": "ORDER_FILL",
        "orderID": order_id,
        "clientOrderID": instruction().correlation.client_order_id,
        "instrument": "EUR_USD",
        "units": signed_units,
        "time": "2026-09-02T12:00:02.000000000Z",
        "price": "9.99999",
        "tradeOpened": {"tradeID": trade_id, "units": signed_units, "price": price},
    }


def _response_payload(
    *,
    fill: dict[str, Any] | None = None,
    cancel: dict[str, Any] | None = None,
    reject: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "orderCreateTransaction": _create_transaction(),
        "relatedTransactionIDs": ["1001", "1002"],
        "lastTransactionID": "1002",
    }
    if fill is not None:
        payload["orderFillTransaction"] = fill
    if cancel is not None:
        payload["orderCancelTransaction"] = cancel
    if reject is not None:
        payload["orderRejectTransaction"] = reject
    return payload


class FakeReadback:
    def __init__(
        self,
        responses: list[Mapping[str, Any] | None],
        transactions: list[Mapping[str, Any] | None] | None = None,
        trades: list[Mapping[str, Any] | None] | None = None,
    ) -> None:
        self.responses = responses
        self.transactions = transactions or []
        self.trades = trades or []
        self.order_calls: list[str] = []
        self.transaction_calls: list[str] = []
        self.trade_calls: list[str] = []

    def read_order_by_client_id(self, client_order_id: str) -> Mapping[str, Any] | None:
        self.order_calls.append(client_order_id)
        return self.responses.pop(0) if self.responses else None

    def read_transaction(self, transaction_id: str) -> Mapping[str, Any] | None:
        self.transaction_calls.append(transaction_id)
        return self.transactions.pop(0) if self.transactions else None

    def read_trade(self, trade_id: str) -> Mapping[str, Any] | None:
        self.trade_calls.append(trade_id)
        return self.trades.pop(0) if self.trades else None


def test_mutation_requester_posts_once_and_never_retries_transport_failure() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        raise httpx.ReadTimeout("provider timeout")

    requester = OandaPracticeMutationRequester(
        SecretStr(TEST_TOKEN), transport=httpx.MockTransport(handler)
    )

    with pytest.raises(OandaMutationTransportError) as error:
        requester.post_entry_order(ACCOUNT_ID, {"order": {"type": "MARKET"}})

    assert len(requests) == 1
    assert error.value.attempts == 1
    assert str(error.value) == "OANDA entry mutation transport outcome is uncertain"


@pytest.mark.parametrize("status", [429, 503])
def test_mutation_requester_returns_transient_status_without_retrying_or_exposing_body(
    status: int,
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(status, text="provider body")

    result = OandaPracticeMutationRequester(
        SecretStr(TEST_TOKEN), transport=httpx.MockTransport(handler)
    ).post_entry_order(ACCOUNT_ID, {"order": {"type": "MARKET"}})

    assert len(requests) == 1
    assert result.status_code == status
    assert result.json_valid is False
    assert "provider body" not in repr(result)


def test_mutation_requester_sends_exact_authenticated_practice_post() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(201, json={"ok": True})

    payload = {"order": {"type": "MARKET", "units": "1"}}
    result = OandaPracticeMutationRequester(
        SecretStr(TEST_TOKEN), transport=httpx.MockTransport(handler)
    ).post_entry_order(ACCOUNT_ID, payload)

    assert result.status_code == 201
    assert len(requests) == 1
    assert requests[0].method == "POST"
    assert requests[0].url == httpx.URL(
        "https://api-fxpractice.oanda.com/v3/accounts/001-011-5838423-001/orders"
    )
    assert requests[0].headers["Authorization"] == f"Bearer {TEST_TOKEN}"
    assert httpx.Request("POST", "https://example.test", json=payload).content == (
        requests[0].content
    )


def test_valid_fill_uses_trade_open_price_and_is_not_falsely_protected() -> None:
    payload = _response_payload(fill=_fill_transaction())
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(201, json=payload, headers={"RequestID": "req-1"})

    result = OandaPracticeEntryMutation(
        OandaPracticeMutationRequester(
            SecretStr(TEST_TOKEN), transport=httpx.MockTransport(handler)
        )
    ).submit(instruction(), INSTRUMENT, readback=FakeReadback([]))

    assert len(requests) == 1
    assert result.outcome is PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE
    assert result.fill is not None
    assert result.fill.price == Decimal("1.10010")
    assert result.fill.price != Decimal("9.99999")
    assert result.fill.broker_order_id == "1001"
    assert result.fill.broker_fill_transaction_id == "1002"
    assert result.fill.broker_trade_id == "7001"
    assert result.protection.stop_loss_status.value == "NOT_ATTEMPTED"
    assert result.protection.take_profit_status.value == "NOT_ATTEMPTED"


def test_fill_worse_than_the_risk_bound_is_an_invariant_failure() -> None:
    payload = _response_payload(fill=_fill_transaction(price="1.10021"))

    with pytest.raises(
        OandaPracticeEntryMutationNormalizationError, match="approved entry bound"
    ):
        OandaPracticeEntryMutation(_static_requester(payload)).submit(
            instruction(), INSTRUMENT
        )


def test_matching_fok_cancel_is_distinct_from_rejection() -> None:
    payload = _response_payload(
        cancel={
            "id": "1003",
            "accountID": ACCOUNT_ID,
            "type": "ORDER_CANCEL",
            "orderID": "1001",
            "reason": "FOK",
        }
    )
    result = OandaPracticeEntryMutation(_static_requester(payload)).submit(
        instruction(), INSTRUMENT, readback=FakeReadback([])
    )

    assert result.outcome is PaperExecutionOutcome.CANCELLED
    assert result.fill is None
    assert result.rejection is None


def test_matching_broker_reject_is_distinct_from_fok_cancel() -> None:
    payload = _response_payload(
        reject={
            "id": "1004",
            "accountID": ACCOUNT_ID,
            "type": "ORDER_REJECT",
            "orderID": "1001",
            "clientOrderID": instruction().correlation.client_order_id,
            "instrument": "EUR_USD",
            "rejectReason": "INSUFFICIENT_MARGIN",
        }
    )
    result = OandaPracticeEntryMutation(_static_requester(payload)).submit(
        instruction(), INSTRUMENT, readback=FakeReadback([])
    )

    assert result.outcome is PaperExecutionOutcome.REJECTED
    assert result.fill is None
    assert result.rejection is not None
    assert result.rejection.reason_code == "BROKER_ORDER_REJECTED"


def test_create_only_uses_one_bounded_original_correlation_readback() -> None:
    payload = _response_payload()
    readback = FakeReadback(
        [
            {
                **_create_transaction(),
                "state": "PENDING",
            }
        ]
    )
    result = OandaPracticeEntryMutation(_static_requester(payload)).submit(
        instruction(), INSTRUMENT, readback=readback
    )

    assert result.outcome is PaperExecutionOutcome.UNKNOWN
    assert result.uncertainty is not None
    assert result.uncertainty.detail_code == "ENTRY_READBACK_PENDING"
    assert readback.order_calls == [instruction().correlation.client_order_id]


def test_uncertain_create_only_fill_readback_uses_one_original_correlation_path() -> (
    None
):
    order = {
        **_create_transaction(),
        "state": "FILLED",
        "fillingTransactionID": "1002",
    }
    trade = {
        "id": "7001",
        "accountID": ACCOUNT_ID,
        "instrument": "EUR_USD",
        "state": "OPEN",
        "currentUnits": "19230",
        "price": "1.10010",
        "clientExtensions": {"id": instruction().correlation.client_trade_id},
    }
    readback = FakeReadback(
        [order],
        transactions=[_fill_transaction()],
        trades=[trade],
    )

    result = OandaPracticeEntryMutation(_static_requester(_response_payload())).submit(
        instruction(), INSTRUMENT, readback=readback
    )

    assert result.outcome is PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE
    assert readback.order_calls == [instruction().correlation.client_order_id]
    assert readback.transaction_calls == ["1002"]
    assert readback.trade_calls == ["7001"]


def test_malformed_possible_submission_reads_back_once_without_resubmitting() -> None:
    post_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        post_requests.append(request)
        return httpx.Response(201, text="not-json")

    readback = FakeReadback(
        [{**_create_transaction(), "state": "PENDING"}],
    )
    result = OandaPracticeEntryMutation(
        OandaPracticeMutationRequester(
            SecretStr(TEST_TOKEN), transport=httpx.MockTransport(handler)
        )
    ).submit(instruction(), INSTRUMENT, readback=readback)

    assert result.outcome is PaperExecutionOutcome.UNKNOWN
    assert result.uncertainty is not None
    assert result.uncertainty.detail_code == "ENTRY_READBACK_PENDING"
    assert len(post_requests) == 1
    assert readback.order_calls == [instruction().correlation.client_order_id]


def test_same_attempt_cannot_issue_a_second_entry_post() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(201, json=_response_payload())

    adapter = OandaPracticeEntryMutation(
        OandaPracticeMutationRequester(
            SecretStr(TEST_TOKEN), transport=httpx.MockTransport(handler)
        )
    )
    first = adapter.submit(instruction(), INSTRUMENT, readback=FakeReadback([]))
    second = adapter.submit(instruction(), INSTRUMENT, readback=FakeReadback([]))

    assert calls == 1
    assert second is first


def test_timeout_readback_not_found_is_unknown_without_a_second_post() -> None:
    post_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        post_requests.append(request)
        raise httpx.ConnectError("connection reset", request=request)

    readback = FakeReadback([None])
    result = OandaPracticeEntryMutation(
        OandaPracticeMutationRequester(
            SecretStr(TEST_TOKEN), transport=httpx.MockTransport(handler)
        )
    ).submit(instruction(), INSTRUMENT, readback=readback)

    assert result.outcome is PaperExecutionOutcome.UNKNOWN
    assert result.uncertainty is not None
    assert result.uncertainty.detail_code == "ENTRY_READBACK_NOT_FOUND"
    assert len(post_requests) == 1


def test_readback_reader_is_get_only_and_uses_original_client_correlation() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(404, json={"errorCode": "ORDER_NOT_FOUND"})

    reader = OandaPracticeEntryReadbackReader(
        SecretStr(TEST_TOKEN), ACCOUNT_ID, transport=httpx.MockTransport(handler)
    )
    assert reader.read_order_by_client_id("atlas-p04-o-original") is None
    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert requests[0].url.path.endswith("/orders/@atlas-p04-o-original")


def test_observation_requester_has_no_mutation_method() -> None:
    from backend.integrations.oanda.request import OandaObservationRequester

    assert not hasattr(OandaObservationRequester(SecretStr(TEST_TOKEN)), "post_entry")


def _static_requester(payload: Mapping[str, Any]) -> OandaPracticeMutationRequester:
    return OandaPracticeMutationRequester(
        SecretStr(TEST_TOKEN),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(201, json=payload)
        ),
    )
