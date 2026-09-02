"""OANDA Practice normalization for the bounded PAPER read-only seam."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, cast
from urllib.parse import quote

import httpx
from pydantic import SecretStr

from backend.domain import Direction, Instrument
from backend.paper.execution import (
    BrokerFillFacts,
    BrokerProtectionOrder,
    BrokerRejection,
    ProtectionConfirmation,
    ProtectionLegStatus,
)
from backend.paper.persistence_contracts import (
    PaperBrokerObservation,
    PaperObservationObjectKind,
    PaperObservationReadKind,
)
from backend.paper.reconciliation import (
    PaperReconciliationContext,
    PaperReconciliationProvider,
    PaperReconciliationRead,
    PaperReconciliationReadState,
    PaperReconciliationTransaction,
)

from .account import is_valid_oanda_practice_account_id
from .execution_account import normalize_oanda_practice_execution_account_snapshot
from .primitives import OandaPrimitiveError, parse_decimal, parse_transaction_id
from .request import OandaObservationRequester, OandaObservationResponse, validate_token
from .source import OandaNormalizationError, OandaRequestError

_ORDER_PATH = "/v3/accounts/{account_id}/orders/@{client_order_id}"
_TRANSACTION_PATH = "/v3/accounts/{account_id}/transactions/{transaction_id}"
_TRADE_PATH = "/v3/accounts/{account_id}/trades/{trade_id}"
_ACCOUNT_PATH = "/v3/accounts/{account_id}"
_RANGE_PATH = "/v3/accounts/{account_id}/transactions/idrange"
_MAX_RANGE_ITEMS = 64


class OandaReconciliationNormalizationError(OandaNormalizationError):
    """A read-only OANDA reconciliation response is not safely interpretable."""


Clock = Callable[[], datetime]


class OandaPracticeReconciliationReader(PaperReconciliationProvider):
    """Normalize the finite OANDA reads used by one PAPER reconciliation pass."""

    def __init__(
        self,
        token: SecretStr | None,
        account_id: str,
        *,
        client: httpx.Client | None = None,
        transport: httpx.BaseTransport | None = None,
        connect_timeout_seconds: float = 5.0,
        read_timeout_seconds: float = 20.0,
        clock: Clock | None = None,
    ) -> None:
        if not is_valid_oanda_practice_account_id(account_id):
            raise OandaReconciliationNormalizationError("OANDA account ID is invalid")
        self._account_id = account_id
        self._requester = OandaObservationRequester(
            token,
            client=client,
            transport=transport,
            connect_timeout_seconds=connect_timeout_seconds,
            read_timeout_seconds=read_timeout_seconds,
        )
        self._token = token
        self._clock = clock or (lambda: datetime.now(UTC))

    def read_order(
        self, context: PaperReconciliationContext
    ) -> PaperReconciliationRead:
        self._validate_context(context)
        path = _ORDER_PATH.format(
            account_id=quote(self._account_id, safe="-"),
            client_order_id=quote(context.client_order_id, safe="-_@"),
        )
        response = self._get(path, "reconciliation Order")
        if response is None or response.payload is None:
            return self._not_found(
                context,
                PaperObservationReadKind.ORDER_DETAIL,
                PaperObservationObjectKind.ORDER,
                request_id=response.request_id if response is not None else None,
            )
        payload = _object(response.payload, "reconciliation Order")
        order = _object_or_none(payload.get("order")) or payload
        order_id = _positive_id(order.get("id"))
        account_id = order.get("accountID")
        instrument = order.get("instrument")
        client_order_id = _client_order_id(order)
        attributable = (
            order_id is not None
            and account_id == context.provider_account_id
            and instrument == context.instrument
            and client_order_id == context.client_order_id
            and _order_matches_request(context, order)
        )
        state_value = order.get("state")
        state = _order_state(state_value)
        terminal_id: str | None = None
        if state is PaperReconciliationReadState.FILLED:
            terminal_id = _positive_id(order.get("fillingTransactionID"))
        elif state is PaperReconciliationReadState.CANCELLED:
            terminal_id = _positive_id(order.get("cancellingTransactionID"))
        elif state is PaperReconciliationReadState.REJECTED:
            terminal_id = _positive_id(
                order.get("rejectingTransactionID")
                or order.get("rejectionTransactionID")
            )
        if (
            state
            in (
                PaperReconciliationReadState.FILLED,
                PaperReconciliationReadState.CANCELLED,
                PaperReconciliationReadState.REJECTED,
            )
            and terminal_id is None
        ):
            attributable = False
            state = PaperReconciliationReadState.CONFLICT
        facts = {
            "found": True,
            "account_id": account_id if isinstance(account_id, str) else None,
            "instrument": instrument if isinstance(instrument, str) else None,
            "order_id": order_id,
            "client_order_id": client_order_id,
            "type": order.get("type") if isinstance(order.get("type"), str) else None,
            "state": state_value if isinstance(state_value, str) else None,
            "filling_transaction_id": terminal_id
            if state is PaperReconciliationReadState.FILLED
            else None,
            "cancelling_transaction_id": terminal_id
            if state is PaperReconciliationReadState.CANCELLED
            else None,
            "rejecting_transaction_id": terminal_id
            if state is PaperReconciliationReadState.REJECTED
            else None,
            "time_in_force": order.get("timeInForce")
            if isinstance(order.get("timeInForce"), str)
            else None,
            "position_fill": order.get("positionFill")
            if isinstance(order.get("positionFill"), str)
            else None,
            "price_bound": _decimal_text(order.get("priceBound")),
        }
        observation = self._observation(
            context,
            PaperObservationReadKind.ORDER_DETAIL,
            PaperObservationObjectKind.ORDER,
            facts,
            provider_order_id=order_id,
            client_order_id=client_order_id,
            request_id=response.request_id,
            provider_observed_at=_timestamp_or_none(order.get("createTime")),
        )
        return PaperReconciliationRead(
            observation=observation,
            state=state,
            terminal_transaction_id=terminal_id,
            attributable=attributable,
        )

    def read_transaction(
        self, context: PaperReconciliationContext, transaction_id: str
    ) -> PaperReconciliationRead:
        self._validate_context(context)
        normalized_id = _positive_id(transaction_id)
        if normalized_id is None:
            raise OandaReconciliationNormalizationError("transaction ID is invalid")
        path = _TRANSACTION_PATH.format(
            account_id=quote(self._account_id, safe="-"),
            transaction_id=quote(normalized_id, safe="-"),
        )
        response = self._get(path, "reconciliation transaction")
        if response is None or response.payload is None:
            return self._not_found(
                context,
                PaperObservationReadKind.TRANSACTION_DETAIL,
                PaperObservationObjectKind.TRANSACTION,
                provider_transaction_id=normalized_id,
                request_id=response.request_id if response is not None else None,
            )
        payload = _object(response.payload, "reconciliation transaction")
        transaction = _unwrap_transaction(payload)
        return self._transaction_read(
            context,
            transaction,
            response.request_id,
            PaperObservationReadKind.TRANSACTION_DETAIL,
            expected_transaction_id=normalized_id,
        )

    def read_trade(
        self, context: PaperReconciliationContext, trade_id: str
    ) -> PaperReconciliationRead:
        self._validate_context(context)
        normalized_id = _positive_id(trade_id)
        if normalized_id is None:
            raise OandaReconciliationNormalizationError("Trade ID is invalid")
        path = _TRADE_PATH.format(
            account_id=quote(self._account_id, safe="-"),
            trade_id=quote(normalized_id, safe="-"),
        )
        response = self._get(path, "reconciliation Trade")
        if response is None or response.payload is None:
            return self._not_found(
                context,
                PaperObservationReadKind.TRADE_DETAIL,
                PaperObservationObjectKind.TRADE,
                provider_trade_id=normalized_id,
                request_id=response.request_id if response is not None else None,
            )
        payload = _object(response.payload, "reconciliation Trade")
        trade = _object_or_none(payload.get("trade")) or payload
        return self._trade_read(
            context, trade, response.request_id, expected_trade_id=normalized_id
        )

    def read_account(
        self, context: PaperReconciliationContext
    ) -> PaperReconciliationRead:
        self._validate_context(context)
        path = _ACCOUNT_PATH.format(account_id=quote(self._account_id, safe="-"))
        response = self._get(path, "reconciliation Account Details")
        if response is None or response.payload is None:
            return self._not_found(
                context,
                PaperObservationReadKind.ACCOUNT_DETAILS,
                PaperObservationObjectKind.ACCOUNT,
                request_id=response.request_id if response is not None else None,
            )
        payload = _object(response.payload, "reconciliation Account Details")
        snapshot = normalize_oanda_practice_execution_account_snapshot(
            payload, self._account_id
        )
        trades = [
            {
                "trade_id": trade.provider_trade_id,
                "instrument": trade.provider_instrument,
                "units": str(trade.current_units),
                "price": str(trade.open_price),
                "state": trade.state,
            }
            for trade in snapshot.trades.trades
        ]
        positions = [
            {
                "instrument": position.provider_instrument,
                "long": str(position.long.units),
                "short": str(position.short.units),
            }
            for position in snapshot.positions.positions
        ]
        pending = [
            {
                "order_id": order.provider_order_id,
                "type": order.provider_order_type,
                "state": order.state,
            }
            for order in snapshot.pending_orders.orders
        ]
        facts = {
            "account_id": snapshot.identity.provider_account_id,
            "last_transaction_id": snapshot.last_transaction_id,
            "open_trades": trades,
            "open_positions": positions,
            "pending_orders": pending,
        }
        observation = self._observation(
            context,
            PaperObservationReadKind.ACCOUNT_DETAILS,
            PaperObservationObjectKind.ACCOUNT,
            facts,
            request_id=response.request_id,
            last_transaction_id=snapshot.last_transaction_id,
        )
        return PaperReconciliationRead(
            observation=observation,
            state=PaperReconciliationReadState.ACCOUNT,
            unexpected_exposure=(
                snapshot.summary.open_trade_count > 0
                or snapshot.summary.open_position_count > 0
                or snapshot.summary.pending_order_count > 0
            ),
        )

    def read_transaction_range(
        self, context: PaperReconciliationContext, from_id: str, to_id: str
    ) -> PaperReconciliationRead:
        self._validate_context(context)
        start = _positive_or_zero_id(from_id)
        end = _positive_or_zero_id(to_id)
        if start is None or end is None or int(end) < int(start):
            raise OandaReconciliationNormalizationError("transaction range is invalid")
        if int(end) - int(start) + 1 > _MAX_RANGE_ITEMS:
            raise OandaReconciliationNormalizationError("transaction range is too wide")
        path = _RANGE_PATH.format(account_id=quote(self._account_id, safe="-"))
        response = self._get(
            path,
            "reconciliation transaction range",
            params={"from": start, "to": end},
        )
        if response is None:
            raise OandaReconciliationNormalizationError(
                "transaction range unexpectedly returned not found"
            )
        payload = _object(response.payload, "reconciliation transaction range")
        values = cast(object, payload.get("transactions"))
        if not isinstance(values, list):
            raise OandaReconciliationNormalizationError(
                "transaction range has invalid transactions"
            )
        raw_transactions = cast(list[object], values)
        if len(raw_transactions) > _MAX_RANGE_ITEMS:
            raise OandaReconciliationNormalizationError(
                "transaction range has too many transactions"
            )
        create_ids: set[str] = set()
        for value in raw_transactions:
            if not isinstance(value, Mapping):
                continue
            transaction = cast(Mapping[str, Any], value)
            transaction_id = _positive_id(transaction.get("id"))
            if (
                transaction_id is not None
                and transaction.get("type") == "MARKET_ORDER"
                and self._matches_create(context, transaction)
            ):
                create_ids.add(transaction_id)
                order_id = _positive_id(transaction.get("orderID"))
                if order_id is not None:
                    create_ids.add(order_id)
        normalized_transactions: list[PaperReconciliationTransaction] = []
        normalized_facts: list[dict[str, object]] = []
        for value in raw_transactions:
            transaction = _object(value, "transaction range item")
            transaction_id = _positive_id(transaction.get("id"))
            if transaction_id is None or not (
                int(start) <= int(transaction_id) <= int(end)
            ):
                raise OandaReconciliationNormalizationError(
                    "transaction range item is outside requested bounds"
                )
            normalized_facts.append(_transaction_facts(transaction))
            normalized_transactions.append(
                self._range_candidate(context, transaction, create_ids=create_ids)
            )
        selected_fill = next(
            (item.fill for item in normalized_transactions if item.fill is not None),
            None,
        )
        selected_rejection = next(
            (
                item.rejection
                for item in normalized_transactions
                if item.rejection is not None
            ),
            None,
        )
        terminal_candidates = [
            item
            for item in normalized_transactions
            if item.attributable
            and (
                item.fill is not None
                or item.state
                in (
                    PaperReconciliationReadState.REJECTED,
                    PaperReconciliationReadState.CANCELLED,
                )
            )
        ]
        contradictory = selected_fill is not None and any(
            item.rejection is not None for item in normalized_transactions
        )
        selected = terminal_candidates[0] if len(terminal_candidates) == 1 else None
        # The response remains a range read even when it contains one selected
        # terminal candidate; the typed candidate list is part of the range
        # contract and is consumed by the provider-neutral coordinator.
        state = PaperReconciliationReadState.RANGE
        attributable = selected is not None and not contradictory
        if contradictory or len(terminal_candidates) > 1:
            state = PaperReconciliationReadState.CONFLICT
        last_id = _optional_positive_id(payload, "lastTransactionID")
        facts: dict[str, object] = {"transactions": normalized_facts}
        if last_id is not None:
            facts["last_transaction_id"] = last_id
        observation = self._observation(
            context,
            PaperObservationReadKind.TRANSACTION_RANGE,
            PaperObservationObjectKind.TRANSACTION,
            facts,
            provider_transaction_id=(
                selected.provider_transaction_id if selected is not None else None
            ),
            provider_order_id=(
                selected.provider_order_id if selected is not None else None
            ),
            provider_trade_id=(
                selected.provider_trade_id if selected is not None else None
            ),
            request_id=response.request_id,
            batch_id=_first_transaction_value(raw_transactions, "batchID"),
            related_transaction_ids=_all_related_ids(raw_transactions),
            last_transaction_id=last_id,
        )
        return PaperReconciliationRead(
            observation=observation,
            state=state,
            fill=selected_fill if attributable or contradictory else None,
            rejection=selected_rejection,
            attributable=attributable,
            transactions=tuple(normalized_transactions),
        )

    def _range_candidate(
        self,
        context: PaperReconciliationContext,
        transaction: Mapping[str, Any],
        *,
        create_ids: set[str] | None = None,
    ) -> PaperReconciliationTransaction:
        transaction_id = _positive_id(transaction.get("id"))
        transaction_type = transaction.get("type")
        if transaction_type == "ORDER_FILL":
            fill = self._fill_from_transaction(
                context,
                transaction,
                expected_order_id=context.provider_order_id,
            )
            order_id = _positive_id(transaction.get("orderID"))
            attributable = (
                fill is not None
                and (
                    context.provider_order_id is None
                    or order_id == context.provider_order_id
                )
                and (create_ids is None or order_id in create_ids)
                and _range_lineage_matches(transaction, create_ids)
            )
            return PaperReconciliationTransaction(
                PaperReconciliationReadState.FILLED,
                provider_transaction_id=transaction_id,
                provider_order_id=order_id,
                provider_trade_id=fill.broker_trade_id if fill else None,
                fill=fill if attributable else None,
                attributable=attributable,
            )
        if transaction_type == "MARKET_ORDER_REJECT":
            rejection = self._rejection_from_transaction(
                context, transaction, create_ids=create_ids
            )
            return PaperReconciliationTransaction(
                PaperReconciliationReadState.REJECTED,
                provider_transaction_id=transaction_id,
                provider_order_id=_positive_id(transaction.get("orderID")),
                rejection=rejection,
                attributable=rejection is not None,
            )
        if transaction_type == "ORDER_CANCEL":
            order_id = _positive_id(transaction.get("orderID"))
            attributable = (
                transaction.get("accountID") == context.provider_account_id
                and order_id is not None
                and (
                    context.provider_order_id is None
                    or order_id == context.provider_order_id
                )
                and (create_ids is None or order_id in create_ids)
                and _entry_optional_fields_match(context, transaction)
                and _range_lineage_matches(transaction, create_ids)
            )
            return PaperReconciliationTransaction(
                PaperReconciliationReadState.CANCELLED,
                provider_transaction_id=transaction_id,
                provider_order_id=order_id,
                attributable=attributable,
            )
        return PaperReconciliationTransaction(
            PaperReconciliationReadState.UNKNOWN,
            provider_transaction_id=transaction_id,
            attributable=False,
        )

    def _transaction_read(
        self,
        context: PaperReconciliationContext,
        transaction: Mapping[str, Any],
        request_id: str | None,
        read_kind: PaperObservationReadKind,
        expected_transaction_id: str | None = None,
    ) -> PaperReconciliationRead:
        candidate = self._range_candidate(context, transaction)
        if (
            expected_transaction_id is not None
            and candidate.provider_transaction_id != expected_transaction_id
        ):
            candidate = replace(candidate, attributable=False)
        if (
            expected_transaction_id is not None
            and context.provider_order_id is None
            and candidate.state
            in (
                PaperReconciliationReadState.FILLED,
                PaperReconciliationReadState.REJECTED,
                PaperReconciliationReadState.CANCELLED,
            )
        ):
            candidate = replace(candidate, attributable=False)
        facts = _transaction_facts(transaction)
        observation = self._observation(
            context,
            read_kind,
            PaperObservationObjectKind.TRANSACTION,
            facts,
            provider_order_id=candidate.provider_order_id,
            provider_transaction_id=candidate.provider_transaction_id,
            provider_trade_id=candidate.provider_trade_id,
            client_order_id=_client_order_id(transaction),
            request_id=request_id,
            batch_id=_positive_id(transaction.get("batchID")),
            related_transaction_ids=_related_ids(
                transaction.get("relatedTransactionIDs")
            ),
            last_transaction_id=_optional_positive_id(transaction, "lastTransactionID"),
            provider_observed_at=_timestamp_or_none(transaction.get("time")),
        )
        return PaperReconciliationRead(
            observation=observation,
            state=(
                PaperReconciliationReadState.CONFLICT
                if not candidate.attributable
                and candidate.state
                in (
                    PaperReconciliationReadState.FILLED,
                    PaperReconciliationReadState.REJECTED,
                    PaperReconciliationReadState.CANCELLED,
                )
                else candidate.state
            ),
            fill=candidate.fill if candidate.attributable else None,
            rejection=candidate.rejection if candidate.attributable else None,
            attributable=candidate.attributable,
        )

    def _trade_read(
        self,
        context: PaperReconciliationContext,
        trade: Mapping[str, Any],
        request_id: str | None,
        *,
        expected_trade_id: str | None = None,
    ) -> PaperReconciliationRead:
        trade_id = _positive_id(trade.get("id"))
        client_trade_id = _client_id(trade.get("clientExtensions"))
        account_id = trade.get("accountID")
        instrument = trade.get("instrument")
        state_value = trade.get("state")
        units = _decimal_or_none(
            trade.get("initialUnits")
            if state_value == "CLOSED" and trade.get("initialUnits") is not None
            else trade.get("currentUnits")
        )
        price = _decimal_or_none(trade.get("price"))
        attributable = (
            trade_id is not None
            and trade_id == (expected_trade_id or trade_id)
            and (
                context.provider_trade_id is None
                or trade_id == context.provider_trade_id
            )
            and account_id == context.provider_account_id
            and instrument == context.instrument
            and client_trade_id == context.client_trade_id
            and (
                context.fill_signed_units is None or units == context.fill_signed_units
            )
            and (context.fill_price is None or price == context.fill_price)
        )
        if state_value == "CLOSED":
            state = PaperReconciliationReadState.CLOSED
        elif state_value == "OPEN":
            state = PaperReconciliationReadState.OPEN
        else:
            state = PaperReconciliationReadState.UNKNOWN
        stop, stop_drift = self._leg(
            trade,
            "stopLossOrder",
            context,
            expected_client_id=context.client_stop_loss_order_id,
            expected_price=context.stop_price,
            expected_type="STOP_LOSS",
            claimed=True,
        )
        target, target_drift = self._leg(
            trade,
            "takeProfitOrder",
            context,
            expected_client_id=context.client_take_profit_order_id,
            expected_price=context.actual_target_price,
            expected_type="TAKE_PROFIT",
            claimed=context.take_profit_claimed,
        )
        protection = ProtectionConfirmation(
            stop_loss_status=stop[0],
            stop_loss=stop[1],
            take_profit_status=target[0],
            take_profit=target[1],
            actual_target_price=(
                context.actual_target_price if context.take_profit_claimed else None
            ),
        )
        facts = _trade_facts(trade, stop[1], target[1])
        observation = self._observation(
            context,
            PaperObservationReadKind.TRADE_DETAIL,
            PaperObservationObjectKind.TRADE,
            facts,
            provider_trade_id=trade_id,
            client_trade_id=client_trade_id,
            signed_units=units,
            price=price,
            request_id=request_id,
            last_transaction_id=_optional_positive_id(trade, "lastTransactionID"),
            provider_observed_at=_timestamp_or_none(trade.get("openTime")),
        )
        return PaperReconciliationRead(
            observation=observation,
            state=state,
            trade_id=trade_id,
            protection=protection,
            attributable=attributable,
            protection_drift=stop_drift or target_drift,
        )

    def _leg(
        self,
        trade: Mapping[str, Any],
        field_name: str,
        context: PaperReconciliationContext,
        *,
        expected_client_id: str,
        expected_price: Decimal | None,
        expected_type: str,
        claimed: bool,
    ) -> tuple[tuple[ProtectionLegStatus, BrokerProtectionOrder | None], bool]:
        if field_name not in trade:
            return (ProtectionLegStatus.UNKNOWN, None), False
        value = cast(object, trade.get(field_name))
        if not isinstance(value, Mapping):
            return (ProtectionLegStatus.UNKNOWN, None), True
        value = cast(Mapping[str, Any], value)
        order_id = _positive_id(value.get("id"))
        client_id = _client_id(value.get("clientExtensions"))
        price = _decimal_or_none(value.get("price"))
        state_value = value.get("state")
        if (
            order_id is None
            or client_id is None
            or price is None
            or not isinstance(state_value, str)
        ):
            return (ProtectionLegStatus.UNKNOWN, None), True
        order = BrokerProtectionOrder(order_id, client_id, price, state_value)
        exact = (
            claimed
            and client_id == expected_client_id
            and expected_price is not None
            and price == expected_price
            and value.get("type") == expected_type
            and value.get("tradeID") == trade.get("id")
            and value.get("timeInForce") == "GTC"
        )
        if not exact:
            return (ProtectionLegStatus.UNKNOWN, None), True
        if state_value == "PENDING":
            return (ProtectionLegStatus.CONFIRMED, order), False
        if state_value in {"CANCELLED", "FILLED", "REJECTED"}:
            return (ProtectionLegStatus.REJECTED, order), False
        return (ProtectionLegStatus.UNKNOWN, order), True

    def _fill_from_transaction(
        self,
        context: PaperReconciliationContext,
        transaction: Mapping[str, Any],
        *,
        expected_order_id: str | None,
    ) -> BrokerFillFacts | None:
        transaction_id = _positive_id(transaction.get("id"))
        order_id = _positive_id(transaction.get("orderID"))
        opened = transaction.get("tradeOpened")
        trade_opened = _object_or_none(opened)
        if trade_opened is None:
            return None
        trade_id = _positive_id(trade_opened.get("tradeID"))
        trade_extensions = transaction.get("tradeClientExtensions")
        transaction_trade_id = _positive_id(transaction.get("tradeID"))
        units = _decimal_or_none(transaction.get("units"))
        opened_units = _decimal_or_none(trade_opened.get("units"))
        price = _decimal_or_none(trade_opened.get("price"))
        executed_at = _timestamp_or_none(transaction.get("time"))
        if (
            transaction.get("accountID") != context.provider_account_id
            or transaction.get("type") != "ORDER_FILL"
            or order_id is None
            or expected_order_id is not None
            and order_id != expected_order_id
            or _client_order_id(transaction) != context.client_order_id
            or transaction.get("instrument") != context.instrument
            or not _entry_optional_fields_match(context, transaction)
            or transaction_id is None
            or units != context.signed_requested_units
            or opened_units != context.signed_requested_units
            or trade_id is None
            or (transaction_trade_id is not None and transaction_trade_id != trade_id)
            or (
                trade_extensions is not None
                and _client_id(trade_extensions) != context.client_trade_id
            )
            or price is None
            or executed_at is None
        ):
            return None
        assert units is not None
        assert price is not None
        assert executed_at is not None
        if context.direction is Direction.LONG:
            valid_geometry = price <= context.approved_entry_price and (
                context.stop_price < price
            )
        else:
            valid_geometry = price >= context.approved_entry_price and (
                context.stop_price > price
            )
        if not valid_geometry:
            return None
        actual_risk = abs(units) * abs(price - context.stop_price)
        return BrokerFillFacts(
            broker_order_id=order_id,
            broker_fill_transaction_id=transaction_id,
            broker_trade_id=trade_id,
            signed_units=units,
            price=price,
            executed_at=executed_at,
            actual_initial_risk=actual_risk,
        )

    @staticmethod
    def _matches_create(
        context: PaperReconciliationContext, transaction: Mapping[str, Any]
    ) -> bool:
        client_extensions = transaction.get("clientExtensions")
        trade_extensions = transaction.get("tradeClientExtensions")
        if not isinstance(client_extensions, Mapping) or not isinstance(
            trade_extensions, Mapping
        ):
            return False
        client_extensions = cast(Mapping[str, Any], client_extensions)
        trade_extensions = cast(Mapping[str, Any], trade_extensions)
        stop_on_fill = transaction.get("stopLossOnFill")
        stop_on_fill_map = _object_or_none(stop_on_fill)
        if "stopLossOnFill" in transaction and stop_on_fill_map is None:
            return False
        stop_price = (
            _decimal_or_none(stop_on_fill_map.get("price"))
            if stop_on_fill_map
            else None
        )
        return (
            _positive_id(transaction.get("id")) is not None
            and transaction.get("accountID") == context.provider_account_id
            and transaction.get("type") == "MARKET_ORDER"
            and transaction.get("instrument") == context.instrument
            and _decimal_or_none(transaction.get("units"))
            == context.signed_requested_units
            and transaction.get("timeInForce") == "FOK"
            and transaction.get("positionFill") == "OPEN_ONLY"
            and _decimal_or_none(transaction.get("priceBound"))
            == context.approved_entry_price
            and _client_id(client_extensions) == context.client_order_id
            and client_extensions.get("tag") == "atlas-paper-04"
            and _client_id(trade_extensions) == context.client_trade_id
            and (
                stop_on_fill_map is None
                or (
                    stop_price == context.stop_price
                    and stop_on_fill_map.get("timeInForce") == "GTC"
                    and _client_id(stop_on_fill_map.get("clientExtensions"))
                    == context.client_stop_loss_order_id
                )
            )
            and _entry_optional_fields_match(context, transaction)
        )

    def _rejection_from_transaction(
        self,
        context: PaperReconciliationContext,
        transaction: Mapping[str, Any],
        *,
        create_ids: set[str] | None = None,
    ) -> BrokerRejection | None:
        transaction_id = _positive_id(transaction.get("id"))
        order_id = _positive_id(transaction.get("orderID"))
        order_matches_lineage = (
            context.provider_order_id is not None
            and order_id == context.provider_order_id
            if create_ids is None
            else order_id is not None and order_id in create_ids
        )
        if (
            transaction_id is None
            or transaction.get("accountID") != context.provider_account_id
            or transaction.get("type") != "MARKET_ORDER_REJECT"
            or _client_order_id(transaction) != context.client_order_id
            or not order_matches_lineage
            or not _entry_optional_fields_match(context, transaction)
            or not _range_lineage_matches(transaction, create_ids)
        ):
            return None
        return BrokerRejection("BROKER_ORDER_REJECTED", order_id, transaction_id)

    def _observation(
        self,
        context: PaperReconciliationContext,
        read_kind: PaperObservationReadKind,
        object_kind: PaperObservationObjectKind,
        facts: Mapping[str, object],
        *,
        provider_order_id: str | None = None,
        provider_transaction_id: str | None = None,
        provider_trade_id: str | None = None,
        client_order_id: str | None = None,
        client_trade_id: str | None = None,
        signed_units: Decimal | None = None,
        price: Decimal | None = None,
        request_id: str | None = None,
        batch_id: str | None = None,
        related_transaction_ids: tuple[str, ...] = (),
        last_transaction_id: str | None = None,
        provider_observed_at: datetime | None = None,
    ) -> PaperBrokerObservation:
        return PaperBrokerObservation(
            attempt_id=context.attempt_id,
            read_kind=read_kind,
            object_kind=object_kind,
            provider_account_id=context.provider_account_id,
            instrument=(
                None
                if object_kind is PaperObservationObjectKind.ACCOUNT
                else Instrument.EUR_USD
            ),
            normalized_facts=dict(facts),
            provider_order_id=provider_order_id,
            provider_transaction_id=provider_transaction_id,
            provider_trade_id=provider_trade_id,
            client_order_id=client_order_id,
            client_trade_id=client_trade_id,
            signed_units=signed_units,
            price=price,
            request_id=request_id,
            batch_id=batch_id,
            related_transaction_ids=related_transaction_ids,
            last_transaction_id=last_transaction_id,
            provider_observed_at=provider_observed_at,
            atlas_observed_at=self._now(),
        )

    def _not_found(
        self,
        context: PaperReconciliationContext,
        read_kind: PaperObservationReadKind,
        object_kind: PaperObservationObjectKind,
        *,
        provider_transaction_id: str | None = None,
        provider_trade_id: str | None = None,
        request_id: str | None = None,
    ) -> PaperReconciliationRead:
        observation = self._observation(
            context,
            read_kind,
            object_kind,
            {"found": False},
            provider_transaction_id=provider_transaction_id,
            provider_trade_id=provider_trade_id,
            request_id=request_id,
        )
        return PaperReconciliationRead(
            observation=observation,
            state=PaperReconciliationReadState.NOT_FOUND,
            attributable=True,
        )

    def _get(
        self,
        path: str,
        subject: str,
        *,
        params: Mapping[str, str] | None = None,
    ) -> OandaObservationResponse | None:
        validate_token(self._token)
        try:
            return self._requester.get_json_with_metadata(
                path, error_subject=subject, params=params
            )
        except OandaRequestError as error:
            if error.status_code == 404:
                return OandaObservationResponse(
                    payload=None, request_id=error.request_id
                )
            raise

    def _validate_context(self, context: PaperReconciliationContext) -> None:
        if (
            type(context) is not PaperReconciliationContext
            or context.provider_account_id != self._account_id
            or context.instrument != "EUR_USD"
        ):
            raise OandaReconciliationNormalizationError(
                "reconciliation context is outside OANDA Practice scope"
            )

    def _now(self) -> datetime:
        value = self._clock()
        if (
            type(value) is not datetime
            or value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise OandaReconciliationNormalizationError("observation clock is invalid")
        return value.astimezone(UTC)


def _object(value: object, subject: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise OandaReconciliationNormalizationError(f"{subject} is not an object")
    return cast(Mapping[str, Any], value)


def _object_or_none(value: object) -> Mapping[str, Any] | None:
    return cast(Mapping[str, Any], value) if isinstance(value, Mapping) else None


def _positive_id(value: object) -> str | None:
    try:
        parsed = parse_transaction_id(value)
    except OandaPrimitiveError:
        return None
    return parsed if int(parsed) > 0 else None


def _positive_or_zero_id(value: object) -> str | None:
    try:
        return parse_transaction_id(value)
    except OandaPrimitiveError:
        return None


def _order_state(value: object) -> PaperReconciliationReadState:
    if value == "PENDING":
        return PaperReconciliationReadState.PENDING
    if value == "FILLED":
        return PaperReconciliationReadState.FILLED
    if value == "CANCELLED":
        return PaperReconciliationReadState.CANCELLED
    if value == "REJECTED":
        return PaperReconciliationReadState.REJECTED
    return PaperReconciliationReadState.UNKNOWN


def _decimal_or_none(value: object) -> Decimal | None:
    try:
        return parse_decimal(value)
    except OandaPrimitiveError:
        return None


def _decimal_text(value: object) -> str | None:
    parsed = _decimal_or_none(value)
    return str(parsed) if parsed is not None else None


def _timestamp_or_none(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (
        parsed.astimezone(UTC)
        if parsed.tzinfo is not None and parsed.utcoffset() is not None
        else None
    )


def _client_id(value: object) -> str | None:
    if not isinstance(value, Mapping):
        return None
    value = cast(Mapping[str, Any], value)
    result = value.get("id")
    return result if isinstance(result, str) and result else None


def _client_order_id(value: Mapping[str, Any]) -> str | None:
    extension_id = _client_id(value.get("clientExtensions"))
    if extension_id is not None:
        return extension_id
    result = value.get("clientOrderID")
    return result if isinstance(result, str) and result else None


def _entry_optional_fields_match(
    context: PaperReconciliationContext, value: Mapping[str, Any]
) -> bool:
    """Check every request field a provider response actually supplied."""
    expected: dict[str, object] = {
        "instrument": context.instrument,
        "timeInForce": "FOK",
        "positionFill": "OPEN_ONLY",
    }
    for key, expected_value in expected.items():
        if key in value and value.get(key) != expected_value:
            return False
    for key, expected_value in (("clientOrderID", context.client_order_id),):
        if key in value and value.get(key) != expected_value:
            return False
    trade_extensions = value.get("tradeClientExtensions")
    if (
        trade_extensions is not None
        and _client_id(trade_extensions) != context.client_trade_id
    ):
        return False
    for key, expected_value in (
        ("units", context.signed_requested_units),
        ("priceBound", context.approved_entry_price),
    ):
        if key in value:
            if _decimal_or_none(value.get(key)) != expected_value:
                return False
    if "stopLossOnFill" in value:
        stop = _object_or_none(value.get("stopLossOnFill"))
        if stop is None:
            return False
        if (
            _decimal_or_none(stop.get("price")) != context.stop_price
            or stop.get("timeInForce") != "GTC"
            or _client_id(stop.get("clientExtensions"))
            != context.client_stop_loss_order_id
        ):
            return False
    return True


def _order_matches_request(
    context: PaperReconciliationContext, order: Mapping[str, Any]
) -> bool:
    """Require the exact immutable request facts on an Order readback."""
    if (
        order.get("type") != "MARKET"
        or "units" not in order
        or "timeInForce" not in order
        or "positionFill" not in order
        or "priceBound" not in order
        or not _entry_optional_fields_match(context, order)
        or _decimal_or_none(order.get("units")) != context.signed_requested_units
        or _decimal_or_none(order.get("priceBound")) != context.approved_entry_price
    ):
        return False
    client_extensions = order.get("clientExtensions")
    client_extension_map = (
        cast(Mapping[str, Any], client_extensions)
        if isinstance(client_extensions, Mapping)
        else None
    )
    if client_extensions is not None and (
        _client_id(client_extension_map) != context.client_order_id
        or (
            client_extension_map is not None
            and client_extension_map.get("tag") not in (None, "atlas-paper-04")
        )
    ):
        return False
    trade_extensions = order.get("tradeClientExtensions")
    if _client_id(trade_extensions) != context.client_trade_id:
        return False
    stop_on_fill = order.get("stopLossOnFill")
    if stop_on_fill is None:
        return True
    stop = _object_or_none(stop_on_fill)
    return bool(
        stop is not None
        and _decimal_or_none(stop.get("price")) == context.stop_price
        and stop.get("timeInForce") == "GTC"
        and _client_id(stop.get("clientExtensions"))
        == context.client_stop_loss_order_id
    )


def _related_ids(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        if value is not None:
            raise OandaReconciliationNormalizationError(
                "related transaction IDs are invalid"
            )
        return ()
    values = cast(list[Any], value)
    if len(values) > 64:
        raise OandaReconciliationNormalizationError(
            "related transaction IDs exceed the bound"
        )
    result: list[str] = []
    for item in values:
        parsed = _positive_id(item)
        if parsed is None:
            raise OandaReconciliationNormalizationError(
                "related transaction ID is invalid"
            )
        if parsed not in result:
            result.append(parsed)
    return tuple(result[:64])


def _all_related_ids(values: list[object]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        if not isinstance(value, Mapping):
            continue
        transaction = cast(Mapping[str, Any], value)
        for transaction_id in _related_ids(transaction.get("relatedTransactionIDs")):
            if transaction_id not in result:
                result.append(transaction_id)
    return tuple(result[:64])


def _first_transaction_value(values: list[object], key: str) -> str | None:
    """Return the first retained numeric provenance value from a range item."""
    for value in values:
        if not isinstance(value, Mapping):
            continue
        transaction = cast(Mapping[str, Any], value)
        result = _optional_positive_id(transaction, key)
        if result is not None:
            return result
    return None


def _optional_positive_id(value: Mapping[str, Any], key: str) -> str | None:
    if key not in value:
        return None
    result = _positive_id(value.get(key))
    if result is None:
        raise OandaReconciliationNormalizationError(f"{key} is invalid")
    return result


def _range_lineage_matches(
    transaction: Mapping[str, Any], create_ids: set[str] | None
) -> bool:
    if create_ids is None:
        return True
    related = _related_ids(transaction.get("relatedTransactionIDs"))
    return not related or bool(set(related) & create_ids)


def _unwrap_transaction(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    for key in (
        "orderCreateTransaction",
        "orderFillTransaction",
        "orderCancelTransaction",
        "orderRejectTransaction",
    ):
        value = payload.get(key)
        if isinstance(value, Mapping):
            return cast(Mapping[str, Any], value)
    return payload


def _transaction_facts(transaction: Mapping[str, Any]) -> dict[str, object]:
    opened = _object_or_none(transaction.get("tradeOpened"))
    trade_id_value = (
        opened.get("tradeID") if opened is not None else transaction.get("tradeID")
    )
    price_value = (
        opened.get("price") if opened is not None else transaction.get("price")
    )
    return {
        "account_id": transaction.get("accountID")
        if isinstance(transaction.get("accountID"), str)
        else None,
        "instrument": transaction.get("instrument")
        if isinstance(transaction.get("instrument"), str)
        else None,
        "transaction_id": _optional_positive_id(transaction, "id"),
        "order_id": _optional_positive_id(transaction, "orderID"),
        "client_order_id": _client_order_id(transaction),
        "trade_id": _positive_id(trade_id_value),
        "transaction_type": transaction.get("type")
        if isinstance(transaction.get("type"), str)
        else None,
        "order_type": transaction.get("type")
        if isinstance(transaction.get("type"), str)
        else None,
        "units": _decimal_text(transaction.get("units")),
        "price": _decimal_text(price_value),
        "time": (
            transaction.get("time")
            if isinstance(transaction.get("time"), str)
            else None
        ),
        "batch_id": _optional_positive_id(transaction, "batchID"),
        "related_transaction_ids": list(
            _related_ids(transaction.get("relatedTransactionIDs"))
        ),
        "last_transaction_id": _optional_positive_id(transaction, "lastTransactionID"),
        "time_in_force": transaction.get("timeInForce")
        if isinstance(transaction.get("timeInForce"), str)
        else None,
        "position_fill": transaction.get("positionFill")
        if isinstance(transaction.get("positionFill"), str)
        else None,
        "price_bound": _decimal_text(transaction.get("priceBound")),
    }


def _trade_facts(
    trade: Mapping[str, Any],
    stop: BrokerProtectionOrder | None,
    target: BrokerProtectionOrder | None,
) -> dict[str, object]:
    return {
        "account_id": trade.get("accountID")
        if isinstance(trade.get("accountID"), str)
        else None,
        "instrument": (
            trade.get("instrument")
            if isinstance(trade.get("instrument"), str)
            else None
        ),
        "trade_id": _positive_id(trade.get("id")),
        "client_trade_id": _client_id(trade.get("clientExtensions")),
        "state": trade.get("state") if isinstance(trade.get("state"), str) else None,
        "units": _decimal_text(trade.get("currentUnits")),
        "price": _decimal_text(trade.get("price")),
        "stop_loss": _protection_fact(stop),
        "take_profit": _protection_fact(target),
    }


def _protection_fact(order: BrokerProtectionOrder | None) -> dict[str, object] | None:
    if order is None:
        return None
    return {
        "order_id": order.broker_order_id,
        "client_protection_order_id": order.client_order_id,
        "price": str(order.price),
        "state": order.state,
    }


__all__ = [
    "OandaPracticeReconciliationReader",
    "OandaReconciliationNormalizationError",
]
