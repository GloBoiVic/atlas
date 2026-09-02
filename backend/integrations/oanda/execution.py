"""OANDA Practice entry translation and post-Fill protection completion."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Literal, Protocol, cast
from urllib.parse import quote
from uuid import UUID

import httpx
from pydantic import SecretStr

from backend.domain import Direction, Instrument, Provider

from .execution_instrument import OandaPracticeExecutionInstrument
from .mutation_request import (
    OandaMutationResponse,
    OandaPracticeMutationRequester,
)
from .primitives import OandaPrimitiveError, parse_decimal, parse_transaction_id
from .request import OandaObservationRequester
from .source import (
    OandaError,
    OandaNormalizationError,
    OandaRequestError,
)

if TYPE_CHECKING:
    from backend.paper.execution import (
        BrokerFillFacts,
        BrokerProtectionOrder,
        BrokerRejection,
        ExecutionCorrelation,
        PaperExecutionInstruction,
        PaperExecutionOutcome,
        PaperExecutionResult,
        ProtectionLegStatus,
        TransactionProvenance,
    )


class OandaPracticeEntryTranslationError(OandaNormalizationError):
    """A provider-neutral entry instruction cannot become a safe OANDA payload."""


def translate_oanda_practice_market_order(
    instruction: PaperExecutionInstruction,
    execution_instrument: OandaPracticeExecutionInstrument,
    *,
    correlation: ExecutionCorrelation | None = None,
) -> dict[str, Any]:
    """Translate one approved instruction to the exact OANDA entry payload.

    This function performs no network operation and allocates no attempt
    identity.  A supplied correlation must be the deterministic correlation
    for the instruction's existing attempt.
    """
    from backend.paper.execution import ExecutionCorrelation, PaperExecutionInstruction

    if type(instruction) is not PaperExecutionInstruction:
        raise OandaPracticeEntryTranslationError(
            "OANDA entry translation requires a PaperExecutionInstruction"
        )
    if type(execution_instrument) is not OandaPracticeExecutionInstrument:
        raise OandaPracticeEntryTranslationError(
            "OANDA entry translation requires observed execution instrument metadata"
        )
    expected_correlation = instruction.correlation
    if correlation is not None and (
        type(correlation) is not ExecutionCorrelation
        or correlation != expected_correlation
    ):
        raise OandaPracticeEntryTranslationError(
            "OANDA entry correlation does not match attempt_id"
        )
    selected_correlation = expected_correlation if correlation is None else correlation

    account = instruction.account
    if (
        account.provider is not Provider.OANDA
        or account.environment != "PRACTICE"
        or account.base_currency != "USD"
        or instruction.instrument is not Instrument.EUR_USD
        or execution_instrument.provider_instrument != "EUR_USD"
        or instruction.display_precision != execution_instrument.display_precision
        or instruction.trade_units_precision
        != execution_instrument.trade_units_precision
    ):
        raise OandaPracticeEntryTranslationError(
            "OANDA entry translation received unsupported account or instrument"
        )

    try:
        quantity = execution_instrument.serialize_quantity(
            instruction.requested_quantity
        )
        entry_price = execution_instrument.serialize_price(
            instruction.approved_entry_price
        )
        stop_price = execution_instrument.serialize_price(instruction.stop_price)
    except OandaNormalizationError as error:
        raise OandaPracticeEntryTranslationError(
            "OANDA entry value is not exactly representable"
        ) from error

    signed_units = (
        quantity if instruction.direction is Direction.LONG else f"-{quantity}"
    )
    order: dict[str, Any] = {
        "type": "MARKET",
        "instrument": "EUR_USD",
        "units": signed_units,
        "timeInForce": "FOK",
        "priceBound": entry_price,
        "positionFill": "OPEN_ONLY",
        "clientExtensions": {
            "id": selected_correlation.client_order_id,
            "tag": "atlas-paper-04",
        },
        "tradeClientExtensions": {
            "id": selected_correlation.client_trade_id,
        },
        "stopLossOnFill": {
            "price": stop_price,
            "timeInForce": "GTC",
            "clientExtensions": {
                "id": selected_correlation.client_stop_loss_order_id,
            },
        },
    }
    return {"order": order}


class OandaPracticeEntryTranslator:
    """Stateless public seam for translating an approved entry instruction."""

    @staticmethod
    def translate(
        instruction: PaperExecutionInstruction,
        execution_instrument: OandaPracticeExecutionInstrument,
        *,
        correlation: ExecutionCorrelation | None = None,
    ) -> dict[str, Any]:
        return translate_oanda_practice_market_order(
            instruction,
            execution_instrument,
            correlation=correlation,
        )


def translate_entry_order(
    instruction: PaperExecutionInstruction,
    execution_instrument: OandaPracticeExecutionInstrument,
    *,
    correlation: ExecutionCorrelation | None = None,
) -> Mapping[str, Any]:
    """Compatibility-named public seam for the pure entry translation."""
    return translate_oanda_practice_market_order(
        instruction,
        execution_instrument,
        correlation=correlation,
    )


class OandaPracticeEntryMutationNormalizationError(OandaNormalizationError):
    """A broker-confirmed Fill violates an execution invariant."""

    def __init__(
        self,
        message: str,
        *,
        fill: BrokerFillFacts | None = None,
        transaction_provenance: TransactionProvenance | None = None,
        diagnostic_code: str = "ENTRY_FILL_INVARIANT_VIOLATION",
    ) -> None:
        self.fill = fill
        self.transaction_provenance = transaction_provenance
        self.diagnostic_code = diagnostic_code
        super().__init__(message)


class OandaPracticeEntryReadbackError(OandaNormalizationError):
    """A bounded entry readback response cannot be safely interpreted."""


class OandaEntryReadbackReader(Protocol):
    """Public seam for the finite uncertain-entry readback sequence."""

    def read_order_by_client_id(
        self, client_order_id: str
    ) -> Mapping[str, Any] | None: ...

    def read_transaction(self, transaction_id: str) -> Mapping[str, Any] | None: ...

    def read_trade(self, trade_id: str) -> Mapping[str, Any] | None: ...


class OandaProtectionReadbackReader(Protocol):
    """Public seam for the two bounded Trade-detail reads in protection."""

    def read_trade(self, trade_id: str) -> Mapping[str, Any] | None: ...


class OandaProtectionMutationRequester(Protocol):
    """Public seam for one dependent Trade-order mutation."""

    def put_trade_orders(
        self, account_id: str, trade_id: str, payload: Mapping[str, Any]
    ) -> OandaMutationResponse | Mapping[str, Any]: ...


OandaTradeProtectionReader = OandaProtectionReadbackReader


_READBACK_ORDER_PATH = "/v3/accounts/{account_id}/orders/@{client_order_id}"
_READBACK_TRANSACTION_PATH = "/v3/accounts/{account_id}/transactions/{transaction_id}"
_READBACK_TRADE_PATH = "/v3/accounts/{account_id}/trades/{trade_id}"


class OandaPracticeEntryReadbackReader:
    """Read only the bounded broker facts needed after uncertain entry POST."""

    def __init__(
        self,
        token: SecretStr | None,
        account_id: str,
        *,
        client: httpx.Client | None = None,
        transport: httpx.BaseTransport | None = None,
        connect_timeout_seconds: float = 5.0,
        read_timeout_seconds: float = 20.0,
    ) -> None:
        self._account_id = account_id
        self._requester = OandaObservationRequester(
            token,
            client=client,
            transport=transport,
            connect_timeout_seconds=connect_timeout_seconds,
            read_timeout_seconds=read_timeout_seconds,
        )

    def read_order_by_client_id(self, client_order_id: str) -> Mapping[str, Any] | None:
        path = _READBACK_ORDER_PATH.format(
            account_id=quote(self._account_id, safe="-"),
            client_order_id=quote(client_order_id, safe="-_@"),
        )
        payload = self._get(path, "entry order readback")
        if payload is None:
            return None
        return _unwrap_readback_object(payload, "order")

    def read_transaction(self, transaction_id: str) -> Mapping[str, Any] | None:
        path = _READBACK_TRANSACTION_PATH.format(
            account_id=quote(self._account_id, safe="-"),
            transaction_id=quote(transaction_id, safe="-"),
        )
        payload = self._get(path, "entry transaction readback")
        if payload is None:
            return None
        for key in (
            "orderFillTransaction",
            "orderCancelTransaction",
            "orderRejectTransaction",
            "orderCreateTransaction",
            "orderReissueTransaction",
            "orderReissueRejectTransaction",
        ):
            if key in payload:
                return _unwrap_readback_object(payload, key)
        return payload

    def read_trade(self, trade_id: str) -> Mapping[str, Any] | None:
        path = _READBACK_TRADE_PATH.format(
            account_id=quote(self._account_id, safe="-"),
            trade_id=quote(trade_id, safe="-"),
        )
        payload = self._get(path, "entry Trade readback")
        if payload is None:
            return None
        return _unwrap_readback_object(payload, "trade")

    def _get(self, path: str, subject: str) -> Mapping[str, Any] | None:
        try:
            payload = self._requester.get_json(path, error_subject=subject)
        except OandaRequestError as error:
            if error.status_code == 404:
                return None
            raise
        if not isinstance(payload, dict):
            raise OandaPracticeEntryReadbackError(
                "OANDA entry readback response is not an object"
            )
        return cast(Mapping[str, Any], payload)


class OandaEntryMutationRequester(Protocol):
    """Public requester seam used by the entry mutation adapter."""

    def post_entry_order(
        self, account_id: str, payload: Mapping[str, Any]
    ) -> OandaMutationResponse | Mapping[str, Any]: ...


class OandaPracticeEntryMutation:
    """Submit and normalize one OANDA Practice entry attempt.

    A mutation requester is injected so tests and callers can observe the
    exact one-POST boundary.  If entry state is uncertain, this adapter only
    reads back the original deterministic client correlation; it never posts
    a replacement order.
    """

    def __init__(
        self,
        requester: OandaEntryMutationRequester | OandaPracticeMutationRequester,
        *,
        readback: OandaEntryReadbackReader | None = None,
    ) -> None:
        self._requester = requester
        self._readback = readback
        self._attempted: set[UUID] = set()
        self._results: dict[UUID, PaperExecutionResult] = {}

    def submit(
        self,
        instruction: PaperExecutionInstruction,
        execution_instrument: OandaPracticeExecutionInstrument,
        *,
        readback: OandaEntryReadbackReader | None = None,
    ) -> PaperExecutionResult:
        """Perform at most one entry POST and normalize its bounded outcome."""
        from backend.paper.execution import (
            PaperExecutionInstruction,
            PaperExecutionOutcome,
            TransactionProvenance,
        )

        if type(instruction) is not PaperExecutionInstruction:
            raise OandaPracticeEntryTranslationError(
                "entry mutation requires a PaperExecutionInstruction"
            )
        previous = self._results.get(instruction.attempt_id)
        if previous is not None:
            return previous
        if instruction.attempt_id in self._attempted:
            return _unknown_result(
                instruction,
                "ENTRY_ATTEMPT_ALREADY_SUBMITTED",
            )
        selected_readback = readback if readback is not None else self._readback
        correlation = instruction.correlation
        payload = translate_oanda_practice_market_order(
            instruction,
            execution_instrument,
            correlation=correlation,
        )
        self._attempted.add(instruction.attempt_id)
        try:
            response = self._requester.post_entry_order(
                instruction.account.account_id, payload
            )
        except OandaRequestError:
            result = self._readback_or_unknown(
                instruction,
                selected_readback,
                detail_code="ENTRY_TRANSPORT_UNCERTAIN",
                request_id=None,
                initial_provenance=TransactionProvenance(),
            )
        else:
            result = normalize_oanda_practice_entry_response(instruction, response)
            if result.outcome is PaperExecutionOutcome.UNKNOWN:
                result = self._readback_or_unknown(
                    instruction,
                    selected_readback,
                    detail_code="ENTRY_RESPONSE_UNCERTAIN",
                    request_id=(
                        _safe_request_id(response.request_id)
                        if isinstance(response, OandaMutationResponse)
                        else None
                    ),
                    initial_provenance=result.transaction_provenance,
                )
        self._results[instruction.attempt_id] = result
        return result

    def _readback_or_unknown(
        self,
        instruction: PaperExecutionInstruction,
        readback: OandaEntryReadbackReader | None,
        *,
        detail_code: str,
        request_id: str | None,
        initial_provenance: TransactionProvenance,
    ) -> PaperExecutionResult:
        if readback is None:
            return _unknown_result(
                instruction,
                detail_code,
                request_id=request_id,
                provenance=initial_provenance,
            )
        try:
            order = readback.read_order_by_client_id(
                instruction.correlation.client_order_id
            )
            if order is None:
                return _unknown_result(
                    instruction,
                    "ENTRY_READBACK_NOT_FOUND",
                    request_id=request_id,
                    provenance=initial_provenance,
                )
            state = order.get("state")
            if state == "PENDING":
                return _unknown_result(
                    instruction,
                    "ENTRY_READBACK_PENDING",
                    request_id=request_id,
                    provenance=initial_provenance,
                )
            if state == "FILLED":
                result = self._readback_fill(instruction, order, readback)
                if result is not None:
                    return result
                return _unknown_result(
                    instruction,
                    "ENTRY_READBACK_CONTRADICTORY",
                    request_id=request_id,
                    provenance=initial_provenance,
                )
            if state == "CANCELLED":
                result = self._readback_cancel(instruction, order, readback)
                if result is not None:
                    return result
                return _unknown_result(
                    instruction,
                    "ENTRY_READBACK_CONTRADICTORY",
                    request_id=request_id,
                    provenance=initial_provenance,
                )
            return _unknown_result(
                instruction,
                "ENTRY_READBACK_UNRECOGNIZED",
                request_id=request_id,
                provenance=initial_provenance,
            )
        except OandaPracticeEntryMutationNormalizationError:
            raise
        except (OandaError, httpx.RequestError, ValueError, TypeError, AttributeError):
            return _unknown_result(
                instruction,
                "ENTRY_READBACK_FAILED",
                request_id=request_id,
                provenance=initial_provenance,
            )

    def _readback_fill(
        self,
        instruction: PaperExecutionInstruction,
        order: Mapping[str, Any],
        readback: OandaEntryReadbackReader,
    ) -> PaperExecutionResult | None:
        transaction_id = _positive_id(order.get("fillingTransactionID"))
        if transaction_id is None:
            return None
        fill_transaction = readback.read_transaction(transaction_id)
        if fill_transaction is None:
            return None
        fill_transaction = _unwrap_transaction(fill_transaction)
        synthetic_create = dict(order)
        synthetic_create["type"] = "MARKET_ORDER"
        result = normalize_oanda_practice_entry_response(
            instruction,
            OandaMutationResponse(
                status_code=200,
                request_id=None,
                payload={
                    "orderCreateTransaction": synthetic_create,
                    "orderFillTransaction": fill_transaction,
                    "lastTransactionID": transaction_id,
                },
                json_valid=True,
            ),
        )
        if result.fill is None:
            return None
        trade = readback.read_trade(result.fill.broker_trade_id)
        if trade is None or not _matches_readback_trade(
            trade, instruction, result.fill
        ):
            return None
        return result

    def _readback_cancel(
        self,
        instruction: PaperExecutionInstruction,
        order: Mapping[str, Any],
        readback: OandaEntryReadbackReader,
    ) -> PaperExecutionResult | None:
        transaction_id = _positive_id(order.get("cancellingTransactionID"))
        if transaction_id is None:
            return None
        cancel_transaction = readback.read_transaction(transaction_id)
        if cancel_transaction is None:
            return None
        cancel_transaction = _unwrap_transaction(cancel_transaction)
        synthetic_create = dict(order)
        synthetic_create["type"] = "MARKET_ORDER"
        result = normalize_oanda_practice_entry_response(
            instruction,
            OandaMutationResponse(
                status_code=200,
                request_id=None,
                payload={
                    "orderCreateTransaction": synthetic_create,
                    "orderCancelTransaction": cancel_transaction,
                    "lastTransactionID": transaction_id,
                },
                json_valid=True,
            ),
        )
        if result.outcome is PaperExecutionOutcome.CANCELLED:
            return result
        return None


def normalize_oanda_practice_entry_response(
    instruction: PaperExecutionInstruction,
    response: OandaMutationResponse | Mapping[str, Any],
    *,
    correlation: ExecutionCorrelation | None = None,
) -> PaperExecutionResult:
    """Normalize only bounded facts from one entry mutation response."""
    from backend.paper.execution import (
        ExecutionCorrelation,
        PaperExecutionInstruction,
        PaperExecutionOutcome,
    )

    if type(instruction) is not PaperExecutionInstruction:
        raise OandaPracticeEntryMutationNormalizationError(
            "entry response requires a PaperExecutionInstruction"
        )
    expected_correlation = instruction.correlation
    if correlation is not None and (
        type(correlation) is not ExecutionCorrelation
        or correlation != expected_correlation
    ):
        raise OandaPracticeEntryMutationNormalizationError(
            "entry response correlation does not match attempt_id"
        )
    selected_correlation = expected_correlation if correlation is None else correlation
    if isinstance(response, OandaMutationResponse):
        request_id = _safe_request_id(response.request_id)
        payload_value = response.payload
        json_valid = response.json_valid
    elif type(response) is dict:
        request_id = None
        payload_value = cast(Mapping[str, Any], response)
        json_valid = True
    else:
        return _unknown_result(
            instruction,
            "ENTRY_MALFORMED_RESPONSE",
            request_id=None,
        )
    if not json_valid or not isinstance(payload_value, Mapping):
        return _unknown_result(
            instruction,
            "ENTRY_MALFORMED_RESPONSE",
            request_id=request_id,
        )
    payload = cast(Mapping[str, Any], payload_value)
    if _has_malformed_transaction_shape(payload):
        return _unknown_result(
            instruction,
            "ENTRY_MALFORMED_RESPONSE",
            request_id=request_id,
            provenance=_provenance(payload, request_id=request_id),
        )
    provenance = _provenance(payload, request_id=request_id)
    create = _transaction(payload, "orderCreateTransaction")
    fill = _transaction(payload, "orderFillTransaction")
    cancel = _transaction(payload, "orderCancelTransaction")
    reject = _transaction(payload, "orderRejectTransaction")
    reissue = _transaction(payload, "orderReissueTransaction")
    reissue_reject = _transaction(payload, "orderReissueRejectTransaction")

    if reissue is not None or reissue_reject is not None:
        return _unknown_result(
            instruction,
            "ENTRY_REISSUE_UNSUPPORTED",
            request_id=request_id,
            provenance=provenance,
        )
    if fill is not None and (cancel is not None or reject is not None):
        return _unknown_result(
            instruction,
            "ENTRY_CONTRADICTORY_TERMINALS",
            request_id=request_id,
            provenance=provenance,
        )
    if fill is not None:
        if create is None or not _matches_create(
            create, instruction, selected_correlation
        ):
            return _unknown_result(
                instruction,
                "ENTRY_FILL_UNMATCHED",
                request_id=request_id,
                provenance=provenance,
            )
        return _filled_result(
            instruction,
            create,
            fill,
            request_id=request_id,
            provenance=provenance,
        )
    if cancel is not None:
        if (
            create is None
            or not _matches_create(create, instruction, selected_correlation)
            or not _matches_cancel(cancel, instruction, create)
        ):
            return _unknown_result(
                instruction,
                "ENTRY_CANCEL_UNMATCHED",
                request_id=request_id,
                provenance=provenance,
            )
        return _terminal_result(
            instruction,
            PaperExecutionOutcome.CANCELLED,
            request_id=request_id,
            provenance=provenance,
            diagnostic="ENTRY_FOK_CANCELLED",
        )
    if reject is not None:
        if not _matches_reject(reject, instruction, selected_correlation):
            return _unknown_result(
                instruction,
                "ENTRY_REJECT_UNMATCHED",
                request_id=request_id,
                provenance=provenance,
            )
        return _terminal_result(
            instruction,
            PaperExecutionOutcome.REJECTED,
            rejection=_rejection(reject),
            request_id=request_id,
            provenance=provenance,
            diagnostic="ENTRY_BROKER_REJECTED",
        )
    return _unknown_result(
        instruction,
        "ENTRY_RESPONSE_UNCERTAIN",
        request_id=request_id,
        provenance=provenance,
    )


def normalize_entry_response(
    instruction: PaperExecutionInstruction,
    response: OandaMutationResponse | Mapping[str, Any],
    *,
    correlation: ExecutionCorrelation | None = None,
) -> PaperExecutionResult:
    """Compatibility-named public seam for entry response normalization."""
    return normalize_oanda_practice_entry_response(
        instruction, response, correlation=correlation
    )


def _filled_result(
    instruction: PaperExecutionInstruction,
    create: Mapping[str, Any],
    fill: Mapping[str, Any],
    *,
    request_id: str | None,
    provenance: TransactionProvenance,
) -> PaperExecutionResult:
    from backend.paper.execution import (
        BrokerFillFacts,
        PaperExecutionOutcome,
    )

    order_id = _positive_id(create.get("id"))
    fill_id = _positive_id(fill.get("id"))
    if order_id is None or fill_id is None:
        return _unknown_result(
            instruction,
            "ENTRY_FILL_MALFORMED",
            request_id=request_id,
            provenance=provenance,
        )
    expected_units = _signed_quantity(instruction)
    if (
        fill.get("accountID") != instruction.account.account_id
        or fill.get("type") != "ORDER_FILL"
        or fill.get("orderID") != order_id
        or fill.get("clientOrderID") != instruction.correlation.client_order_id
        or fill.get("instrument") != "EUR_USD"
        or _decimal_value(fill.get("units")) != expected_units
    ):
        return _unknown_result(
            instruction,
            "ENTRY_FILL_UNMATCHED",
            request_id=request_id,
            provenance=provenance,
        )
    opened = fill.get("tradeOpened")
    if not isinstance(opened, Mapping):
        return _unknown_result(
            instruction,
            "ENTRY_TRADE_OPEN_MISSING",
            request_id=request_id,
            provenance=provenance,
        )
    opened_map = cast(Mapping[str, Any], opened)
    if fill.get("tradeReduced") is not None or fill.get("tradesClosed") not in (
        None,
        [],
    ):
        return _unknown_result(
            instruction,
            "ENTRY_FILL_REDUCED_OR_CLOSED",
            request_id=request_id,
            provenance=provenance,
        )
    trade_id = _positive_id(opened_map.get("tradeID"))
    opened_units = _decimal_value(opened_map.get("units"))
    price = _decimal_value(opened_map.get("price"))
    executed_at = _timestamp(fill.get("time"))
    if (
        trade_id is None
        or opened_units != expected_units
        or price is None
        or price <= 0
        or executed_at is None
    ):
        return _unknown_result(
            instruction,
            "ENTRY_TRADE_OPEN_MALFORMED",
            request_id=request_id,
            provenance=provenance,
        )

    stop = instruction.stop_price
    actual_risk = abs(expected_units) * abs(price - stop)
    broker_fill = BrokerFillFacts(
        broker_order_id=order_id,
        broker_fill_transaction_id=fill_id,
        broker_trade_id=trade_id,
        signed_units=expected_units,
        price=price,
        executed_at=executed_at,
        actual_initial_risk=actual_risk,
    )
    if instruction.direction is Direction.LONG:
        if price > instruction.approved_entry_price:
            raise OandaPracticeEntryMutationNormalizationError(
                "OANDA LONG Fill exceeded the approved entry bound",
                fill=broker_fill,
                transaction_provenance=provenance,
                diagnostic_code="ENTRY_FILL_BOUND_VIOLATION",
            )
        if not stop < price:
            raise OandaPracticeEntryMutationNormalizationError(
                "OANDA LONG Fill has invalid Stop Loss geometry",
                fill=broker_fill,
                transaction_provenance=provenance,
                diagnostic_code="ENTRY_FILL_STOP_GEOMETRY_VIOLATION",
            )
    else:
        if price < instruction.approved_entry_price:
            raise OandaPracticeEntryMutationNormalizationError(
                "OANDA SHORT Fill exceeded the approved entry bound",
                fill=broker_fill,
                transaction_provenance=provenance,
                diagnostic_code="ENTRY_FILL_BOUND_VIOLATION",
            )
        if not stop > price:
            raise OandaPracticeEntryMutationNormalizationError(
                "OANDA SHORT Fill has invalid Stop Loss geometry",
                fill=broker_fill,
                transaction_provenance=provenance,
                diagnostic_code="ENTRY_FILL_STOP_GEOMETRY_VIOLATION",
            )
    risk_budget = instruction.pre_submission.risk_budget
    if risk_budget is None or actual_risk > risk_budget:
        raise OandaPracticeEntryMutationNormalizationError(
            "OANDA Fill actual initial risk exceeded the approved budget",
            fill=broker_fill,
            transaction_provenance=provenance,
            diagnostic_code="ENTRY_FILL_RISK_BUDGET_EXCEEDED",
        )
    return _terminal_result(
        instruction,
        PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE,
        fill=broker_fill,
        request_id=request_id,
        provenance=provenance,
        diagnostic="ENTRY_FILL_CONFIRMED",
    )


def _terminal_result(
    instruction: PaperExecutionInstruction,
    outcome: PaperExecutionOutcome,
    *,
    fill: BrokerFillFacts | None = None,
    rejection: BrokerRejection | None = None,
    request_id: str | None,
    provenance: TransactionProvenance,
    diagnostic: str,
) -> PaperExecutionResult:
    from backend.paper.execution import (
        BrokerFillFacts,
        BrokerRejection,
        ExecutionCorrelation,
        PaperExecutionInstruction,
        PaperExecutionOutcome,
        PaperExecutionResult,
        ProtectionConfirmation,
        ProtectionLegStatus,
        TransactionProvenance,
    )

    if type(instruction) is not PaperExecutionInstruction:
        raise OandaPracticeEntryMutationNormalizationError(
            "entry result requires a PaperExecutionInstruction"
        )
    if fill is not None and type(fill) is not BrokerFillFacts:
        raise OandaPracticeEntryMutationNormalizationError("invalid normalized Fill")
    if rejection is not None and type(rejection) is not BrokerRejection:
        raise OandaPracticeEntryMutationNormalizationError("invalid rejection facts")
    if type(outcome) is not PaperExecutionOutcome:
        raise OandaPracticeEntryMutationNormalizationError("invalid entry outcome")
    if request_id is not None and provenance.request_id is None:
        provenance = TransactionProvenance(
            request_id=request_id,
            provider_transaction_ids=provenance.provider_transaction_ids,
            batch_ids=provenance.batch_ids,
            related_transaction_ids=provenance.related_transaction_ids,
            last_transaction_id=provenance.last_transaction_id,
        )
    return PaperExecutionResult(
        outcome=outcome,
        instruction=instruction,
        correlation=ExecutionCorrelation.for_attempt(instruction.attempt_id),
        fill=fill,
        protection=ProtectionConfirmation(
            stop_loss_status=ProtectionLegStatus.NOT_ATTEMPTED,
            stop_loss=None,
            take_profit_status=ProtectionLegStatus.NOT_ATTEMPTED,
            take_profit=None,
            actual_target_price=None,
        ),
        rejection=rejection,
        uncertainty=None,
        transaction_provenance=provenance,
        diagnostic_codes=(diagnostic,),
    )


def _unknown_result(
    instruction: PaperExecutionInstruction,
    detail_code: str,
    *,
    request_id: str | None = None,
    provenance: TransactionProvenance | None = None,
) -> PaperExecutionResult:
    from backend.paper.execution import (
        BrokerUncertainty,
        ExecutionCorrelation,
        PaperExecutionInstruction,
        PaperExecutionOutcome,
        PaperExecutionResult,
        ProtectionConfirmation,
        ProtectionLegStatus,
        TransactionProvenance,
    )

    if type(instruction) is not PaperExecutionInstruction:
        raise OandaPracticeEntryMutationNormalizationError(
            "entry result requires a PaperExecutionInstruction"
        )
    selected_provenance = provenance or TransactionProvenance()
    if request_id is not None and selected_provenance.request_id is None:
        selected_provenance = TransactionProvenance(
            request_id=request_id,
            provider_transaction_ids=selected_provenance.provider_transaction_ids,
            batch_ids=selected_provenance.batch_ids,
            related_transaction_ids=selected_provenance.related_transaction_ids,
            last_transaction_id=selected_provenance.last_transaction_id,
        )
    return PaperExecutionResult(
        outcome=PaperExecutionOutcome.UNKNOWN,
        instruction=instruction,
        correlation=ExecutionCorrelation.for_attempt(instruction.attempt_id),
        fill=None,
        protection=ProtectionConfirmation(
            stop_loss_status=ProtectionLegStatus.NOT_ATTEMPTED,
            stop_loss=None,
            take_profit_status=ProtectionLegStatus.NOT_ATTEMPTED,
            take_profit=None,
            actual_target_price=None,
        ),
        rejection=None,
        uncertainty=BrokerUncertainty(detail_code, request_id),
        transaction_provenance=selected_provenance,
        diagnostic_codes=(detail_code,),
    )


def _matches_create(
    transaction: Mapping[str, Any],
    instruction: PaperExecutionInstruction,
    correlation: ExecutionCorrelation,
) -> bool:
    expected_units = _signed_quantity(instruction)
    client_extensions = transaction.get("clientExtensions")
    trade_extensions = transaction.get("tradeClientExtensions")
    if not isinstance(client_extensions, Mapping) or not isinstance(
        trade_extensions, Mapping
    ):
        return False
    client_extension_map = cast(Mapping[str, Any], client_extensions)
    trade_extension_map = cast(Mapping[str, Any], trade_extensions)
    return (
        _positive_id(transaction.get("id")) is not None
        and transaction.get("accountID") == instruction.account.account_id
        and transaction.get("type") == "MARKET_ORDER"
        and transaction.get("instrument") == "EUR_USD"
        and _decimal_value(transaction.get("units")) == expected_units
        and transaction.get("timeInForce") == "FOK"
        and transaction.get("positionFill") == "OPEN_ONLY"
        and _decimal_value(transaction.get("priceBound"))
        == instruction.approved_entry_price
        and client_extension_map.get("id") == correlation.client_order_id
        and client_extension_map.get("tag") == "atlas-paper-04"
        and trade_extension_map.get("id") == correlation.client_trade_id
        and (
            "clientOrderID" not in transaction
            or transaction.get("clientOrderID") == correlation.client_order_id
        )
    )


def _matches_cancel(
    transaction: Mapping[str, Any],
    instruction: PaperExecutionInstruction,
    create: Mapping[str, Any],
) -> bool:
    return (
        transaction.get("type") == "ORDER_CANCEL"
        and transaction.get("accountID") == instruction.account.account_id
        and transaction.get("orderID") == create.get("id")
    )


def _matches_reject(
    transaction: Mapping[str, Any],
    instruction: PaperExecutionInstruction,
    correlation: ExecutionCorrelation,
) -> bool:
    return (
        _positive_id(transaction.get("id")) is not None
        and transaction.get("type") == "ORDER_REJECT"
        and transaction.get("accountID") == instruction.account.account_id
        and _positive_id(transaction.get("orderID")) is not None
        and transaction.get("clientOrderID") == correlation.client_order_id
        and transaction.get("instrument") == "EUR_USD"
    )


def _rejection(transaction: Mapping[str, Any]) -> BrokerRejection:
    from backend.paper.execution import BrokerRejection

    order_id = _positive_id(transaction.get("orderID"))
    transaction_id = _positive_id(transaction.get("id"))
    return BrokerRejection(
        detail_code="BROKER_ORDER_REJECTED",
        broker_order_id=order_id,
        broker_transaction_id=transaction_id,
    )


def _signed_quantity(instruction: PaperExecutionInstruction) -> Decimal:
    return (
        instruction.requested_quantity
        if instruction.direction is Direction.LONG
        else -instruction.requested_quantity
    )


def _decimal_value(value: Any) -> Decimal | None:
    try:
        return parse_decimal(value)
    except OandaPrimitiveError:
        return None


def _positive_id(value: Any) -> str | None:
    if type(value) is not str:
        return None
    try:
        parsed = parse_transaction_id(value)
    except OandaPrimitiveError:
        return None
    return parsed if any(character != "0" for character in parsed) else None


def _timestamp(value: Any) -> datetime | None:
    if type(value) is not str:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(UTC)


def _transaction(payload: Mapping[str, Any], key: str) -> Mapping[str, Any] | None:
    value = payload.get(key)
    return cast(Mapping[str, Any], value) if isinstance(value, Mapping) else None


def _has_malformed_transaction_shape(payload: Mapping[str, Any]) -> bool:
    return any(
        key in payload
        and payload[key] is not None
        and not isinstance(payload[key], Mapping)
        for key in (
            "orderCreateTransaction",
            "orderFillTransaction",
            "orderCancelTransaction",
            "orderRejectTransaction",
            "orderReissueTransaction",
            "orderReissueRejectTransaction",
        )
    )


def _provenance(
    payload: Mapping[str, Any], *, request_id: str | None
) -> TransactionProvenance:
    from backend.paper.execution import TransactionProvenance

    provider_ids: list[str] = []
    batch_ids: list[str] = []
    for key in (
        "orderCreateTransaction",
        "orderFillTransaction",
        "orderCancelTransaction",
        "orderRejectTransaction",
        "orderReissueTransaction",
        "orderReissueRejectTransaction",
        "takeProfitOrderTransaction",
        "takeProfitOrderRejectTransaction",
    ):
        transaction = _transaction(payload, key)
        if transaction is None:
            continue
        transaction_id = _positive_id(transaction.get("id"))
        if transaction_id is not None:
            provider_ids.append(transaction_id)
        batch_id = _positive_id(transaction.get("batchID"))
        if batch_id is not None:
            batch_ids.append(batch_id)
    related = payload.get("relatedTransactionIDs")
    related_ids = (
        tuple(
            cast(str, value)
            for value in cast(list[Any], related)
            if _positive_id(value) is not None
        )[:64]
        if isinstance(related, list)
        else ()
    )
    return TransactionProvenance(
        request_id=_safe_request_id(request_id),
        provider_transaction_ids=tuple(dict.fromkeys(provider_ids))[:64],
        batch_ids=tuple(dict.fromkeys(batch_ids))[:64],
        related_transaction_ids=tuple(dict.fromkeys(related_ids)),
        last_transaction_id=_positive_id(payload.get("lastTransactionID")),
    )


def _safe_request_id(value: Any) -> str | None:
    if type(value) is not str or not value or len(value) > 128:
        return None
    return value


def _unwrap_readback_object(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise OandaPracticeEntryReadbackError(
            "OANDA entry readback response has an invalid object"
        )
    return cast(Mapping[str, Any], value)


def _unwrap_transaction(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    for key in (
        "orderFillTransaction",
        "orderCancelTransaction",
        "orderRejectTransaction",
    ):
        if key in payload:
            return _unwrap_readback_object(payload, key)
    return payload


def _matches_readback_trade(
    trade_value: Mapping[str, Any],
    instruction: PaperExecutionInstruction,
    fill: BrokerFillFacts,
) -> bool:
    candidate = trade_value.get("trade")
    trade: Mapping[str, Any] = trade_value
    if isinstance(candidate, Mapping):
        trade = cast(Mapping[str, Any], candidate)
    client_extensions = trade.get("clientExtensions")
    client_extension_map = (
        cast(Mapping[str, Any], client_extensions)
        if isinstance(client_extensions, Mapping)
        else None
    )
    return (
        _positive_id(trade.get("id")) == fill.broker_trade_id
        and trade.get("accountID") == instruction.account.account_id
        and trade.get("instrument") == "EUR_USD"
        and trade.get("state") == "OPEN"
        and _decimal_value(trade.get("currentUnits")) == fill.signed_units
        and _decimal_value(trade.get("price")) == fill.price
        and client_extension_map is not None
        and client_extension_map.get("id") == instruction.correlation.client_trade_id
    )


class OandaPracticeProtectionNormalizationError(OandaNormalizationError):
    """A protection response cannot become bounded broker facts."""


def translate_oanda_practice_take_profit(
    instruction: PaperExecutionInstruction,
    execution_instrument: OandaPracticeExecutionInstrument,
    actual_target: Decimal,
    *,
    correlation: ExecutionCorrelation | None = None,
) -> dict[str, Any]:
    """Translate one exact actual-Fill target to a dependent-order payload.

    The returned payload intentionally has exactly one top-level field.  In
    particular, omitting ``stopLoss`` is what preserves the already confirmed
    ordinary Stop Loss on the Trade.
    """
    from backend.paper.execution import ExecutionCorrelation, PaperExecutionInstruction

    if type(instruction) is not PaperExecutionInstruction:
        raise OandaPracticeProtectionNormalizationError(
            "protection translation requires a PaperExecutionInstruction"
        )
    if type(execution_instrument) is not OandaPracticeExecutionInstrument:
        raise OandaPracticeProtectionNormalizationError(
            "protection translation requires observed execution instrument metadata"
        )
    expected_correlation = instruction.correlation
    if correlation is not None and (
        type(correlation) is not ExecutionCorrelation
        or correlation != expected_correlation
    ):
        raise OandaPracticeProtectionNormalizationError(
            "protection correlation does not match attempt_id"
        )
    if (
        instruction.account.provider is not Provider.OANDA
        or instruction.account.environment != "PRACTICE"
        or instruction.account.base_currency != "USD"
        or instruction.instrument is not Instrument.EUR_USD
        or execution_instrument.provider_instrument != "EUR_USD"
        or instruction.display_precision != execution_instrument.display_precision
    ):
        raise OandaPracticeProtectionNormalizationError(
            "protection translation received unsupported account or instrument"
        )
    try:
        serialized_target = execution_instrument.serialize_price(actual_target)
    except OandaNormalizationError as error:
        raise OandaPracticeProtectionNormalizationError(
            "actual target is not exactly representable"
        ) from error
    selected_correlation = expected_correlation if correlation is None else correlation
    return {
        "takeProfit": {
            "price": serialized_target,
            "timeInForce": "GTC",
            "clientExtensions": {
                "id": selected_correlation.client_take_profit_order_id,
            },
        }
    }


def translate_take_profit_order(
    instruction: PaperExecutionInstruction,
    execution_instrument: OandaPracticeExecutionInstrument,
    actual_target: Decimal,
    *,
    correlation: ExecutionCorrelation | None = None,
) -> Mapping[str, Any]:
    """Compatibility-named public seam for dependent target translation."""
    return translate_oanda_practice_take_profit(
        instruction,
        execution_instrument,
        actual_target,
        correlation=correlation,
    )


def resolve_oanda_practice_actual_target(
    instruction: PaperExecutionInstruction,
    fill: BrokerFillFacts,
) -> Decimal:
    """Resolve the immutable Strategy target from broker-confirmed Fill facts."""
    from backend.paper.execution import BrokerFillFacts, PaperExecutionInstruction

    if type(instruction) is not PaperExecutionInstruction:
        raise OandaPracticeProtectionNormalizationError(
            "actual target requires a PaperExecutionInstruction"
        )
    if type(fill) is not BrokerFillFacts:
        raise OandaPracticeProtectionNormalizationError(
            "actual target requires broker Fill facts"
        )
    target_proposal = instruction.strategy_decision.target
    if target_proposal is None:  # The instruction contract normally prevents this.
        raise OandaPracticeProtectionNormalizationError(
            "actual target requires a Strategy TargetProposal"
        )
    try:
        actual_target = target_proposal.resolve(
            fill.price,
            instruction.stop_price,
            instruction.direction,
        )
    except (TypeError, ValueError) as error:
        raise OandaPracticeProtectionNormalizationError(
            "actual target geometry is invalid"
        ) from error
    if instruction.direction is Direction.LONG:
        valid_geometry = actual_target > fill.price > instruction.stop_price
    else:
        valid_geometry = actual_target < fill.price < instruction.stop_price
    if not valid_geometry:
        raise OandaPracticeProtectionNormalizationError(
            "actual target geometry is invalid"
        )
    return actual_target


@dataclass(frozen=True, slots=True)
class _ProtectionOrderObservation:
    status: ProtectionLegStatus
    order: BrokerProtectionOrder | None


@dataclass(frozen=True, slots=True)
class _TargetMutationObservation:
    status: Literal["CONFIRMED", "REJECTED", "UNKNOWN"]
    order: BrokerProtectionOrder | None
    rejection: BrokerRejection | None
    provenance: TransactionProvenance
    detail_code: str


class OandaPracticeProtectionCompletion:
    """Complete protection after a broker-confirmed actual entry Fill.

    The adapter owns no recovery mutation.  It reads Trade detail, submits at
    most one dependent Take Profit PUT, and optionally performs the one final
    Trade-detail read required to prove both protections.
    """

    def __init__(
        self,
        requester: OandaProtectionMutationRequester,
        readback: OandaProtectionReadbackReader,
    ) -> None:
        self._requester = requester
        self._readback = readback
        self._results: dict[UUID, PaperExecutionResult] = {}

    def complete(
        self,
        entry_result: PaperExecutionResult,
        execution_instrument: OandaPracticeExecutionInstrument,
    ) -> PaperExecutionResult:
        """Confirm Stop, resolve actual target, and complete one target PUT."""
        from backend.paper.execution import (
            PaperExecutionInstruction,
            PaperExecutionOutcome,
            PaperExecutionResult,
            ProtectionLegStatus,
        )

        if type(entry_result) is not PaperExecutionResult:
            raise OandaPracticeProtectionNormalizationError(
                "protection completion requires a PaperExecutionResult"
            )
        if type(execution_instrument) is not OandaPracticeExecutionInstrument:
            raise OandaPracticeProtectionNormalizationError(
                "protection completion requires observed execution instrument metadata"
            )
        cached = self._results.get(entry_result.instruction.attempt_id)
        if cached is not None:
            return cached
        if entry_result.outcome is PaperExecutionOutcome.FILLED_PROTECTED:
            self._results[entry_result.instruction.attempt_id] = entry_result
            return entry_result
        if (
            entry_result.outcome
            is not PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE
            or entry_result.fill is None
        ):
            return entry_result

        instruction = entry_result.instruction
        if type(instruction) is not PaperExecutionInstruction:
            raise OandaPracticeProtectionNormalizationError(
                "protection result has an invalid instruction"
            )
        fill = entry_result.fill
        try:
            trade_value = self._readback.read_trade(fill.broker_trade_id)
        except Exception:
            result = _protection_incomplete(
                entry_result,
                stop_loss_status=ProtectionLegStatus.UNKNOWN,
                stop_loss=None,
                take_profit_status=ProtectionLegStatus.NOT_ATTEMPTED,
                take_profit=None,
                actual_target=None,
                detail_code="STOP_CONFIRMATION_READ_FAILED",
            )
            self._results[instruction.attempt_id] = result
            return result

        trade = _trade_detail(trade_value)
        if trade is None or not _matches_protection_trade(trade, instruction, fill):
            result = _protection_incomplete(
                entry_result,
                stop_loss_status=ProtectionLegStatus.UNKNOWN,
                stop_loss=None,
                take_profit_status=ProtectionLegStatus.NOT_ATTEMPTED,
                take_profit=None,
                actual_target=None,
                detail_code="STOP_CONFIRMATION_UNPROVEN",
            )
            self._results[instruction.attempt_id] = result
            return result

        stop_observation = _observe_protection_order(
            trade,
            field_name="stopLossOrder",
            expected_type="STOP_LOSS",
            expected_trade_id=fill.broker_trade_id,
            expected_client_id=instruction.correlation.client_stop_loss_order_id,
            expected_price=instruction.stop_price,
            expected_account_id=instruction.account.account_id,
        )
        if stop_observation.status is not ProtectionLegStatus.CONFIRMED:
            result = _protection_incomplete(
                entry_result,
                stop_loss_status=stop_observation.status,
                stop_loss=stop_observation.order,
                take_profit_status=ProtectionLegStatus.NOT_ATTEMPTED,
                take_profit=None,
                actual_target=None,
                detail_code="STOP_CONFIRMATION_UNPROVEN",
            )
            self._results[instruction.attempt_id] = result
            return result

        try:
            actual_target = resolve_oanda_practice_actual_target(instruction, fill)
        except OandaPracticeProtectionNormalizationError:
            result = _protection_incomplete(
                entry_result,
                stop_loss_status=ProtectionLegStatus.CONFIRMED,
                stop_loss=stop_observation.order,
                take_profit_status=ProtectionLegStatus.NOT_ATTEMPTED,
                take_profit=None,
                actual_target=None,
                detail_code="TARGET_GEOMETRY_INVALID",
            )
            self._results[instruction.attempt_id] = result
            return result
        try:
            payload = translate_oanda_practice_take_profit(
                instruction, execution_instrument, actual_target
            )
        except OandaPracticeProtectionNormalizationError:
            result = _protection_incomplete(
                entry_result,
                stop_loss_status=ProtectionLegStatus.CONFIRMED,
                stop_loss=stop_observation.order,
                take_profit_status=ProtectionLegStatus.NOT_ATTEMPTED,
                take_profit=None,
                actual_target=actual_target,
                detail_code="TARGET_PRECISION_UNREPRESENTABLE",
            )
            self._results[instruction.attempt_id] = result
            return result

        try:
            response = self._requester.put_trade_orders(
                instruction.account.account_id,
                fill.broker_trade_id,
                payload,
            )
        except Exception:
            result = _protection_incomplete(
                entry_result,
                stop_loss_status=ProtectionLegStatus.CONFIRMED,
                stop_loss=stop_observation.order,
                take_profit_status=ProtectionLegStatus.UNKNOWN,
                take_profit=None,
                actual_target=actual_target,
                uncertainty_detail="TARGET_MUTATION_TRANSPORT_UNCERTAIN",
                detail_code="TARGET_MUTATION_TRANSPORT_UNCERTAIN",
            )
            self._results[instruction.attempt_id] = result
            return result

        mutation = _normalize_target_mutation_response(
            instruction,
            fill.broker_trade_id,
            actual_target,
            response,
        )
        if mutation.status == "REJECTED":
            result = _protection_incomplete(
                entry_result,
                stop_loss_status=ProtectionLegStatus.CONFIRMED,
                stop_loss=stop_observation.order,
                take_profit_status=ProtectionLegStatus.REJECTED,
                take_profit=mutation.order,
                actual_target=actual_target,
                rejection=mutation.rejection,
                provenance=mutation.provenance,
                detail_code=mutation.detail_code,
            )
            self._results[instruction.attempt_id] = result
            return result
        if mutation.status != "CONFIRMED":
            result = _protection_incomplete(
                entry_result,
                stop_loss_status=ProtectionLegStatus.CONFIRMED,
                stop_loss=stop_observation.order,
                take_profit_status=ProtectionLegStatus.UNKNOWN,
                take_profit=None,
                actual_target=actual_target,
                uncertainty_detail=mutation.detail_code,
                provenance=mutation.provenance,
                detail_code=mutation.detail_code,
            )
            self._results[instruction.attempt_id] = result
            return result

        try:
            final_value = self._readback.read_trade(fill.broker_trade_id)
        except Exception:
            final_value = None
        final_trade = _trade_detail(final_value)
        if final_trade is None or not _matches_protection_trade(
            final_trade, instruction, fill
        ):
            result = _protection_incomplete(
                entry_result,
                stop_loss_status=ProtectionLegStatus.CONFIRMED,
                stop_loss=stop_observation.order,
                take_profit_status=ProtectionLegStatus.UNKNOWN,
                take_profit=None,
                actual_target=actual_target,
                uncertainty_detail="FINAL_PROTECTION_READBACK_UNPROVEN",
                provenance=mutation.provenance,
                detail_code="FINAL_PROTECTION_READBACK_UNPROVEN",
            )
            self._results[instruction.attempt_id] = result
            return result

        final_stop = _observe_protection_order(
            final_trade,
            field_name="stopLossOrder",
            expected_type="STOP_LOSS",
            expected_trade_id=fill.broker_trade_id,
            expected_client_id=instruction.correlation.client_stop_loss_order_id,
            expected_price=instruction.stop_price,
            expected_account_id=instruction.account.account_id,
        )
        final_target = _observe_protection_order(
            final_trade,
            field_name="takeProfitOrder",
            expected_type="TAKE_PROFIT",
            expected_trade_id=fill.broker_trade_id,
            expected_client_id=instruction.correlation.client_take_profit_order_id,
            expected_price=actual_target,
            expected_account_id=instruction.account.account_id,
            expected_client_trade_id=instruction.correlation.client_trade_id,
            require_pending=True,
        )
        if (
            final_stop.status is not ProtectionLegStatus.CONFIRMED
            or final_target.status is not ProtectionLegStatus.CONFIRMED
        ):
            result = _protection_incomplete(
                entry_result,
                stop_loss_status=final_stop.status,
                stop_loss=final_stop.order,
                take_profit_status=final_target.status,
                take_profit=final_target.order,
                actual_target=actual_target,
                provenance=mutation.provenance,
                detail_code="FINAL_PROTECTION_UNPROVEN",
            )
            self._results[instruction.attempt_id] = result
            return result

        result = _protection_complete(
            entry_result,
            stop_loss=final_stop.order,
            take_profit=final_target.order,
            actual_target=actual_target,
            provenance=mutation.provenance,
        )
        self._results[instruction.attempt_id] = result
        return result

    complete_protection = complete


def complete_oanda_practice_protection(
    entry_result: PaperExecutionResult,
    execution_instrument: OandaPracticeExecutionInstrument,
    requester: OandaProtectionMutationRequester,
    readback: OandaProtectionReadbackReader,
) -> PaperExecutionResult:
    """Functional public seam for completing one entry Fill's protection."""
    return OandaPracticeProtectionCompletion(requester, readback).complete(
        entry_result, execution_instrument
    )


