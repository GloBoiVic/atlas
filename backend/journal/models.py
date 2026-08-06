"""Immutable journal projections of completed execution trades."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4


class JournalDirection(StrEnum):
    """Trade direction persisted in the journal projection."""

    LONG = "long"
    SHORT = "short"


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
    if positive and value <= 0:
        raise ValueError(f"{field_name} must be positive")
    if not positive and not signed and value < 0:
        raise ValueError(f"{field_name} must be non-negative")


def _validate_utc(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
        raise ValueError(f"{field_name} must be UTC")


@dataclass(frozen=True, slots=True)
class JournalEntry:
    """A historical, human-readable snapshot associated with one completed trade.

    Trade-derived fields are immutable snapshots.  Notes are changed through the
    repository, which returns a replacement entry rather than mutating this value.
    """

    account_id: UUID
    trade_id: UUID
    symbol: str
    direction: JournalDirection
    entry_price: Decimal
    quantity: Decimal
    strategy_name: str
    opened_at: datetime
    id: UUID = field(default_factory=uuid4)
    bot_id: UUID | None = None
    strategy_version_id: UUID | None = None
    instrument_id: UUID | None = None
    exit_price: Decimal | None = None
    pnl: Decimal | None = None
    signal: dict[str, object] = field(default_factory=dict)
    market_conditions: dict[str, object] = field(default_factory=dict)
    notes: str | None = None
    risk_metadata: dict[str, object] = field(default_factory=dict)
    closed_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        identities = (self.id, self.account_id, self.trade_id)
        if not all(isinstance(value, UUID) for value in identities):
            raise TypeError("journal entry identities must be UUIDs")
        for name in ("bot_id", "strategy_version_id", "instrument_id"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, UUID):
                raise TypeError(f"{name} must be a UUID")
        if not isinstance(self.direction, JournalDirection):
            raise TypeError("direction must be a JournalDirection")
        for name in ("symbol", "strategy_name"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise ValueError(f"{name} must not be empty")
        _validate_decimal(self.entry_price, "entry_price", positive=True)
        _validate_decimal(self.quantity, "quantity", positive=True)
        if self.exit_price is not None:
            _validate_decimal(self.exit_price, "exit_price", positive=True)
        if self.pnl is not None:
            _validate_decimal(self.pnl, "pnl", signed=True)
        for name in ("opened_at", "created_at", "updated_at"):
            _validate_utc(getattr(self, name), name)
        if self.closed_at is not None:
            _validate_utc(self.closed_at, "closed_at")
