"""Narrow OANDA Practice execution contracts.

The adapter is intentionally transport-injected.  Production composition may
provide an authenticated HTTP transport, while all validation can use a
recorded transport and cannot accidentally reach OANDA.  Provider response
objects stop at this module; callers receive canonical execution facts.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Protocol, cast
from uuid import UUID

import httpx
from pydantic import SecretStr
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from backend.execution.contract import Fill, Order
from backend.execution.fill_application import apply_fill
from backend.persistence.models import (
    DeploymentModel,
    FillModel,
    OrderEventModel,
    OrderModel,
    SystemEventModel,
)

RawObject = Mapping[str, object]


class OandaExecutionError(RuntimeError):
    """A safe, provider-independent execution transport or contract error."""


class FillIdentityConflictError(OandaExecutionError):
    """A provider Fill identity was already attributed to different facts."""


class OandaOrderStatus(StrEnum):
    FULL_FILLED = "FULL_FILLED"
    REJECTED = "REJECTED"
    CANCELED = "CANCELED"
    UNKNOWN = "UNKNOWN"
    PARTIAL = "PARTIAL"
    REISSUED = "REISSUED"


class OandaExecutionTransport(Protocol):
    def submit_market_fok(self, account_id: str, payload: RawObject) -> RawObject: ...

    def attach_take_profit(
        self, account_id: str, trade_id: str, payload: RawObject
    ) -> RawObject: ...

    def trade(self, account_id: str, trade_id: str) -> RawObject: ...


class OandaPracticeExecutionClient:
    """Authenticated HTTP transport; it has no retry or mutation convenience."""

    def __init__(
        self,
        token: SecretStr,
        *,
        client: httpx.Client | None = None,
        transport: httpx.BaseTransport | None = None,
        base_url: str = "https://api-fxpractice.oanda.com",
    ) -> None:
        if not token.get_secret_value():
            raise OandaExecutionError("OANDA execution token is required")
        self._token = token
        self._client = client
        self._transport = transport
        self._base_url = base_url.rstrip("/")

    @staticmethod
    def _account_id(account_id: str) -> str:
        if (
            type(account_id) is not str
            or not account_id
            or any(char in account_id for char in "/?#")
        ):
            raise OandaExecutionError("an explicit OANDA account ID is required")
        return account_id

    def _request(
        self, method: str, path: str, payload: RawObject | None = None
    ) -> RawObject:
        owned = self._client is None
        client = self._client or httpx.Client(
            transport=self._transport,
            base_url=self._base_url,
            follow_redirects=False,
            trust_env=False,
        )
        try:
            response = client.request(
                method,
                f"{self._base_url}{path}",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self._token.get_secret_value()}",
                    "Accept-Datetime-Format": "RFC3339",
                },
            )
            try:
                value = response.json()
            except ValueError:
                raise OandaExecutionError(
                    "OANDA execution request outcome is unknown"
                ) from None
            if not isinstance(value, Mapping):
                raise OandaExecutionError("OANDA returned an invalid execution object")
            if response.status_code < 200 or response.status_code >= 300:
                if not any(
                    key in value
                    for key in ("orderRejectTransaction", "orderCancelTransaction")
                ):
                    raise OandaExecutionError("OANDA execution request was rejected")
            return cast(RawObject, value)
        except (httpx.RequestError, ValueError):
            raise OandaExecutionError(
                "OANDA execution request outcome is unknown"
            ) from None
        finally:
            if owned:
                client.close()

    def submit_market_fok(self, account_id: str, payload: RawObject) -> RawObject:
        return self._request(
            "POST", f"/v3/accounts/{self._account_id(account_id)}/orders", payload
        )

    def attach_take_profit(
        self, account_id: str, trade_id: str, payload: RawObject
    ) -> RawObject:
        if type(trade_id) is not str or not trade_id or "/" in trade_id:
            raise OandaExecutionError("an explicit OANDA trade ID is required")
        return self._request(
            "PUT",
            f"/v3/accounts/{self._account_id(account_id)}/trades/{trade_id}/orders",
            payload,
        )

    def trade(self, account_id: str, trade_id: str) -> RawObject:
        if type(trade_id) is not str or not trade_id or "/" in trade_id:
            raise OandaExecutionError("an explicit OANDA trade ID is required")
        return self._request(
            "GET",
            f"/v3/accounts/{self._account_id(account_id)}/trades/{trade_id}",
        )


def _object(value: object, name: str) -> RawObject:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return cast(RawObject, value)


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value or any(ord(char) < 32 for char in value):
        raise ValueError(f"{name} is invalid")
    return value


def _decimal(value: object, name: str) -> Decimal:
    if type(value) not in (str, Decimal):
        raise ValueError(f"{name} is invalid")
    try:
        result = value if type(value) is Decimal else Decimal(cast(str, value))
    except (InvalidOperation, ValueError):
        raise ValueError(f"{name} is invalid") from None
    if not result.is_finite():
        raise ValueError(f"{name} is invalid")
    return result


def _timestamp(value: object, name: str) -> datetime:
    if type(value) is not str:
        raise ValueError(f"{name} is invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"{name} is invalid") from None
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError(f"{name} is not UTC")
    return parsed.astimezone(UTC)


def _ids(value: object, name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"{name} is invalid")
    values = cast(list[object], value)
    return tuple(_text(item, name) for item in values)


@dataclass(frozen=True, slots=True)
class OandaExecutionResult:
    """Normalized result of one submission attempt; UNKNOWN is never a reject."""

    status: str
    order_id: UUID
    external_order_id: str | None = None
    external_trade_ids: tuple[str, ...] = ()
    related_transaction_ids: tuple[str, ...] = ()
    provider_request_id: str | None = None
    last_transaction_id: str | None = None
    fill: Fill | None = None
    reason: str | None = None
    executed_units: Decimal | None = None


@dataclass(frozen=True, slots=True)
class ProtectionState:
    trade_id: str
    stop_order_id: str
    target_order_id: str
    stop_price: Decimal
    target_price: Decimal
    stop_units: Decimal | None = None
    target_units: Decimal | None = None
    current_units: Decimal | None = None
    initial_units: Decimal | None = None
    trade_state: str | None = None
    observed_at: datetime | None = None
    fresh: bool = False

    def same_protection(self, other: "ProtectionState") -> bool:
        """Compare broker protection while ignoring read timestamps."""

        return (
            self.trade_id == other.trade_id
            and self.stop_order_id == other.stop_order_id
            and self.target_order_id == other.target_order_id
            and self.stop_price == other.stop_price
            and self.target_price == other.target_price
            and self.stop_units == other.stop_units
            and self.target_units == other.target_units
            and self.current_units == other.current_units
            and self.initial_units == other.initial_units
            and self.trade_state == other.trade_state
        )

    def matches(
        self,
        *,
        trade_id: str,
        direction: str,
        quantity: Decimal,
        stop_price: Decimal,
        target_price: Decimal,
    ) -> bool:
        """Check authoritative protection without accepting local-only claims."""
        return (
            self.trade_id == trade_id
            and bool(self.stop_order_id)
            and bool(self.target_order_id)
            and self.stop_order_id != self.target_order_id
            and self.stop_price == stop_price
            and self.target_price == target_price
        )


def target_from_fill(
    fill_price: Decimal,
    approved_stop: Decimal,
    direction: str,
    multiple: Decimal = Decimal("1.7"),
) -> Decimal:
    """Calculate the final target from authoritative Fill price only."""
    for value, name in (
        (fill_price, "fill_price"),
        (approved_stop, "approved_stop"),
        (multiple, "multiple"),
    ):
        if type(value) is not Decimal or not value.is_finite() or value <= 0:
            raise OandaExecutionError(f"{name} is invalid")
    if direction not in {"LONG", "SHORT"}:
        raise OandaExecutionError("direction is invalid")
    if (direction == "LONG" and approved_stop >= fill_price) or (
        direction == "SHORT" and approved_stop <= fill_price
    ):
        raise OandaExecutionError("stop geometry is invalid")
    risk = abs(fill_price - approved_stop)
    return (
        fill_price + multiple * risk
        if direction == "LONG"
        else fill_price - multiple * risk
    )


class OandaExecutionAdapter:
    """Translate canonical PAPER entry/protection facts to OANDA shapes."""

    def build_entry_payload(self, order: Order) -> dict[str, object]:
        if order.purpose != "ENTRY" or order.order_type != "MARKET":
            raise OandaExecutionError("PAPER entry must be MARKET")
        if order.time_in_force != "FOK":
            raise OandaExecutionError("PAPER entry must use FOK")
        if order.instrument.value != "EUR/USD":
            raise OandaExecutionError("only EUR/USD is supported")
        if order.client_correlation_id is None:
            raise OandaExecutionError("stable client correlation is required")
        if order.price_bound is None or order.stop_loss_price is None:
            raise OandaExecutionError(
                "PAPER entry requires priceBound and stop protection"
            )
        units = order.quantity if order.direction == "LONG" else -order.quantity
        protection: dict[str, object] = {
            "price": str(order.stop_loss_price),
            "timeInForce": "GTC",
            "clientExtensions": {"id": f"{order.client_correlation_id}-stop"},
        }
        return {
            "order": {
                "type": "MARKET",
                "instrument": "EUR_USD",
                "units": str(units),
                "timeInForce": "FOK",
                "positionFill": "DEFAULT",
                "priceBound": str(order.price_bound),
                "clientExtensions": {"id": order.client_correlation_id},
                "stopLossOnFill": protection,
            }
        }

    def build_target_payload(
        self, *, target_price: Decimal, units: Decimal, client_correlation_id: str
    ) -> dict[str, object]:
        if target_price <= 0 or units <= 0 or not client_correlation_id:
            raise OandaExecutionError("target protection facts are invalid")
        return {
            "takeProfit": {
                "price": str(target_price),
                "timeInForce": "GTC",
                "clientExtensions": {"id": f"{client_correlation_id}-target"},
            }
        }

    def submit_entry(
        self,
        transport: OandaExecutionTransport,
        *,
        account_id: str,
        order: Order,
        persist_pending: Callable[[], None],
    ) -> OandaExecutionResult:
        """Persist-before-network; transport exceptions become UNKNOWN, never retry."""
        payload = self.build_entry_payload(order)
        persist_pending()
        try:
            response = transport.submit_market_fok(account_id, payload)
        except (TimeoutError, httpx.TimeoutException, OandaExecutionError):
            return OandaExecutionResult(
                OandaOrderStatus.UNKNOWN, order.id, reason="SUBMISSION_OUTCOME_UNKNOWN"
            )
        return normalize_create_response(response, order)

    def attach_target(
        self,
        transport: OandaExecutionTransport,
        *,
        account_id: str,
        trade_id: str,
        target_price: Decimal,
        units: Decimal,
        client_correlation_id: str,
    ) -> ProtectionState:
        payload = self.build_target_payload(
            target_price=target_price,
            units=units,
            client_correlation_id=client_correlation_id,
        )
        try:
            response = transport.attach_take_profit(account_id, trade_id, payload)
        except (TimeoutError, httpx.TimeoutException, OandaExecutionError):
            raise OandaExecutionError("target protection outcome is unknown") from None
        return normalize_protection_state(
            response, observed_at=datetime.now(UTC), fresh=True
        )

    def confirm_protection(
        self,
        transport: OandaExecutionTransport,
        *,
        account_id: str,
        trade_id: str,
        direction: str,
        quantity: Decimal,
        stop_price: Decimal,
        target_price: Decimal,
        observed_at: datetime | None = None,
        now: datetime | None = None,
    ) -> ProtectionState:
        """Read broker Trade state and require both protections to match."""
        try:
            response = transport.trade(account_id, trade_id)
        except (TimeoutError, httpx.TimeoutException, OandaExecutionError):
            raise OandaExecutionError("protection confirmation is unknown") from None
        reference = now or datetime.now(UTC)
        observation = observed_at or reference
        return validate_protection_state(
            normalize_protection_state(
                response, observed_at=observation, fresh=True
            ),
            trade_id=trade_id,
            direction=direction,
            quantity=quantity,
            stop_price=stop_price,
            target_price=target_price,
            now=reference,
        )


def normalize_create_response(payload: RawObject, order: Order) -> OandaExecutionResult:
    """Normalize compound OANDA create/fill/reject/cancel/reissue responses."""
    try:
        related = _ids(payload.get("relatedTransactionIDs", []), "related transactions")
        last_id = (
            _text(payload["lastTransactionID"], "last transaction ID")
            if payload.get("lastTransactionID") is not None
            else None
        )
        create_value = payload.get("orderCreateTransaction")
        create: RawObject = (
            _object(create_value, "create transaction")
            if create_value is not None
            else {}
        )
        fill_value = payload.get("orderFillTransaction")
        fill_probe: RawObject = (
            _object(cast(RawObject, fill_value), "fill transaction")
            if isinstance(fill_value, Mapping)
            else {}
        )
        identity_values: list[str] = []
        for name, value in (
            ("orderCreateTransaction.id", create.get("id")),
            ("orderCreateTransaction.orderID", create.get("orderID")),
            ("orderFillTransaction.orderID", fill_probe.get("orderID")),
            ("payload.orderID", payload.get("orderID")),
        ):
            if value is not None:
                identity_values.append(_text(value, name))
        for key in (
            "orderRejectTransaction",
            "orderCancelTransaction",
            "orderReissueTransaction",
        ):
            value = payload.get(key)
            transaction: RawObject = (
                cast(RawObject, value) if isinstance(value, Mapping) else {}
            )
            if transaction.get("orderID") is not None:
                identity_values.append(
                    _text(transaction["orderID"], f"{key}.orderID")
                )
        if len(set(identity_values)) > 1:
            raise ValueError("provider Order identities conflict")
        external_order_id = identity_values[0] if identity_values else None
        request_id = (
            _text(payload["requestID"], "request ID")
            if payload.get("requestID") is not None
            else _text(create["requestID"], "request ID")
            if create.get("requestID") is not None
            else None
        )
        reissue = payload.get("orderReissueTransaction") is not None
        fill_object = payload.get("orderFillTransaction")
        cancel = payload.get("orderCancelTransaction")
        reject = payload.get("orderRejectTransaction")
        if reissue:
            return OandaExecutionResult(
                OandaOrderStatus.REISSUED, order.id, external_order_id,
                related_transaction_ids=related, provider_request_id=request_id,
                last_transaction_id=last_id, reason="ORDER_REISSUED",
            )
        if fill_object is not None and (cancel is not None or reject is not None):
            return OandaExecutionResult(
                OandaOrderStatus.UNKNOWN,
                order.id,
                external_order_id,
                related_transaction_ids=related,
                provider_request_id=request_id,
                last_transaction_id=last_id,
                reason="AMBIGUOUS_BROKER_RESPONSE",
            )
        if fill_object is None:
            if reject is not None:
                return OandaExecutionResult(
                    OandaOrderStatus.REJECTED, order.id, external_order_id,
                    related_transaction_ids=related, provider_request_id=request_id,
                    last_transaction_id=last_id, reason="BROKER_REJECTED",
                )
            if cancel is not None:
                return OandaExecutionResult(
                    OandaOrderStatus.CANCELED, order.id, external_order_id,
                    related_transaction_ids=related, provider_request_id=request_id,
                    last_transaction_id=last_id, reason="BROKER_CANCELED",
                )
            raise ValueError("compound response has no terminal outcome")
        fill = _object(fill_object, "fill transaction")
        signed_units = _decimal(fill.get("units"), "fill units")
        expected_sign = 1 if order.direction == "LONG" else -1
        if signed_units == 0 or (signed_units > 0) != (expected_sign > 0):
            raise ValueError("fill units have the wrong direction")
        executed_units = abs(signed_units)
        if executed_units != order.quantity:
            return OandaExecutionResult(
                OandaOrderStatus.PARTIAL, order.id, external_order_id,
                related_transaction_ids=related, provider_request_id=request_id,
                last_transaction_id=last_id,
                reason="PARTIAL_FILL",
                executed_units=executed_units,
            )
        trade_opened = _object(fill.get("tradeOpened"), "trade opened")
        trade_id = _text(trade_opened.get("tradeID"), "external trade ID")
        transaction_id = _text(fill.get("id"), "fill transaction ID")
        executed_at = _timestamp(fill.get("time"), "fill time")
        fee = _decimal(fill.get("commission", "0"), "commission")
        canonical_fill = Fill(
            order_id=order.id,
            sequence_number=1,
            quantity=executed_units,
            execution_price=_decimal(fill.get("price"), "fill price"),
            executed_at=executed_at,
            fee=fee,
            price_basis="OPEN",
            external_execution_id=transaction_id,
            external_transaction_id=transaction_id,
            external_trade_id=trade_id,
            related_transaction_ids=related,
        )
        return OandaExecutionResult(
            OandaOrderStatus.FULL_FILLED, order.id, external_order_id,
            external_trade_ids=(trade_id,), related_transaction_ids=related,
            provider_request_id=request_id, last_transaction_id=last_id,
            fill=canonical_fill, executed_units=executed_units,
        )
    except (KeyError, TypeError, ValueError, InvalidOperation):
        return OandaExecutionResult(
            OandaOrderStatus.UNKNOWN, order.id, reason="MALFORMED_BROKER_RESPONSE"
        )


def normalize_protection_state(
    payload: RawObject,
    *,
    observed_at: datetime | None = None,
    fresh: bool = False,
) -> ProtectionState:
    """Require authoritative broker stop and target facts before continuing."""
    try:
        raw_trade = payload.get("trade", payload)
        trade = _object(raw_trade, "trade")
        trade_id = _text(trade.get("id"), "trade ID")
        trade_state = _text(trade.get("state"), "trade state")
        current_units = _decimal(trade.get("currentUnits"), "trade currentUnits")
        initial_units = (
            _decimal(trade["initialUnits"], "trade initialUnits")
            if trade.get("initialUnits") is not None
            else None
        )
        stop = _object(trade.get("stopLossOrder"), "stop order")
        target = _object(trade.get("takeProfitOrder"), "target order")
        stop_id = _text(stop.get("id"), "stop order ID")
        target_id = _text(target.get("id"), "target order ID")
        stop_price = _decimal(stop.get("price"), "stop price")
        target_price = _decimal(target.get("price"), "target price")
        stop_units = (
            _decimal(stop["units"], "stop units")
            if stop.get("units") is not None
            else None
        )
        target_units = (
            _decimal(target["units"], "target units")
            if target.get("units") is not None
            else None
        )
        return ProtectionState(
            trade_id,
            stop_id,
            target_id,
            stop_price,
            target_price,
            stop_units,
            target_units,
            current_units,
            initial_units,
            trade_state,
            observed_at,
            fresh,
        )
    except (KeyError, TypeError, ValueError, InvalidOperation):
        raise OandaExecutionError("broker protection is missing or ambiguous") from None


def validate_protection_state(
    state: ProtectionState,
    *,
    trade_id: str,
    direction: str,
    quantity: Decimal,
    stop_price: Decimal,
    target_price: Decimal,
    now: datetime | None = None,
    max_age: timedelta = timedelta(minutes=2),
) -> ProtectionState:
    if not state.matches(
        trade_id=trade_id,
        direction=direction,
        quantity=quantity,
        stop_price=stop_price,
        target_price=target_price,
    ):
        raise OandaExecutionError("broker protection is missing, wrong, or orphaned")
    if (
        state.trade_state != "OPEN"
        or state.current_units is None
        or abs(state.current_units) != quantity
        or (state.current_units > 0) != (direction == "LONG")
        or (
            state.initial_units is not None
            and (
                abs(state.initial_units) != quantity
                or (state.initial_units > 0) != (direction == "LONG")
            )
        )
        or not state.fresh
        or state.observed_at is None
    ):
        raise OandaExecutionError(
            "broker Trade exposure is missing, partial, closed, or stale"
        )
    reference = now or datetime.now(UTC)
    if (
        reference.tzinfo is None
        or reference.utcoffset() != timedelta(0)
        or state.observed_at > reference
        or reference - state.observed_at > max_age
    ):
        raise OandaExecutionError("broker protection observation is stale")
    return state


def fill_model_from_canonical(fill: Fill) -> FillModel:
    """Bridge one normalized OANDA Fill to the shared persistence model."""
    return FillModel(
        order_id=fill.order_id,
        sequence_number=fill.sequence_number,
        quantity=fill.quantity,
        execution_price=fill.execution_price,
        executed_at=fill.executed_at,
        external_execution_id=fill.external_execution_id,
        external_transaction_id=fill.external_transaction_id,
        external_trade_id=fill.external_trade_id,
        related_transaction_ids=list(fill.related_transaction_ids),
        fee=fill.fee,
        price_basis=fill.price_basis,
        executable_reference_price=fill.executable_reference_price,
        slippage_per_unit=fill.slippage_per_unit,
        slippage_cost=fill.slippage_cost,
        source_market_bar_id=fill.source_market_bar_id,
    )


def immutable_fill_facts_agree(existing: FillModel, incoming: Fill) -> bool:
    """Require exact agreement before treating an external Fill as a replay."""

    return (
        existing.order_id == incoming.order_id
        and existing.sequence_number == incoming.sequence_number
        and existing.quantity == incoming.quantity
        and existing.execution_price == incoming.execution_price
        and existing.executed_at == incoming.executed_at
        and existing.external_execution_id == incoming.external_execution_id
        and existing.external_transaction_id == incoming.external_transaction_id
        and existing.external_trade_id == incoming.external_trade_id
        and tuple(existing.related_transaction_ids)
        == incoming.related_transaction_ids
        and existing.fee == incoming.fee
        and existing.source_market_bar_id == incoming.source_market_bar_id
        and existing.price_basis == incoming.price_basis
        and existing.executable_reference_price == incoming.executable_reference_price
        and existing.slippage_per_unit == incoming.slippage_per_unit
        and existing.slippage_cost == incoming.slippage_cost
    )


def order_provider_facts_agree(
    order: OrderModel, result: OandaExecutionResult
) -> bool:
    """Compare immutable provider identity facts without request provenance."""

    return (
        order.external_order_id == result.external_order_id
        and tuple(order.external_trade_ids) == result.external_trade_ids
        and tuple(order.related_transaction_ids) == result.related_transaction_ids
    )


def _fill_identity_rows(session: Session, fill: Fill) -> list[FillModel]:
    if fill.external_execution_id is None or fill.external_transaction_id is None:
        return []
    return list(
        session.scalars(
            select(FillModel).where(
                or_(
                    FillModel.external_execution_id == fill.external_execution_id,
                    FillModel.external_transaction_id == fill.external_transaction_id,
                )
            )
        ).all()
    )


def apply_execution_result(
    session: Session, order: OrderModel, result: OandaExecutionResult
) -> FillModel | None:
    """Persist a normalized result and apply exposure only for a full Fill."""
    if order.id != result.order_id:
        raise OandaExecutionError("execution result does not match Order")
    if result.status == OandaOrderStatus.FULL_FILLED:
        if result.fill is None or result.fill.quantity != order.quantity:
            raise OandaExecutionError("PAPER result is not an unambiguous full Fill")
        fill = result.fill
        if (
            fill.external_execution_id is None
            or fill.external_transaction_id is None
            or result.external_order_id is None
            or len(result.external_trade_ids) != 1
            or fill.external_trade_id is None
            or result.external_trade_ids != (fill.external_trade_id,)
            or tuple(fill.related_transaction_ids) != result.related_transaction_ids
        ):
            raise OandaExecutionError(
                "PAPER full Fill is missing complete provider identity"
            )
        existing_rows = _fill_identity_rows(session, fill)
        if existing_rows:
            if len(existing_rows) != 1:
                raise FillIdentityConflictError(
                    "external Fill identity has multiple canonical owners"
                )
            existing = existing_rows[0]
            if (
                not immutable_fill_facts_agree(existing, fill)
                or not order_provider_facts_agree(order, result)
            ):
                raise FillIdentityConflictError(
                    "external Fill identity conflicts with existing canonical facts"
                )
            return existing

        # Do not mutate Order provider facts until all replay/collision checks
        # above have passed.  A failed identity check must not complete the
        # current Order or its intent/handoff.
        if order.external_order_id is not None and (
            order.external_order_id != result.external_order_id
        ):
            raise FillIdentityConflictError("external Order identity conflicts")
        if order.external_trade_ids and (
            tuple(order.external_trade_ids) != result.external_trade_ids
        ):
            raise FillIdentityConflictError("external Trade identity conflicts")
        if order.related_transaction_ids and (
            tuple(order.related_transaction_ids) != result.related_transaction_ids
        ):
            raise FillIdentityConflictError("external transaction identity conflicts")
        order.external_order_id = result.external_order_id
        order.external_trade_ids = list(result.external_trade_ids)
        order.related_transaction_ids = list(result.related_transaction_ids)
        order.provider_request_id = result.provider_request_id
        return apply_fill(session, fill_model_from_canonical(fill))

    if result.external_order_id is not None:
        order.external_order_id = result.external_order_id
    order.external_trade_ids = list(result.external_trade_ids)
    order.related_transaction_ids = list(result.related_transaction_ids)
    order.provider_request_id = result.provider_request_id
    state_by_status: dict[str, tuple[str, str]] = {
        OandaOrderStatus.REJECTED: ("REJECTED", "ORDER_REJECTED"),
        OandaOrderStatus.CANCELED: ("CANCELED", "ORDER_CANCELED"),
        OandaOrderStatus.UNKNOWN: ("UNKNOWN", "ORDER_UNKNOWN"),
        OandaOrderStatus.PARTIAL: ("UNKNOWN", "ORDER_PARTIAL"),
        OandaOrderStatus.REISSUED: ("UNKNOWN", "ORDER_REISSUED"),
    }
    try:
        status, event = state_by_status[result.status]
    except KeyError:
        raise OandaExecutionError("unsupported execution result") from None
    order.current_status = status
    if order.deployment_id is not None:
        deployment = session.get(DeploymentModel, order.deployment_id)
        if deployment is not None:
            deployment.actual_state = "RECONCILIATION_REQUIRED"
            deployment.safety_reason = (
                "Broker execution outcome is uncertain or not full-fill-only"
            )
        session.add(
            SystemEventModel(
                deployment_id=order.deployment_id,
                severity="CRITICAL",
                code=(
                    "ORDER_OUTCOME_UNKNOWN"
                    if result.status == OandaOrderStatus.UNKNOWN
                    else "ORDER_NOT_FULL_FILLED"
                ),
                detail=(
                    "Broker execution outcome requires reconciliation; "
                    "new exposure is blocked"
                ),
                details={"order_id": str(order.id), "status": result.status},
            )
        )
    sequence = session.scalar(
        select(func.coalesce(func.max(OrderEventModel.sequence_number), 0) + 1)
        .where(OrderEventModel.order_id == order.id)
    )
    if sequence is None:
        raise OandaExecutionError("cannot sequence Order event")
    session.add(
        OrderEventModel(
            order_id=order.id,
            sequence_number=int(sequence),
            event_type=event,
            occurred_at=datetime.now(UTC),
            details={
                "reason": result.reason or "BROKER_OUTCOME",
                "executed_units": str(result.executed_units)
                if result.executed_units is not None
                else None,
            },
        )
    )
    session.flush()
    return None


__all__ = [
    "FillIdentityConflictError",
    "OandaExecutionAdapter",
    "OandaExecutionError",
    "OandaExecutionResult",
    "OandaExecutionTransport",
    "OandaOrderStatus",
    "OandaPracticeExecutionClient",
    "ProtectionState",
    "apply_execution_result",
    "fill_model_from_canonical",
    "normalize_create_response",
    "normalize_protection_state",
    "target_from_fill",
    "validate_protection_state",
]
