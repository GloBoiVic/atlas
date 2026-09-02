from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from decimal import Decimal
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from backend.domain import TargetProposal
from backend.integrations.oanda import OandaPracticeExecutionInstrument
from backend.integrations.oanda.execution import (
    OandaPracticeEntryMutation,
    OandaPracticeProtectionCompletion,
)
from backend.integrations.oanda.mutation_request import (
    OandaMutationResponse,
    OandaPracticeMutationRequester,
)
from backend.paper.execution import (
    PaperExecutionInstruction,
    PaperExecutionOutcome,
    PaperExecutionResult,
    ProtectionLegStatus,
)
from backend.tests.paper.test_execution_contracts import instruction

ACCOUNT_ID = "001-011-5838423-001"
INSTRUMENT = OandaPracticeExecutionInstrument(
    provider_instrument="EUR_USD",
    display_precision=5,
    trade_units_precision=0,
    minimum_trade_size=Decimal("1"),
    maximum_order_units=Decimal("1000000"),
    last_transaction_id="42",
)


def _trade(
    *,
    fill_price: str = "1.10010",
    stop: Mapping[str, Any] | None = None,
    target: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    value = instruction()
    trade: dict[str, Any] = {
        "id": "7001",
        "accountID": ACCOUNT_ID,
        "instrument": "EUR_USD",
        "state": "OPEN",
        "initialUnits": "19230",
        "currentUnits": "19230",
        "price": fill_price,
        "clientExtensions": {"id": value.correlation.client_trade_id},
    }
    if stop is not None:
        trade["stopLossOrder"] = dict(stop)
    if target is not None:
        trade["takeProfitOrder"] = dict(target)
    return trade


def _stop(*, state: str = "PENDING", price: str = "1.09500") -> dict[str, Any]:
    value = instruction()
    return {
        "id": "8001",
        "type": "STOP_LOSS",
        "state": state,
        "tradeID": "7001",
        "price": price,
        "timeInForce": "GTC",
        "clientExtensions": {"id": value.correlation.client_stop_loss_order_id},
    }


def _target(*, state: str = "PENDING", price: str = "1.10877") -> dict[str, Any]:
    value = instruction()
    return {
        "id": "9001",
        "type": "TAKE_PROFIT",
        "state": state,
        "tradeID": "7001",
        "clientTradeID": value.correlation.client_trade_id,
        "price": price,
        "timeInForce": "GTC",
        "clientExtensions": {"id": value.correlation.client_take_profit_order_id},
    }


class FakeTradeReader:
    def __init__(self, trades: list[Mapping[str, Any] | None]) -> None:
        self.trades = trades
        self.trade_calls: list[str] = []

    def read_trade(self, trade_id: str) -> Mapping[str, Any] | None:
        self.trade_calls.append(trade_id)
        return self.trades.pop(0) if self.trades else None


def _entry_result(
    *, fill_price: str = "1.10010", value: PaperExecutionInstruction | None = None
) -> PaperExecutionResult:
    value = value or instruction()
    signed_units = "19230"
    create = {
        "id": "1001",
        "accountID": ACCOUNT_ID,
        "type": "MARKET_ORDER",
        "instrument": "EUR_USD",
        "units": signed_units,
        "timeInForce": "FOK",
        "priceBound": "1.10020",
        "positionFill": "OPEN_ONLY",
        "clientOrderID": value.correlation.client_order_id,
        "clientExtensions": {
            "id": value.correlation.client_order_id,
            "tag": "atlas-paper-04",
        },
        "tradeClientExtensions": {"id": value.correlation.client_trade_id},
    }
    fill = {
        "id": "1002",
        "accountID": ACCOUNT_ID,
        "type": "ORDER_FILL",
        "orderID": "1001",
        "clientOrderID": value.correlation.client_order_id,
        "instrument": "EUR_USD",
        "units": signed_units,
        "time": "2026-09-02T12:00:02.000000000Z",
        "tradeOpened": {
            "tradeID": "7001",
            "units": signed_units,
            "price": fill_price,
        },
    }

    class StaticRequester:
        def post_entry_order(
            self, account_id: str, payload: Mapping[str, Any]
        ) -> OandaMutationResponse:
            return OandaMutationResponse(
                status_code=201,
                request_id=None,
                payload={
                    "orderCreateTransaction": create,
                    "orderFillTransaction": fill,
                    "relatedTransactionIDs": ["1001", "1002"],
                    "lastTransactionID": "1002",
                },
                json_valid=True,
            )

    return OandaPracticeEntryMutation(StaticRequester()).submit(value, INSTRUMENT)


def _target_response(value: Any) -> dict[str, Any]:
    return {
        "takeProfitOrderTransaction": value,
        "lastTransactionID": "9002",
        "relatedTransactionIDs": ["9002"],
    }


def _target_transaction(*, price: str = "1.10877") -> dict[str, Any]:
    value = instruction()
    return {
        "id": "9002",
        "accountID": ACCOUNT_ID,
        "type": "TAKE_PROFIT_ORDER",
        "tradeID": "7001",
        "clientTradeID": value.correlation.client_trade_id,
        "price": price,
        "timeInForce": "GTC",
        "clientExtensions": {"id": value.correlation.client_take_profit_order_id},
    }


def test_actual_fill_target_is_confirmed_with_one_take_profit_put_only() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json=_target_response(_target_transaction()),
            headers={"RequestID": "target-request"},
        )

    initial = _trade(stop=_stop())
    final = _trade(stop=_stop(), target=_target())
    reader = FakeTradeReader([initial, final])
    requester = OandaPracticeMutationRequester(
        SecretStr("unit-credential"), transport=httpx.MockTransport(handler)
    )

    result = OandaPracticeProtectionCompletion(requester, reader).complete(
        _entry_result(), INSTRUMENT
    )

    assert result.outcome is PaperExecutionOutcome.FILLED_PROTECTED
    assert result.fill is not None
    assert result.fill.price == Decimal("1.10010")
    assert result.protection.stop_loss_status is ProtectionLegStatus.CONFIRMED
    assert result.protection.take_profit_status is ProtectionLegStatus.CONFIRMED
    assert result.protection.actual_target_price == Decimal("1.10877")
    assert result.protection.take_profit is not None
    assert result.protection.take_profit.price == Decimal("1.10877")
    assert len(requests) == 1
    assert requests[0].method == "PUT"
    assert requests[0].url.path == f"/v3/accounts/{ACCOUNT_ID}/trades/7001/orders"
    assert (
        httpx.Request(
            "PUT",
            "https://example.test",
            json={
                "takeProfit": {
                    "price": "1.10877",
                    "timeInForce": "GTC",
                    "clientExtensions": {
                        "id": instruction().correlation.client_take_profit_order_id
                    },
                }
            },
        ).content
        == requests[0].content
    )
    assert reader.trade_calls == ["7001", "7001"]


