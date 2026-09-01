"""Pure, deterministic contracts for historical simulated execution."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from backend.domain.market_data import Instrument


class ExecutionInputError(ValueError):
    """An invalid canonical execution input."""


class ExecutionRejection(StrEnum):
    NOT_TRIGGERED = "NOT_TRIGGERED"
    INVALID_SLIPPAGE = "INVALID_SLIPPAGE"
    # Retained as compatibility values for the Phase 3 runner; Phase 4 never
    # uses them for a valid historical observation.
    UNSUPPORTED_PHASE3_STOP_GAP = "UNSUPPORTED_PHASE3_STOP_GAP"
    UNSUPPORTED_PHASE3_INTRABAR_TRIGGER = "UNSUPPORTED_PHASE3_INTRABAR_TRIGGER"


class ExecutionRejected(ValueError):
    """A valid order which did not produce a fill."""

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
    instrument: Instrument = Instrument.EUR_USD
    client_correlation_id: str | None = None
    time_in_force: str | None = None
    price_bound: Decimal | None = None
    stop_loss_price: Decimal | None = None

    def __post_init__(self) -> None:
        if type(self.id) is not UUID:
            raise ExecutionInputError("order id must be a UUID")
        if type(self.instrument) is not Instrument:
            raise ExecutionInputError("order instrument must be an Instrument")
        if self.client_correlation_id is not None and (
            type(self.client_correlation_id) is not str
            or not self.client_correlation_id
        ):
            raise ExecutionInputError("client correlation must be a non-empty string")
        if self.time_in_force is not None and self.time_in_force not in {"FOK", "IOC"}:
            raise ExecutionInputError("unsupported time in force")
        for name in ("price_bound", "stop_loss_price"):
            value = getattr(self, name)
            if value is not None:
                _positive(value, name)
        _positive(self.quantity, "order quantity")
        if self.direction not in {"LONG", "SHORT"}:
            raise ExecutionInputError("order direction must be LONG or SHORT")
        valid = {
            ("MARKET", "ENTRY"),
            ("MARKET", "EXIT"),
            ("LIMIT", "TAKE_PROFIT"),
            ("STOP", "STOP_LOSS"),
        }
        if (self.order_type, self.purpose) not in valid:
            raise ExecutionInputError("unsupported simulated order")
        if self.purpose in {"ENTRY", "EXIT"} and self.requested_price is not None:
            raise ExecutionInputError("market entry cannot have a requested price")
        if self.purpose not in {"ENTRY", "EXIT"}:
            if self.requested_price is None:
                raise ExecutionInputError("exit order requires a requested price")
            _positive(self.requested_price, "requested price")


@dataclass(frozen=True, slots=True)
class ExecutionObservation:
    """One complete M1 BID/ASK observation and its immutable provenance."""

    observed_at: datetime
    bid_open: Decimal
    ask_open: Decimal
    bid_high: Decimal | None = None
    bid_low: Decimal | None = None
    ask_high: Decimal | None = None
    ask_low: Decimal | None = None
    bid_close: Decimal | None = None
    ask_close: Decimal | None = None
    bid_source_market_bar_id: UUID | None = None
    ask_source_market_bar_id: UUID | None = None
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
        for name in ("bid_close", "ask_close"):
            value = getattr(self, name)
            if value is not None:
                _positive(value, name)
        for name in ("bid_source_market_bar_id", "ask_source_market_bar_id"):
            value = getattr(self, name)
            if value is not None and type(value) is not UUID:
                raise ExecutionInputError(f"{name} must be a UUID")
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
    source_market_bar_id: UUID | None = None
    price_basis: str = "OPEN"
    executable_reference_price: Decimal | None = None
    slippage_per_unit: Decimal = Decimal("0")
    slippage_cost: Decimal = Decimal("0")
    external_execution_id: str | None = None
    external_transaction_id: str | None = None
    external_trade_id: str | None = None
    related_transaction_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.order_id) is not UUID or self.sequence_number != 1:
            raise ExecutionInputError("Phase 3 Fill must be sequence one")
        _positive(self.quantity, "fill quantity")
        _positive(self.execution_price, "execution price")
        for name in ("fee", "slippage_per_unit", "slippage_cost"):
            value = getattr(self, name)
            if type(value) is not Decimal or not value.is_finite() or value < 0:
                raise ExecutionInputError(
                    f"{name} must be a finite non-negative Decimal"
                )
        if (
            self.source_market_bar_id is not None
            and type(self.source_market_bar_id) is not UUID
        ):
            raise ExecutionInputError("source_market_bar_id must be a UUID")
        if self.price_basis not in {
            "OPEN", "OPEN_GAP", "INTRABAR_STOP", "INTRABAR_TARGET", "END_CLOSE"
        }:
            raise ExecutionInputError("unsupported price basis")
        if self.executable_reference_price is not None:
            _positive(self.executable_reference_price, "executable reference price")
        for name in (
            "external_execution_id", "external_transaction_id", "external_trade_id",
        ):
            value = getattr(self, name)
            if value is not None and (type(value) is not str or not value):
                raise ExecutionInputError(f"{name} must be a non-empty string")
        if type(self.related_transaction_ids) is not tuple or any(
            type(value) is not str or not value
            for value in self.related_transaction_ids
        ):
            raise ExecutionInputError("related transaction IDs are invalid")
        _utc(self.executed_at, "fill timestamp")


__all__ = [
    "ExecutionInputError", "ExecutionObservation", "ExecutionRejected",
    "ExecutionRejection", "Fill", "Order",
]