def _protection_incomplete(
    entry_result: PaperExecutionResult,
    *,
    stop_loss_status: ProtectionLegStatus,
    stop_loss: BrokerProtectionOrder | None,
    take_profit_status: ProtectionLegStatus,
    take_profit: BrokerProtectionOrder | None,
    actual_target: Decimal | None,
    detail_code: str,
    rejection: BrokerRejection | None = None,
    uncertainty_detail: str | None = None,
    provenance: TransactionProvenance | None = None,
) -> PaperExecutionResult:
    from backend.paper.execution import (
        BrokerUncertainty,
        PaperExecutionOutcome,
        ProtectionConfirmation,
    )

    diagnostic_codes = tuple(
        dict.fromkeys((*entry_result.diagnostic_codes, detail_code))
    )
    selected_uncertainty = (
        BrokerUncertainty(uncertainty_detail)
        if uncertainty_detail is not None
        else entry_result.uncertainty
    )
    return replace(
        entry_result,
        outcome=PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE,
        protection=ProtectionConfirmation(
            stop_loss_status=stop_loss_status,
            stop_loss=stop_loss,
            take_profit_status=take_profit_status,
            take_profit=take_profit,
            actual_target_price=actual_target,
        ),
        rejection=rejection,
        uncertainty=selected_uncertainty,
        transaction_provenance=_merge_provenance(
            entry_result.transaction_provenance, provenance
        ),
        diagnostic_codes=diagnostic_codes,
    )


