"""Strict OANDA Practice response normalization.

Only this module knows OANDA field names.  It accepts recorded/mocked response
shapes and emits provider-neutral Atlas facts; it never performs a request.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import cast

from backend.domain.broker import (
    AccountIdentity,
    AccountSnapshot,
    BrokerFactsError,
    BrokerOrderFact,
    BrokerPositionSide,
    BrokerProtectionFact,
    BrokerTradeFact,
    BrokerTransactionFact,
    ExecutableQuote,
    VenueInstrumentFacts,
)
from backend.domain.market_data import Instrument, Provider, VenueInstrument
from backend.domain.strategy import Direction

RawObject = Mapping[str, object]


def _object(value: object, name: str) -> RawObject:
    if not isinstance(value, Mapping):
        raise BrokerFactsError(f"OANDA {name} must be an object")
    return cast(RawObject, value)


def _string(value: object, name: str) -> str:
    if type(value) is not str or not value:
        raise BrokerFactsError(f"OANDA {name} must be a non-empty string")
    return value


def _decimal(value: object, name: str, *, positive: bool = False) -> Decimal:
    if type(value) is not str:
        raise BrokerFactsError(f"OANDA {name} must be a decimal string")
    try:
        result = Decimal(value)
    except (InvalidOperation, ValueError):
        raise BrokerFactsError(f"OANDA {name} is not a decimal") from None
    if not result.is_finite() or (positive and result <= 0):
        raise BrokerFactsError(f"OANDA {name} is not finite and positive")
    return result


def _timestamp(value: object, name: str) -> datetime:
    if type(value) is not str:
        raise BrokerFactsError(f"OANDA {name} must be an RFC3339 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise BrokerFactsError(f"OANDA {name} is not an RFC3339 timestamp") from None
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise BrokerFactsError(f"OANDA {name} must be UTC")
    return parsed.astimezone(UTC)


def _array(value: object, name: str) -> list[RawObject]:
    if not isinstance(value, list):
        raise BrokerFactsError(f"OANDA {name} must be an object array")
    items = cast(list[object], value)
    if any(not isinstance(item, Mapping) for item in items):
        raise BrokerFactsError(f"OANDA {name} must be an object array")
    return [cast(RawObject, item) for item in items]


def _instrument(value: object, name: str = "instrument") -> Instrument:
    if value != "EUR_USD":
        raise BrokerFactsError(f"unsupported OANDA {name}")
    return Instrument.EUR_USD


def _optional_text(value: RawObject, name: str) -> str | None:
    item = value.get(name)
    return _string(item, name) if item is not None else None


def _optional_decimal(value: RawObject, name: str) -> Decimal | None:
    item = value.get(name)
    return _decimal(item, name) if item is not None else None


def normalize_account_selection(
    payload: RawObject, selected_account_id: str | None
) -> AccountIdentity:
    """Require one explicit Practice account and reject MT4 ambiguity."""

    if type(selected_account_id) is not str or not selected_account_id:
        raise BrokerFactsError("an explicit OANDA Practice account ID is required")
    accounts = _array(payload.get("accounts"), "accounts")
    if not accounts:
        raise BrokerFactsError("OANDA returned no authorized accounts")
    ids: set[str] = set()
    selected: RawObject | None = None
    for account in accounts:
        account_id = _string(account.get("id"), "account id")
        if account_id in ids:
            raise BrokerFactsError("OANDA returned duplicate account identities")
        ids.add(account_id)
        if account_id == selected_account_id:
            selected = account
    if selected is None:
        raise BrokerFactsError("selected OANDA account is not authorized")
    if "mt4AccountID" not in selected:
        raise BrokerFactsError("MT4 association is unknown for selected account")
    if selected["mt4AccountID"] is not None:
        raise BrokerFactsError("MT4-associated OANDA accounts are unsupported")
    return AccountIdentity(selected_account_id)


def _selected_account(value: AccountIdentity | str) -> AccountIdentity:
    if type(value) is AccountIdentity:
        return value
    if type(value) is str and value:
        return AccountIdentity(value)
    raise BrokerFactsError("account normalization requires explicit identity")


def _position_side(value: object, direction: Direction) -> BrokerPositionSide:
    side = _object(value, f"{direction.value.lower()} position side")
    signed_units = _decimal(side.get("units"), "position units")
    if (direction is Direction.LONG and signed_units < 0) or (
        direction is Direction.SHORT and signed_units > 0
    ):
        raise BrokerFactsError("OANDA position units have an invalid sign")
    units = abs(signed_units)
    average = side.get("averagePrice")
    trade_ids_value = side.get("openTradeIDs", [])
    if not isinstance(trade_ids_value, list):
        raise BrokerFactsError("OANDA position trade IDs are invalid")
    trade_ids = cast(list[object], trade_ids_value)
    if any(type(item) is not str or not item for item in trade_ids):
        raise BrokerFactsError("OANDA position trade IDs are invalid")
    return BrokerPositionSide(
        direction,
        units,
        _decimal(average, "position averagePrice", positive=True)
        if average is not None
        else None,
        tuple(cast(str, item) for item in trade_ids),
    )


def normalize_account_snapshot(
    payload: RawObject,
    account: AccountIdentity | str,
    *,
    observed_at: datetime,
    fresh: bool = True,
    source: str = "OANDA_ACCOUNT_SUMMARY_V1",
) -> AccountSnapshot:
    """Normalize the USD account summary without treating positions as exposure."""

    identity = _selected_account(account)
    raw = _object(payload.get("account"), "account summary")
    provider_id = _string(raw.get("id"), "account summary id")
    if provider_id != identity.account_id:
        raise BrokerFactsError(
            "OANDA account summary identity does not match selection"
        )
    if raw.get("currency") != "USD":
        raise BrokerFactsError("OANDA account is not USD")

    pending: list[BrokerOrderFact] = []
    for item in _array(raw.get("orders"), "orders"):
        if "instrument" not in item:
            raise BrokerFactsError("OANDA order instrument is missing")
        if item["instrument"] != "EUR_USD":
            continue
        pending.append(
            BrokerOrderFact(
                _string(item.get("id"), "order id"),
                _string(item.get("state"), "order state"),
                Instrument.EUR_USD,
                _decimal(item.get("units"), "order units"),
            )
        )

    trades: list[BrokerTradeFact] = []
    for item in _array(raw.get("trades"), "trades"):
        if "instrument" not in item:
            raise BrokerFactsError("OANDA trade instrument is missing")
        if item["instrument"] != "EUR_USD":
            continue
        trades.append(
            BrokerTradeFact(
                _string(item.get("id"), "trade id"),
                Instrument.EUR_USD,
                _decimal(item.get("currentUnits"), "trade currentUnits"),
                _decimal(item.get("initialUnits"), "trade initialUnits"),
            )
        )

    sides: list[BrokerPositionSide] = []
    for item in _array(raw.get("positions"), "positions"):
        if "instrument" not in item:
            raise BrokerFactsError("OANDA position instrument is missing")
        if item["instrument"] != "EUR_USD":
            continue
        for key, direction in (("long", Direction.LONG), ("short", Direction.SHORT)):
            if key in item:
                sides.append(_position_side(item[key], direction))

    return AccountSnapshot(
        identity=identity,
        balance=_decimal(raw.get("balance"), "balance"),
        nav=_decimal(raw.get("NAV"), "NAV"),
        unrealized_pl=_decimal(raw.get("unrealizedPL"), "unrealizedPL"),
        equity=_decimal(raw.get("NAV"), "NAV"),
        margin_available=_decimal(
            raw.get("marginAvailable"), "marginAvailable"
        ),
        margin_used=_decimal(raw.get("marginUsed"), "marginUsed"),
        observed_at=observed_at,
        source=source,
        fresh=fresh,
        pending_orders=tuple(pending),
        open_trades=tuple(trades),
        position_sides=tuple(sides),
        last_transaction_id=(
            _string(payload.get("lastTransactionID"), "lastTransactionID")
            if payload.get("lastTransactionID") is not None
            else None
        ),
        orders_known=True,
        trades_known=True,
        positions_known=True,
    )


def _instrument_object(payload: RawObject) -> RawObject:
    if "instrument" in payload:
        return _object(payload["instrument"], "instrument")
    instruments = _array(payload.get("instruments"), "instruments")
    if len(instruments) != 1:
        raise BrokerFactsError("OANDA instrument response is ambiguous")
    return instruments[0]


def normalize_instrument_facts(payload: RawObject) -> VenueInstrumentFacts:
    raw = _instrument_object(payload)
    _instrument(raw.get("name"))
    raw_capabilities = raw.get("capabilities")
    if raw_capabilities is not None:
        capabilities_value = raw_capabilities
    else:
        capabilities_value = raw.get("orderTypes")
    if not isinstance(capabilities_value, list):
        raise BrokerFactsError("OANDA instrument capabilities are missing")
    capability_items = cast(list[object], capabilities_value)
    if any(type(item) is not str for item in capability_items):
        raise BrokerFactsError("OANDA instrument capabilities are missing")
    capabilities = set(cast(str, item) for item in capability_items)
    capabilities.update({"LONG", "SHORT"})
    required = {"LONG", "SHORT", "MARKET", "STOP_LOSS", "TAKE_PROFIT"}
    if not required.issubset(capabilities):
        raise BrokerFactsError("OANDA EUR/USD capabilities are incomplete")

    maximum_position = _decimal(
        raw.get("maximumPositionSize"), "maximumPositionSize", positive=False
    )
    maximum_order = _decimal(
        raw.get("maximumOrderUnits"), "maximumOrderUnits", positive=False
    )
    pip_location = raw.get("pipLocation")
    display_precision = raw.get("displayPrecision")
    trade_units_precision = raw.get("tradeUnitsPrecision")
    if any(
        type(value) is not int
        for value in (pip_location, display_precision, trade_units_precision)
    ):
        raise BrokerFactsError("OANDA instrument precision fields are invalid")
    available = raw.get("tradeable", True)
    if type(available) is not bool:
        raise BrokerFactsError("OANDA instrument availability is invalid")
    return VenueInstrumentFacts(
        venue_instrument=VenueInstrument(
            Instrument.EUR_USD, Provider.OANDA, "EUR_USD"
        ),
        pip_location=cast(int, pip_location),
        display_precision=cast(int, display_precision),
        trade_units_precision=cast(int, trade_units_precision),
        minimum_order_units=_decimal(
            raw.get("minimumOrderUnits", raw.get("minimumTradeSize")),
            "minimumOrderUnits",
            positive=True,
        ),
        maximum_order_units=maximum_order if maximum_order > 0 else None,
        maximum_position_units=maximum_position if maximum_position > 0 else None,
        margin_rate=_decimal(raw.get("marginRate"), "marginRate", positive=True),
        capabilities=frozenset(capabilities),
        available=available,
    )


def _price_level(value: object, name: str) -> Decimal:
    levels = _array(value, name)
    if not levels:
        raise BrokerFactsError(f"OANDA quote {name} is missing")
    return _decimal(levels[0].get("price"), f"{name} price", positive=True)


def normalize_executable_quote(
    payload: RawObject,
    *,
    source: str = "OANDA_PRICING_V1",
) -> ExecutableQuote:
    prices = _array(payload.get("prices"), "prices")
    if len(prices) != 1:
        raise BrokerFactsError("OANDA pricing response is ambiguous")
    raw = prices[0]
    instrument = _instrument(raw.get("instrument"), "pricing instrument")
    quote_time = _timestamp(raw.get("time", payload.get("time")), "pricing time")
    tradeable = raw.get("tradeable")
    if type(tradeable) is not bool:
        raise BrokerFactsError("OANDA quote tradeable flag is missing")

    def optional_price(name: str) -> Decimal | None:
        value = raw.get(name)
        return _decimal(value, name, positive=True) if value is not None else None

    return ExecutableQuote(
        instrument=instrument,
        bid=_price_level(raw.get("bids"), "bids"),
        ask=_price_level(raw.get("asks"), "asks"),
        quote_time=quote_time,
        source=source,
        tradeable=tradeable,
        closeout_bid=optional_price("closeoutBid"),
        closeout_ask=optional_price("closeoutAsk"),
    )


def normalize_transactions(payload: RawObject) -> tuple[BrokerTransactionFact, ...]:
    """Normalize bounded transaction evidence without retaining provider DTOs."""

    result: list[BrokerTransactionFact] = []
    for item in _array(payload.get("transactions"), "transactions"):
        transaction_id = _string(item.get("id"), "transaction id")
        transaction_type = _string(item.get("type"), "transaction type")

        occurred_at = (
            _timestamp(item["time"], "transaction time")
            if item.get("time") is not None
            else None
        )
        result.append(
            BrokerTransactionFact(
                transaction_id,
                transaction_type,
                _optional_text(item, "orderID"),
                _optional_text(item, "tradeID"),
                _optional_decimal(item, "units"),
                _optional_decimal(item, "price"),
                occurred_at,
                (
                    "EUR/USD"
                    if item.get("instrument") == "EUR_USD"
                    else _optional_text(item, "instrument")
                ),
            )
        )
    return tuple(result)


@dataclass(frozen=True, slots=True)
class OandaAccountChanges:
    """A read-only Account Changes fence bound to the requested account."""

    account_id: str
    last_transaction_id: str
    transactions: tuple[BrokerTransactionFact, ...]


def normalize_account_changes(
    payload: RawObject, *, expected_account_id: str
) -> OandaAccountChanges:
    """Normalize every unfiltered Account Changes transaction and its fence."""

    expected = _string(expected_account_id, "expected account id")
    response_account = _optional_text(payload, "accountID")
    if response_account is not None and response_account != expected:
        raise BrokerFactsError("OANDA Account Changes account identity disagrees")
    changes = payload.get("changes")
    transactions_payload = (
        payload if changes is None else _object(changes, "account changes")
    )
    fence = payload.get("lastTransactionID")
    if fence is None and isinstance(payload.get("state"), Mapping):
        fence = cast(Mapping[str, object], payload["state"]).get("lastTransactionID")
    last_transaction_id = _string(fence, "Account Changes last transaction ID")
    if not last_transaction_id.isdecimal():
        raise BrokerFactsError("Account Changes last transaction ID is invalid")
    return OandaAccountChanges(
        expected, last_transaction_id, normalize_transactions(transactions_payload)
    )


def normalize_trade_protection(
    payload: RawObject, *, observed_at: datetime | None = None
) -> BrokerProtectionFact:
    """Normalize the broker Trade's stop and target orders."""

    trade = _object(payload.get("trade", payload), "trade")
    stop = _object(trade.get("stopLossOrder"), "stop-loss order")
    target = _object(trade.get("takeProfitOrder"), "take-profit order")
    return BrokerProtectionFact(
        _string(trade.get("id"), "trade id"),
        _string(stop.get("id"), "stop order id"),
        _string(target.get("id"), "target order id"),
        _decimal(stop.get("price"), "stop price", positive=True),
        _decimal(target.get("price"), "target price", positive=True),
        (
            _decimal(stop["units"], "stop units")
            if stop.get("units") is not None
            else None
        ),
        _decimal(target["units"], "target units")
        if target.get("units") is not None
        else None,
        observed_at,
    )


# Names used by composition code that prefers the noun over the provider verb.
normalize_account = normalize_account_snapshot
normalize_quote = normalize_executable_quote


__all__ = [
    "normalize_account",
    "normalize_account_changes",
    "normalize_account_selection",
    "normalize_account_snapshot",
    "normalize_executable_quote",
    "normalize_instrument_facts",
    "normalize_quote",
    "normalize_trade_protection",
    "normalize_transactions",
    "OandaAccountChanges",
]
