"""Broker-facing protocols and immutable result/snapshot contracts."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from backend.execution.models import Fill, Order, OrderStatus, Position


@dataclass(frozen=True, slots=True)
class OrderResult:
    """Classified broker response; ``unknown`` is fail-closed and not retryable."""

    success: bool
    status: OrderStatus
    order_id: str | None = None
    fills: tuple[Fill, ...] = ()
    error: str | None = None
    unknown: bool = False

    @property
    def broker_order_id(self) -> str | None:
        """Return the provider order identifier under the domain vocabulary."""
        return self.order_id


@dataclass(frozen=True, slots=True)
class AccountInfo:
    """Broker account balance snapshot using quote-currency Decimals."""

    account_id: UUID
    balance: Decimal
    equity: Decimal
    available_balance: Decimal
    as_of: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not isinstance(self.account_id, UUID):
            raise TypeError("account_id must be a UUID")
        for name in ("balance", "equity", "available_balance"):
            value = getattr(self, name)
            if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
                raise ValueError(f"{name} must be a finite non-negative Decimal")
        if self.as_of.tzinfo is None or self.as_of.utcoffset() != UTC.utcoffset(self.as_of):
            raise ValueError("as_of must be UTC")


@dataclass(frozen=True, slots=True)
class BrokerSnapshot:
    """Authoritative broker state used during reconciliation."""

    account: AccountInfo
    orders: tuple[Order, ...] = ()
    positions: tuple[Position, ...] = ()
    fills: tuple[Fill, ...] = ()
    as_of: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if self.as_of.tzinfo is None or self.as_of.utcoffset() != UTC.utcoffset(self.as_of):
            raise ValueError("as_of must be UTC")


class Broker(Protocol):
    """Broker boundary; implementations own provider-specific API details."""

    async def submit_order(self, order: Order, client_order_id: str) -> OrderResult:
        """Submit an order idempotently by client order ID."""

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order by broker order ID."""

    async def get_positions(self) -> list[Position]:
        """Return current broker positions."""

    async def get_account(self) -> AccountInfo:
        """Return current broker account state."""

    async def reconcile(self) -> BrokerSnapshot:
        """Return an authoritative snapshot for recovery and unknown states."""