def _protection_complete(
    entry_result: PaperExecutionResult,
    *,
    stop_loss: BrokerProtectionOrder | None,
    take_profit: BrokerProtectionOrder | None,
    actual_target: Decimal,
    provenance: TransactionProvenance,
) -> PaperExecutionResult:
    from backend.paper.execution import (
        PaperExecutionOutcome,
        ProtectionConfirmation,
        ProtectionLegStatus,
    )

    return replace(
        entry_result,
        outcome=PaperExecutionOutcome.FILLED_PROTECTED,
        protection=ProtectionConfirmation(
            stop_loss_status=ProtectionLegStatus.CONFIRMED,
            stop_loss=stop_loss,
            take_profit_status=ProtectionLegStatus.CONFIRMED,
            take_profit=take_profit,
            actual_target_price=actual_target,
        ),
        uncertainty=None,
        transaction_provenance=_merge_provenance(
            entry_result.transaction_provenance, provenance
        ),
        diagnostic_codes=tuple(
            dict.fromkeys(
                (*entry_result.diagnostic_codes, "PROTECTION_FINAL_CONFIRMED")
            )
        ),
    )


def _merge_provenance(
    first: TransactionProvenance,
    second: TransactionProvenance | None,
) -> TransactionProvenance:
    from backend.paper.execution import TransactionProvenance

    if second is None:
        return first
    return TransactionProvenance(
        request_id=second.request_id or first.request_id,
        provider_transaction_ids=tuple(
            dict.fromkeys(
                (*first.provider_transaction_ids, *second.provider_transaction_ids)
            )
        )[:64],
        batch_ids=tuple(dict.fromkeys((*first.batch_ids, *second.batch_ids)))[:64],
        related_transaction_ids=tuple(
            dict.fromkeys(
                (*first.related_transaction_ids, *second.related_transaction_ids)
            )
        )[:64],
        last_transaction_id=second.last_transaction_id or first.last_transaction_id,
    )


