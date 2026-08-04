"""Immutable execution-domain contracts shared by brokers and later execution slices."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from backend.core.account_mode import AccountMode
from backend.strategy.contracts import Signal


def _validate_decimal(
    value: Decimal,
    field_name: str,
    *,
    positive: bool = False,
    signed: bool = False,
) -> None:
    if not isinstance(value, Decimal):
        raise TypeError(f"{field_name} must be a Decimal")
    if not value.is_finite():
        raise ValueError(f"{field_name} must be finite")
    if not signed and ((value <= 0) if positive else (value < 0)):
        qualifier = "positive" if positive else "non-negative"
        raise ValueError(f"{field_name} must be {qualifier}")


def _validate_utc(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
        raise ValueError(f"{field_name} must be UTC")


class OrderSide(StrEnum):
    """A broker order side; CLOSE is represented by the opposing side."""

    BUY = "buy"
    SELL = "sell"


class OrderType(StrEnum):
    """Order types supported by the first execution contract slice."""

    MARKET = "market"


class OrderStatus(StrEnum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELED = "canceled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


class PositionSide(StrEnum):
    LONG = "long"
    SHORT = "short"


class PositionStatus(StrEnum):
    OPEN = "open"
    REDUCING = "reducing"
    CLOSED = "closed"


class TradeStatus(StrEnum):
    ENTERED = "entered"
    EXITED = "exited"


@dataclass(frozen=True, slots=True)
class Order:
    """A market order in one-way Futures mode."""

    account_id: UUID
    instrument_id: UUID
    side: OrderSide
    quantity: Decimal
    client_order_id: str
    id: UUID = field(default_factory=uuid4)
    bot_id: UUID | None = None
    strategy_version_id: UUID | None = None
    mode: AccountMode | None = None
    order_type: OrderType = OrderType.MARKET
    stop_loss: Decimal = Decimal("0")
    take_profit: Decimal = Decimal("0")
    reduce_only: bool = False
    leverage: Decimal = Decimal("1")
    status: OrderStatus = OrderStatus.PENDING
    broker_order_id: str | None = None
    filled_quantity: Decimal = Decimal("0")
    average_fill_price: Decimal | None = None
    signal: Signal | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not isinstance(self.account_id, UUID) or not isinstance(self.instrument_id, UUID):
            raise TypeError("order account_id and instrument_id must be UUIDs")
        if not isinstance(self.side, OrderSide):
            raise TypeError("side must be an OrderSide")
        if not isinstance(self.order_type, OrderType):
            raise TypeError("order_type must be an OrderType")
        if not self.client_order_id:
            raise ValueError("client_order_id must not be empty")
        _validate_decimal(self.quantity, "quantity", positive=True)
        _validate_decimal(self.stop_loss, "stop_loss")
        _validate_decimal(self.take_profit, "take_profit")
        _validate_decimal(self.leverage, "leverage", positive=True)
        if self.leverage > Decimal("2"):
            raise ValueError("leverage cannot exceed 2x")
        _validate_decimal(self.filled_quantity, "filled_quantity")
        if self.filled_quantity > self.quantity:
            raise ValueError("filled_quantity cannot exceed quantity")
        if self.average_fill_price is not None:
            _validate_decimal(self.average_fill_price, "average_fill_price", positive=True)
        _validate_utc(self.created_at, "created_at")
        _validate_utc(self.updated_at, "updated_at")


@dataclass(frozen=True, slots=True)
class Fill:
    """Append-only execution of part or all of an order."""

    order_id: UUID
    account_id: UUID
    instrument_id: UUID
    side: OrderSide
    quantity: Decimal
    price: Decimal
    fee: Decimal
    filled_at: datetime
    id: UUID = field(default_factory=uuid4)
    broker_fill_id: str | None = None

    def __post_init__(self) -> None:
        identities = (self.order_id, self.account_id, self.instrument_id)
        if not all(isinstance(value, UUID) for value in identities):
            raise TypeError("fill identities must be UUIDs")
        if not isinstance(self.side, OrderSide):
            raise TypeError("side must be an OrderSide")
        _validate_decimal(self.quantity, "quantity", positive=True)
        _validate_decimal(self.price, "price", positive=True)
        _validate_decimal(self.fee, "fee")
        _validate_utc(self.filled_at, "filled_at")


@dataclass(frozen=True, slots=True)
class Position:
    """The single net account/instrument position in one-way Futures mode."""

    account_id: UUID
    instrument_id: UUID
    side: PositionSide
    quantity: Decimal
    entry_price: Decimal
    mode: AccountMode
    id: UUID = field(default_factory=uuid4)
    bot_id: UUID | None = None
    strategy_version_id: UUID | None = None
    current_price: Decimal | None = None
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    unrealized_pnl: Decimal = Decimal("0")
    realized_pnl: Decimal = Decimal("0")
    leverage: Decimal = Decimal("1")
    isolated_margin: Decimal = Decimal("0")
    maintenance_margin: Decimal = Decimal("0")
    liquidation_price: Decimal | None = None
    status: PositionStatus = PositionStatus.OPEN
    opened_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    closed_at: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.account_id, UUID) or not isinstance(self.instrument_id, UUID):
            raise TypeError("position account_id and instrument_id must be UUIDs")
        if not isinstance(self.side, PositionSide):
            raise TypeError("side must be a PositionSide")
        if not isinstance(self.status, PositionStatus):
            raise TypeError("status must be a PositionStatus")
        _validate_decimal(self.quantity, "quantity", positive=True)
        _validate_decimal(self.entry_price, "entry_price", positive=True)
        for name in ("current_price", "stop_loss", "take_profit"):
            value = getattr(self, name)
            if value is not None:
                _validate_decimal(value, name, positive=True)
        _validate_decimal(self.unrealized_pnl, "unrealized_pnl", signed=True)
        _validate_decimal(self.realized_pnl, "realized_pnl", signed=True)
        _validate_decimal(self.leverage, "leverage", positive=True)
        if self.leverage > Decimal("2"):
            raise ValueError("leverage cannot exceed 2x")
        _validate_decimal(self.isolated_margin, "isolated_margin")
        _validate_decimal(self.maintenance_margin, "maintenance_margin")
        _validate_utc(self.opened_at, "opened_at")
        if self.closed_at is not None:
            _validate_utc(self.closed_at, "closed_at")


@dataclass(frozen=True, slots=True)
class Trade:
    """A position lifecycle aggregate, finalized when its position closes."""

    account_id: UUID
    instrument_id: UUID
    position_id: UUID
    direction: PositionSide
    entry_price: Decimal
    quantity: Decimal
    total_fees: Decimal
    entry_time: datetime
    id: UUID = field(default_factory=uuid4)
    bot_id: UUID | None = None
    strategy_version_id: UUID | None = None
    exit_price: Decimal | None = None
    gross_pnl: Decimal | None = None
    net_pnl: Decimal | None = None
    status: TradeStatus = TradeStatus.ENTERED
    signal_metadata: dict[str, object] = field(default_factory=dict)
    market_context: dict[str, object] = field(default_factory=dict)
    exit_time: datetime | None = None

    def __post_init__(self) -> None:
        identities = (self.account_id, self.instrument_id, self.position_id)
        if not all(isinstance(value, UUID) for value in identities):
            raise TypeError("trade identities must be UUIDs")
        if not isinstance(self.direction, PositionSide) or not isinstance(self.status, TradeStatus):
            raise TypeError("invalid trade direction or status")
        _validate_decimal(self.entry_price, "entry_price", positive=True)
        _validate_decimal(self.quantity, "quantity", positive=True)
        _validate_decimal(self.total_fees, "total_fees")
        for name in ("exit_price", "gross_pnl", "net_pnl"):
            value = getattr(self, name)
            if value is not None:
                _validate_decimal(
                    value,
                    name,
                    positive=name == "exit_price",
                    signed=name in {"gross_pnl", "net_pnl"},
                )
        _validate_utc(self.entry_time, "entry_time")
        if self.exit_time is not None:
            _validate_utc(self.exit_time, "exit_time")
