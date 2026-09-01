"""Provider-neutral broker facts used by PAPER composition.

These values deliberately contain no provider response objects.  OANDA's
normalizer is responsible for turning its response shapes into these small,
immutable facts before they reach Risk or runtime code.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum

from .market_data import InputError, Instrument, Provider, VenueInstrument
from .strategy import Direction


class AccountMode(StrEnum):
    PAPER = "PAPER"
    LIVE = "LIVE"


class BrokerFactsError(InputError):
    """A broker fact is missing, malformed, or unsafe to use."""


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value:
        raise BrokerFactsError(f"{name} must be a non-empty string")
    return value


def _decimal(value: object, name: str, *, non_negative: bool = False) -> Decimal:
    if type(value) is not Decimal or not value.is_finite():
        raise BrokerFactsError(f"{name} must be a finite Decimal")
    if non_negative and value < 0:
        raise BrokerFactsError(f"{name} must be non-negative")
    return value


def _utc(value: object, name: str) -> datetime:
    if (
        type(value) is not datetime
        or value.tzinfo is None
        or value.utcoffset() != timedelta(0)
    ):
        raise BrokerFactsError(f"{name} must be timezone-aware UTC")
    return value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class AccountIdentity:
    """The explicit account selection required for a PAPER Deployment."""

    account_id: str
    environment: str = "Practice"
    mode: AccountMode = AccountMode.PAPER
    base_currency: str = "USD"
    provider: Provider = Provider.OANDA

    def __post_init__(self) -> None:
        _text(self.account_id, "account_id")
        if self.environment != "Practice":
            raise BrokerFactsError("PAPER requires an OANDA Practice account")
        if self.mode is not AccountMode.PAPER:
            raise BrokerFactsError("PAPER account identity must use PAPER mode")
        if self.base_currency != "USD":
            raise BrokerFactsError("PAPER 01 requires a USD account")
        if self.provider is not Provider.OANDA:
            raise BrokerFactsError("PAPER 01 requires provider OANDA")


@dataclass(frozen=True, slots=True)
class BrokerOrderFact:
    external_id: str
    status: str
    instrument: Instrument
    units: Decimal

    def __post_init__(self) -> None:
        _text(self.external_id, "order external_id")
        _text(self.status, "order status")
        if self.instrument is not Instrument.EUR_USD:
            raise BrokerFactsError("unsupported broker order instrument")
        _decimal(self.units, "order units")

    @property
    def order_id(self) -> str:
        """Readable alias for provider-neutral callers."""

        return self.external_id


@dataclass(frozen=True, slots=True)
class BrokerTradeFact:
    external_id: str
    instrument: Instrument
    current_units: Decimal
    initial_units: Decimal

    def __post_init__(self) -> None:
        _text(self.external_id, "trade external_id")
        if self.instrument is not Instrument.EUR_USD:
            raise BrokerFactsError("unsupported broker trade instrument")
        _decimal(self.current_units, "trade current_units")
        _decimal(self.initial_units, "trade initial_units")

    @property
    def is_open(self) -> bool:
        return self.current_units != 0

    @property
    def direction(self) -> Direction:
        if self.current_units > 0:
            return Direction.LONG
        if self.current_units < 0:
            return Direction.SHORT
        raise BrokerFactsError("closed trade has no direction")

    @property
    def absolute_units(self) -> Decimal:
        return abs(self.current_units)


@dataclass(frozen=True, slots=True)
class BrokerTransactionFact:
    """Bounded transaction evidence retained for reconciliation."""

    external_id: str
    transaction_type: str
    external_order_id: str | None = None
    external_trade_id: str | None = None
    units: Decimal | None = None
    price: Decimal | None = None
    occurred_at: datetime | None = None
    instrument: str | None = None

    def __post_init__(self) -> None:
        _text(self.external_id, "transaction external_id")
        _text(self.transaction_type, "transaction type")
        for name in ("external_order_id", "external_trade_id"):
            value = getattr(self, name)
            if value is not None:
                _text(value, name)
        for name in ("units", "price"):
            value = getattr(self, name)
            if value is not None:
                _decimal(value, name)
        if self.occurred_at is not None:
            _utc(self.occurred_at, "transaction occurred_at")
        if self.instrument is not None:
            _text(self.instrument, "transaction instrument")


@dataclass(frozen=True, slots=True)
class BrokerProtectionFact:
    """Authoritative stop/target facts for one open broker Trade."""

    trade_id: str
    stop_order_id: str
    target_order_id: str
    stop_price: Decimal
    target_price: Decimal
    stop_units: Decimal | None = None
    target_units: Decimal | None = None
    # The enclosing account/trade read binds protection to one coherent
    # reconciliation observation.  A missing binding is not current proof.
    observed_at: datetime | None = None

    def __post_init__(self) -> None:
        _text(self.trade_id, "protection trade_id")
        _text(self.stop_order_id, "stop_order_id")
        _text(self.target_order_id, "target_order_id")
        _decimal(self.stop_price, "stop_price")
        _decimal(self.target_price, "target_price")
        for name in ("stop_units", "target_units"):
            value = getattr(self, name)
            if value is not None:
                _decimal(value, name)
        if self.observed_at is not None:
            _utc(self.observed_at, "protection observed_at")

    def matches(self, trade: BrokerTradeFact, *, stop_price: Decimal | None = None,
                 target_price: Decimal | None = None) -> bool:
        return (
            trade.external_id == self.trade_id
            and self.stop_order_id != self.target_order_id
            and (stop_price is None or self.stop_price == stop_price)
            and (target_price is None or self.target_price == target_price)
        )


@dataclass(frozen=True, slots=True)
class BrokerPositionSide:
    direction: Direction
    units: Decimal
    average_price: Decimal | None = None
    trade_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.direction) is not Direction:
            raise BrokerFactsError("position direction is invalid")
        _decimal(self.units, "position units", non_negative=True)
        if self.average_price is not None:
            _decimal(self.average_price, "position average_price")
            if self.average_price <= 0:
                raise BrokerFactsError("position average_price must be positive")
        if type(self.trade_ids) is not tuple or any(
            type(value) is not str or not value for value in self.trade_ids
        ):
            raise BrokerFactsError("position trade_ids are invalid")

    @property
    def is_open(self) -> bool:
        return self.units > 0


@dataclass(frozen=True, slots=True)
class AccountSnapshot:
    """Broker-authoritative account facts at one read timestamp."""

    identity: AccountIdentity
    balance: Decimal
    nav: Decimal
    unrealized_pl: Decimal
    equity: Decimal
    margin_available: Decimal
    margin_used: Decimal
    observed_at: datetime
    source: str
    fresh: bool = True
    pending_orders: tuple[BrokerOrderFact, ...] = ()
    open_trades: tuple[BrokerTradeFact, ...] = ()
    position_sides: tuple[BrokerPositionSide, ...] = ()
    last_transaction_id: str | None = None
    orders_known: bool = False
    trades_known: bool = False
    positions_known: bool = False

    def __post_init__(self) -> None:
        if type(self.identity) is not AccountIdentity:
            raise BrokerFactsError("account identity is invalid")
        for name in ("balance", "nav", "equity"):
            _decimal(getattr(self, name), name, non_negative=True)
        _decimal(self.unrealized_pl, "unrealized_pl")
        for name in ("margin_available", "margin_used"):
            _decimal(getattr(self, name), name, non_negative=True)
        _utc(self.observed_at, "account observed_at")
        _text(self.source, "account source")
        if type(self.fresh) is not bool:
            raise BrokerFactsError("account fresh must be bool")
        if type(self.pending_orders) is not tuple or any(
            type(item) is not BrokerOrderFact for item in self.pending_orders
        ):
            raise BrokerFactsError("pending_orders are invalid")
        if type(self.open_trades) is not tuple or any(
            type(item) is not BrokerTradeFact for item in self.open_trades
        ):
            raise BrokerFactsError("open_trades are invalid")
        if type(self.position_sides) is not tuple or any(
            type(item) is not BrokerPositionSide for item in self.position_sides
        ):
            raise BrokerFactsError("position_sides are invalid")
        if self.last_transaction_id is not None:
            _text(self.last_transaction_id, "last_transaction_id")
        for name in ("orders_known", "trades_known", "positions_known"):
            if type(getattr(self, name)) is not bool:
                raise BrokerFactsError(f"{name} must be bool")

    @property
    def account_state_known(self) -> bool:
        """Whether every broker collection needed to establish exposure is known."""

        return self.orders_known and self.trades_known and self.positions_known

    @property
    def has_open_position(self) -> bool:
        # Unknown broker state is unsafe to treat as flat.  Reconciliation and
        # Risk still distinguish this from known exposure via account_state_known.
        if not self.account_state_known:
            return True
        return any(side.is_open for side in self.position_sides) or any(
            trade.is_open for trade in self.open_trades
        )


@dataclass(frozen=True, slots=True)
class VenueInstrumentFacts:
    """Executable EUR/USD venue constraints, independent of OANDA naming."""

    venue_instrument: VenueInstrument
    pip_location: int
    display_precision: int
    trade_units_precision: int
    minimum_order_units: Decimal
    maximum_order_units: Decimal | None
    maximum_position_units: Decimal | None
    margin_rate: Decimal
    capabilities: frozenset[str]
    available: bool = True

    def __post_init__(self) -> None:
        if type(self.venue_instrument) is not VenueInstrument:
            raise BrokerFactsError("venue instrument is invalid")
        if self.venue_instrument.instrument is not Instrument.EUR_USD:
            raise BrokerFactsError("only EUR/USD is supported")
        for name in ("pip_location", "display_precision", "trade_units_precision"):
            if type(getattr(self, name)) is not int or (
                name != "pip_location" and getattr(self, name) < 0
            ):
                raise BrokerFactsError(f"{name} is invalid")
        _decimal(self.minimum_order_units, "minimum_order_units", non_negative=True)
        if self.minimum_order_units <= 0:
            raise BrokerFactsError("minimum_order_units must be positive")
        for name in ("maximum_order_units", "maximum_position_units"):
            value = getattr(self, name)
            if value is not None:
                _decimal(value, name, non_negative=True)
                if value == 0:
                    raise BrokerFactsError(f"{name} must be null or positive")
        if (
            self.maximum_order_units is not None
            and self.maximum_order_units < self.minimum_order_units
        ):
            raise BrokerFactsError("maximum_order_units is below the minimum")
        _decimal(self.margin_rate, "margin_rate")
        if self.margin_rate <= 0:
            raise BrokerFactsError("margin_rate must be positive")
        if type(self.capabilities) is not frozenset or not self.capabilities:
            raise BrokerFactsError("instrument capabilities are missing")
        if type(self.available) is not bool:
            raise BrokerFactsError("instrument availability must be bool")

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities


@dataclass(frozen=True, slots=True)
class ExecutableQuote:
    """A complete, current-enough BID/ASK quote for executable pricing."""

    instrument: Instrument
    bid: Decimal
    ask: Decimal
    quote_time: datetime
    source: str
    tradeable: bool
    closeout_bid: Decimal | None = None
    closeout_ask: Decimal | None = None

    def __post_init__(self) -> None:
        if self.instrument is not Instrument.EUR_USD:
            raise BrokerFactsError("only EUR/USD quotes are supported")
        _decimal(self.bid, "quote bid")
        _decimal(self.ask, "quote ask")
        if self.bid <= 0 or self.ask <= 0 or self.bid > self.ask:
            raise BrokerFactsError("quote BID/ASK geometry is invalid")
        _utc(self.quote_time, "quote_time")
        _text(self.source, "quote source")
        if type(self.tradeable) is not bool:
            raise BrokerFactsError("quote tradeable must be bool")
        for name in ("closeout_bid", "closeout_ask"):
            value = getattr(self, name)
            if value is not None:
                _decimal(value, name)
                if value <= 0:
                    raise BrokerFactsError(f"{name} must be positive")

    def is_fresh(self, as_of: datetime, max_age: timedelta) -> bool:
        """Return whether this quote is safe at ``as_of`` without using a clock."""

        as_of = _utc(as_of, "as_of")
        if type(max_age) is not timedelta or max_age <= timedelta(0):
            raise BrokerFactsError("max_age must be positive")
        age = as_of - self.quote_time
        return self.tradeable and timedelta(0) <= age <= max_age

    def price_for(self, direction: Direction) -> Decimal:
        if direction is Direction.LONG:
            return self.ask
        if direction is Direction.SHORT:
            return self.bid
        raise BrokerFactsError("quote direction is invalid")


__all__ = [
    "AccountIdentity",
    "AccountMode",
    "AccountSnapshot",
    "BrokerFactsError",
    "BrokerOrderFact",
    "BrokerPositionSide",
    "BrokerTradeFact",
    "BrokerProtectionFact",
    "BrokerTransactionFact",
    "ExecutableQuote",
    "VenueInstrumentFacts",
]