def test_better_fill_resolves_target_from_actual_fill_not_risk_target() -> None:
    reader = FakeTradeReader(
        [_trade(stop=_stop()), _trade(stop=_stop(), target=_target())]
    )
    requester = OandaPracticeMutationRequester(
        SecretStr("unit-credential"),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, json=_target_response(_target_transaction())
            )
        ),
    )

    result = OandaPracticeProtectionCompletion(requester, reader).complete(
        _entry_result(fill_price="1.10010"), INSTRUMENT
    )

    assert result.outcome is PaperExecutionOutcome.FILLED_PROTECTED
    assert result.instruction.pre_submission.target_price == Decimal("1.10904")
    assert result.protection.actual_target_price == Decimal("1.10877")


def test_stop_mismatch_is_incomplete_and_target_is_not_attempted() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={})

    reader = FakeTradeReader([_trade(stop=_stop(price="1.09501"))])
    result = OandaPracticeProtectionCompletion(
        OandaPracticeMutationRequester(
            SecretStr("unit-credential"), transport=httpx.MockTransport(handler)
        ),
        reader,
    ).complete(_entry_result(), INSTRUMENT)

    assert result.outcome is PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE
    assert result.protection.stop_loss_status is ProtectionLegStatus.UNKNOWN
    assert result.protection.take_profit_status is ProtectionLegStatus.NOT_ATTEMPTED
    assert result.protection.actual_target_price is None
    assert calls == 0
    assert reader.trade_calls == ["7001"]