def _trade_detail(value: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    nested = value.get("trade")
    if isinstance(nested, Mapping):
        return cast(Mapping[str, Any], nested)
    return value


def _matches_protection_trade(
    trade: Mapping[str, Any],
    instruction: PaperExecutionInstruction,
    fill: BrokerFillFacts,
) -> bool:
    client_extensions = trade.get("clientExtensions")
    if not isinstance(client_extensions, Mapping):
        return False
    client_extension_map = cast(Mapping[str, Any], client_extensions)
    return (
        _positive_id(trade.get("id")) == fill.broker_trade_id
        and trade.get("accountID") == instruction.account.account_id
        and trade.get("instrument") == "EUR_USD"
        and trade.get("state") == "OPEN"
        and _decimal_value(trade.get("initialUnits")) == fill.signed_units
        and _decimal_value(trade.get("currentUnits")) == fill.signed_units
        and _decimal_value(trade.get("price")) == fill.price
        and client_extension_map.get("id") == instruction.correlation.client_trade_id
    )


def _dependent_order_candidates(
    trade: Mapping[str, Any], field_name: str, expected_type: str
) -> list[Mapping[str, Any]] | None:
    if field_name in trade:
        value = trade.get(field_name)
        if not isinstance(value, Mapping):
            return None
        return [cast(Mapping[str, Any], value)]
    orders = trade.get("orders")
    if not isinstance(orders, list):
        return None
    candidates: list[Mapping[str, Any]] = []
    for value in cast(list[Any], orders):
        if not isinstance(value, Mapping):
            continue
        candidate = cast(Mapping[str, Any], value)
        if candidate.get("type") == expected_type:
            candidates.append(candidate)
    return candidates


def _observe_protection_order(
    trade: Mapping[str, Any],
    *,
    field_name: str,
    expected_type: str,
    expected_trade_id: str,
    expected_client_id: str,
    expected_price: Decimal,
    expected_account_id: str,
    expected_client_trade_id: str | None = None,
    require_pending: bool = False,
) -> _ProtectionOrderObservation:
    from backend.paper.execution import ProtectionLegStatus

    candidates = _dependent_order_candidates(trade, field_name, expected_type)
    if candidates is None or len(candidates) != 1:
        return _ProtectionOrderObservation(ProtectionLegStatus.UNKNOWN, None)
    candidate = candidates[0]
    order = _broker_protection_order(candidate)
    if order is None:
        return _ProtectionOrderObservation(ProtectionLegStatus.UNKNOWN, None)
    client_extensions = candidate.get("clientExtensions")
    if not isinstance(client_extensions, Mapping):
        return _ProtectionOrderObservation(ProtectionLegStatus.UNKNOWN, None)
    if (
        candidate.get("accountID") not in (None, expected_account_id)
        or candidate.get("type") != expected_type
        or candidate.get("tradeID") != expected_trade_id
        or cast(Mapping[str, Any], client_extensions).get("id") != expected_client_id
        or _decimal_value(candidate.get("price")) != expected_price
        or candidate.get("timeInForce") != "GTC"
        or (
            expected_client_trade_id is not None
            and candidate.get("clientTradeID") not in (None, expected_client_trade_id)
        )
    ):
        return _ProtectionOrderObservation(ProtectionLegStatus.UNKNOWN, None)
    if order.state == "PENDING":
        return _ProtectionOrderObservation(ProtectionLegStatus.CONFIRMED, order)
    if order.state in {"CANCELLED", "FILLED", "REJECTED"}:
        return _ProtectionOrderObservation(ProtectionLegStatus.REJECTED, order)
    return _ProtectionOrderObservation(ProtectionLegStatus.UNKNOWN, order)


def _broker_protection_order(
    candidate: Mapping[str, Any],
) -> BrokerProtectionOrder | None:
    from backend.paper.execution import BrokerProtectionOrder

    order_id = _positive_id(candidate.get("id"))
    client_extensions = candidate.get("clientExtensions")
    client_id = (
        cast(Mapping[str, Any], client_extensions).get("id")
        if isinstance(client_extensions, Mapping)
        else None
    )
    price = _decimal_value(candidate.get("price"))
    state_value = candidate.get("state")
    if (
        order_id is None
        or type(client_id) is not str
        or price is None
        or type(state_value) is not str
    ):
        return None
    state = state_value
    try:
        return BrokerProtectionOrder(order_id, client_id, price, state)
    except ValueError:
        return None


def _normalize_target_mutation_response(
    instruction: PaperExecutionInstruction,
    trade_id: str,
    actual_target: Decimal,
    response: OandaMutationResponse | Mapping[str, Any],
) -> _TargetMutationObservation:
    from backend.paper.execution import (
        BrokerProtectionOrder,
        BrokerRejection,
        TransactionProvenance,
    )

    if isinstance(response, OandaMutationResponse):
        request_id = _safe_request_id(response.request_id)
        payload_value = response.payload
        if not response.json_valid or not isinstance(payload_value, Mapping):
            return _TargetMutationObservation(
                "UNKNOWN",
                None,
                None,
                TransactionProvenance(request_id=request_id),
                "TARGET_MUTATION_MALFORMED_RESPONSE",
            )
        payload = cast(Mapping[str, Any], payload_value)
        if not 200 <= response.status_code < 300:
            return _TargetMutationObservation(
                "UNKNOWN",
                None,
                None,
                _provenance(payload, request_id=request_id),
                "TARGET_MUTATION_UNCERTAIN",
            )
    elif type(response) is dict:
        request_id = None
        payload = cast(Mapping[str, Any], response)
    else:
        return _TargetMutationObservation(
            "UNKNOWN",
            None,
            None,
            TransactionProvenance(),
            "TARGET_MUTATION_MALFORMED_RESPONSE",
        )

    create = _transaction(payload, "takeProfitOrderTransaction")
    reject = _transaction(payload, "takeProfitOrderRejectTransaction")
    if create is not None and reject is not None:
        return _TargetMutationObservation(
            "UNKNOWN",
            None,
            None,
            _provenance(payload, request_id=request_id),
            "TARGET_MUTATION_CONTRADICTORY_TERMINALS",
        )
    provenance = _provenance(payload, request_id=request_id)
    if reject is not None:
        if not _matches_target_reject(reject, instruction, trade_id):
            return _TargetMutationObservation(
                "UNKNOWN", None, None, provenance, "TARGET_MUTATION_UNCERTAIN"
            )
        return _TargetMutationObservation(
            "REJECTED",
            None,
            BrokerRejection(
                detail_code="TARGET_BROKER_REJECTED",
                broker_order_id=_positive_id(reject.get("orderID")),
                broker_transaction_id=_positive_id(reject.get("id")),
            ),
            provenance,
            "TARGET_BROKER_REJECTED",
        )
    if create is None or not _matches_target_create(
        create, instruction, trade_id, actual_target
    ):
        return _TargetMutationObservation(
            "UNKNOWN", None, None, provenance, "TARGET_MUTATION_UNCERTAIN"
        )
    target_id = _positive_id(create.get("id"))
    if target_id is None:
        return _TargetMutationObservation(
            "UNKNOWN", None, None, provenance, "TARGET_MUTATION_MALFORMED_RESPONSE"
        )
    return _TargetMutationObservation(
        "CONFIRMED",
        BrokerProtectionOrder(
            target_id,
            instruction.correlation.client_take_profit_order_id,
            actual_target,
            "PENDING",
        ),
        None,
        provenance,
        "TARGET_MUTATION_CONFIRMED",
    )


def _matches_target_create(
    transaction: Mapping[str, Any],
    instruction: PaperExecutionInstruction,
    trade_id: str,
    actual_target: Decimal,
) -> bool:
    client_extensions = transaction.get("clientExtensions")
    if not isinstance(client_extensions, Mapping):
        return False
    return (
        transaction.get("accountID") == instruction.account.account_id
        and transaction.get("type") == "TAKE_PROFIT_ORDER"
        and transaction.get("tradeID") == trade_id
        and transaction.get("clientTradeID")
        in (None, instruction.correlation.client_trade_id)
        and cast(Mapping[str, Any], client_extensions).get("id")
        == instruction.correlation.client_take_profit_order_id
        and _decimal_value(transaction.get("price")) == actual_target
        and transaction.get("timeInForce") == "GTC"
    )


def _matches_target_reject(
    transaction: Mapping[str, Any],
    instruction: PaperExecutionInstruction,
    trade_id: str,
) -> bool:
    return (
        _positive_id(transaction.get("id")) is not None
        and transaction.get("accountID") == instruction.account.account_id
        and transaction.get("type") == "TAKE_PROFIT_ORDER_REJECT"
        and transaction.get("tradeID") == trade_id
        and transaction.get("clientTradeID")
        in (None, instruction.correlation.client_trade_id)
    )


__all__ = [
    "OandaEntryMutationRequester",
    "OandaEntryReadbackReader",
    "OandaProtectionMutationRequester",
    "OandaProtectionReadbackReader",
    "OandaPracticeProtectionCompletion",
    "OandaPracticeProtectionNormalizationError",
    "OandaTradeProtectionReader",
    "OandaPracticeEntryMutation",
    "OandaPracticeEntryMutationNormalizationError",
    "OandaPracticeEntryReadbackError",
    "OandaPracticeEntryReadbackReader",
    "OandaPracticeEntryTranslationError",
    "OandaPracticeEntryTranslator",
    "normalize_entry_response",
    "normalize_oanda_practice_entry_response",
    "complete_oanda_practice_protection",
    "resolve_oanda_practice_actual_target",
    "translate_take_profit_order",
    "translate_oanda_practice_take_profit",
    "translate_entry_order",
    "translate_oanda_practice_market_order",
]
