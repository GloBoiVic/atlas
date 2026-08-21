"""Pure contracts shared by Phase 3 execution adapters."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from uuid import UUID


class ExecutionInputError(ValueError):
    """An invalid canonical execution input."""


class ExecutionRejection(StrEnum):
    UNSUPPORTED_PHASE3_STOP_GAP = "UNSUPPORTED_PHASE3_STOP_GAP"
    UNSUPPORTED_PHASE3_INTRABAR_TRIGGER = "UNSUPPORTED_PHASE3_INTRABAR_TRIGGER"


class ExecutionRejected(ValueError):
    """A valid order which cannot be safely simulated in Phase 3."""

    def __init__(self, code: ExecutionRejection) -> None:
        self.code = code
        super().__init__(code.value)


def _positive(value: Decimal, name: str) -> None:
    if type(value) is not Decimal or not value.is_finite() or value <= 0:
        raise ExecutionInputError(f"{name} must be a positive finite Decimal")


def _utc(value: datetime, name: str) -> None:
    if (
        type(value) is not datetime
        or value.tzinfo is None
        or value.utcoffset() != timedelta(0)
    ):
        raise ExecutionInputError(f"{name} must be timezone-aware UTC")


@dataclass(frozen=True, slots=True)
class Order:
    """The small, immutable order contract accepted by execution."""

    id: UUID
    order_type: str
    purpose: str
    direction: str
    quantity: Decimal
    requested_price: Decimal | None = None

    def __post_init__(self) -> None:
        if type(self.id) is not UUID:
            raise ExecutionInputError("order id must be a UUID")
        _positive(self.quantity, "order quantity")
        if self.direction not in {"LONG", "SHORT"}:
            raise ExecutionInputError("order direction must be LONG or SHORT")
        valid = {
            ("MARKET", "ENTRY"),
            ("LIMIT", "TAKE_PROFIT"),
            ("STOP", "STOP_LOSS"),
        }
        if (self.order_type, self.purpose) not in valid:
            raise ExecutionInputError("order is not supported by Phase 3 execution")
        if self.purpose == "ENTRY" and self.requested_price is not None:
            raise ExecutionInputError("market entry cannot have a requested price")
        if self.purpose != "ENTRY":
            if self.requested_price is None:
                raise ExecutionInputError("exit order requires a requested price")
            _positive(self.requested_price, "requested price")


@dataclass(frozen=True, slots=True)
class ExecutionObservation:
    """Only prices available at the post-decision M1 open.

    Optional completed-bar ranges are accepted solely to identify an
    unsupported intrabar trigger; they are never used to invent a fill.
    """

    observed_at: datetime
    bid_open: Decimal
    ask_open: Decimal
    bid_high: Decimal | None = None
    bid_low: Decimal | None = None
    ask_high: Decimal | None = None
    ask_low: Decimal | None = None
    intrabar_trigger: bool = False

    def __post_init__(self) -> None:
        _utc(self.observed_at, "observation timestamp")
        _positive(self.bid_open, "bid open")
        _positive(self.ask_open, "ask open")
        if self.bid_open > self.ask_open:
            raise ExecutionInputError("bid open cannot exceed ask open")
        for name in ("bid_high", "bid_low", "ask_high", "ask_low"):
            value = getattr(self, name)
            if value is not None:
                _positive(value, name)
        if type(self.intrabar_trigger) is not bool:
            raise ExecutionInputError("intrabar_trigger must be bool")


@dataclass(frozen=True, slots=True)
class Fill:
    """One complete, in-memory Phase 3 Fill; persistence applies it later."""

    order_id: UUID
    sequence_number: int
    quantity: Decimal
    execution_price: Decimal
    executed_at: datetime
    fee: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        if type(self.order_id) is not UUID or self.sequence_number != 1:
            raise ExecutionInputError("Phase 3 Fill must be sequence one")
        _positive(self.quantity, "fill quantity")
        _positive(self.execution_price, "execution price")
        if type(self.fee) is not Decimal or not self.fee.is_finite() or self.fee != 0:
            raise ExecutionInputError("Phase 3 Fill fee must be zero")
        _utc(self.executed_at, "fill timestamp")


__all__ = [
    "ExecutionInputError", "ExecutionObservation", "ExecutionRejected",
    "ExecutionRejection", "Fill", "Order",
]