def test_unrepresentable_actual_target_is_refused_without_rounding_or_put() -> None:
    value = instruction()
    value = replace(
        value,
        strategy_decision=replace(
            value.strategy_decision, target=TargetProposal(multiple=Decimal("1.71"))
        ),
    )
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={})

    reader = FakeTradeReader([_trade(stop=_stop())])
    result = OandaPracticeProtectionCompletion(
        OandaPracticeMutationRequester(
            SecretStr("unit-credential"), transport=httpx.MockTransport(handler)
        ),
        reader,
    ).complete(_entry_result(value=value), INSTRUMENT)

    assert result.outcome is PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE
    assert result.protection.stop_loss_status is ProtectionLegStatus.CONFIRMED
    assert result.protection.take_profit_status is ProtectionLegStatus.NOT_ATTEMPTED
    assert result.protection.actual_target_price == Decimal("1.1088210")
    assert "TARGET_PRECISION_UNREPRESENTABLE" in result.diagnostic_codes
    assert calls == 0


@pytest.mark.parametrize("state", ["CANCELLED", "FILLED"])
def test_non_pending_stop_is_rejected_and_never_repaired(state: str) -> None:
    reader = FakeTradeReader([_trade(stop=_stop(state=state))])
    result = OandaPracticeProtectionCompletion(
        OandaPracticeMutationRequester(
            SecretStr("unit-credential"),
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})),
        ),
        reader,
    ).complete(_entry_result(), INSTRUMENT)

    assert result.outcome is PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE
    assert result.protection.stop_loss_status is ProtectionLegStatus.REJECTED
    assert result.protection.take_profit_status is ProtectionLegStatus.NOT_ATTEMPTED


def test_target_rejection_is_incomplete_without_retry() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "takeProfitOrderRejectTransaction": {
                    "id": "9002",
                    "accountID": ACCOUNT_ID,
                    "type": "TAKE_PROFIT_ORDER_REJECT",
                    "tradeID": "7001",
                    "clientTradeID": instruction().correlation.client_trade_id,
                }
            },
        )

    reader = FakeTradeReader([_trade(stop=_stop())])
    result = OandaPracticeProtectionCompletion(
        OandaPracticeMutationRequester(
            SecretStr("unit-credential"), transport=httpx.MockTransport(handler)
        ),
        reader,
    ).complete(_entry_result(), INSTRUMENT)

    assert result.outcome is PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE
    assert result.protection.stop_loss_status is ProtectionLegStatus.CONFIRMED
    assert result.protection.take_profit_status is ProtectionLegStatus.REJECTED
    assert result.rejection is not None
    assert result.rejection.detail_code == "TARGET_BROKER_REJECTED"
    assert len(requests) == 1


def test_target_transport_uncertainty_is_incomplete_and_put_is_not_retried() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        raise httpx.ReadTimeout("provider timeout")

    reader = FakeTradeReader([_trade(stop=_stop()), _trade(stop=_stop())])
    completion = OandaPracticeProtectionCompletion(
        OandaPracticeMutationRequester(
            SecretStr("unit-credential"), transport=httpx.MockTransport(handler)
        ),
        reader,
    )
    result = completion.complete(_entry_result(), INSTRUMENT)
    repeated = completion.complete(_entry_result(), INSTRUMENT)

    assert result.outcome is PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE
    assert result.protection.stop_loss_status is ProtectionLegStatus.CONFIRMED
    assert result.protection.take_profit_status is ProtectionLegStatus.UNKNOWN
    assert result.uncertainty is not None
    assert result.uncertainty.detail_code == "TARGET_MUTATION_TRANSPORT_UNCERTAIN"
    assert repeated is result
    assert len(requests) == 1


def test_final_readback_must_prove_both_protections() -> None:
    reader = FakeTradeReader([_trade(stop=_stop()), _trade(stop=_stop())])
    requester = OandaPracticeMutationRequester(
        SecretStr("unit-credential"),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, json=_target_response(_target_transaction())
            )
        ),
    )

    result = OandaPracticeProtectionCompletion(requester, reader).complete(
        _entry_result(), INSTRUMENT
    )

    assert result.outcome is PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE
    assert result.protection.stop_loss_status is ProtectionLegStatus.CONFIRMED
    assert result.protection.take_profit_status is ProtectionLegStatus.UNKNOWN
