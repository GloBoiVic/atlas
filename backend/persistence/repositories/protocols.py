from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Protocol
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from collections.abc import Mapping

    from backend.core.account_mode import AccountMode
    from backend.data.models import Candle as CandleDomain
    from backend.execution.models import Fill, Order, Position, Trade


@dataclass(frozen=True, slots=True)
class BotRecord:
    """Persistence-neutral bot data needed by the supervisor."""

    id: UUID
    name: str
    account_id: UUID
    broker: str
    mode: str
    instrument: str
    timeframe: str
    desired_status: str
    status: str
    last_error: str | None
    started_at: datetime | None
    stopped_at: datetime | None


@dataclass(frozen=True, slots=True)
class LifecycleUpdate:
    """The complete supervisor-owned lifecycle state of a bot."""

    desired_status: str
    status: str
    last_error: str | None = None
    started_at: datetime | None = None
    stopped_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ReconciliationRecord:
    """A broker reconciliation result, represented without ORM objects."""

    account_id: UUID
    bot_id: UUID | None
    status: str
    broker_snapshot: Mapping[str, object] = field(default_factory=dict)
    differences: Mapping[str, object] = field(default_factory=dict)
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    error_message: str | None = None
    id: UUID = field(default_factory=uuid4)


class BotRepository(Protocol):
    async def get_restore_candidates(self) -> list[BotRecord]:
        """Return bots whose desired state is not stopped."""

    async def get(self, bot_id: UUID) -> BotRecord | None:
        """Return one bot, if it exists."""

    async def persist_lifecycle(self, bot_id: UUID, state: LifecycleUpdate) -> BotRecord | None:
        """Persist lifecycle state and return the resulting bot."""


class ReconciliationRepository(Protocol):
    async def record(self, result: ReconciliationRecord) -> ReconciliationRecord:
        """Persist a reconciliation result."""

    async def get_reconciliation(self, reconciliation_id: UUID) -> ReconciliationRecord | None:
        """Return one reconciliation result, if it exists."""


class SupervisorRepositories(BotRepository, ReconciliationRepository, Protocol):
    """Combined dependency contract used by supervisor composition."""


# --- Feature 03 repository protocols ---


class InstrumentRepository(Protocol):
    """Provider-aware instrument lookup and creation."""

    async def resolve(
        self,
        *,
        symbol: str,
        provider: str,
        asset_type: str | None = None,
    ) -> InstrumentRecord:
        """Get or create an instrument keyed on ``(provider, symbol)``.

        If the row exists, returns it.  Otherwise inserts a record with the
        supplied fields and sensible defaults for precision/constraints.
        """

    async def upsert(
        self,
        *,
        symbol: str,
        provider: str,
        asset_type: str,
        base_currency: str | None = None,
        quote_currency: str | None = None,
        price_precision: int = 8,
        quantity_precision: int = 8,
        constraints: dict[str, object] | None = None,
    ) -> InstrumentRecord:
        """Upsert an instrument, updating constraints and ``is_active`` on conflict."""


@dataclass(frozen=True, slots=True)
class InstrumentRecord:
    """Persistence-neutral instrument data."""

    id: UUID
    symbol: str
    provider: str
    asset_type: str
    base_currency: str | None
    quote_currency: str | None
    price_precision: int
    quantity_precision: int
    is_active: bool
    constraints: dict[str, object] = field(default_factory=dict)


class CandleRepository(Protocol):
    """Bulk-insert candles with conflict-safe no-op deduplication."""

    async def save_many(self, candles: list[CandleDomain]) -> int:
        """Insert ``candles``, deduplicating on unique-constraint conflict.

        Uses ``ON CONFLICT DO NOTHING`` — existing rows are retained unchanged.
        Returns the number of rows that were **inserted**, not the batch size.
        """


class ExecutionRepository(Protocol):
    """Durable boundary for execution facts and idempotency lookups.

    Implementations must treat fills as append-only and must return the existing
    record for repeated client, broker-order, or broker-execution identifiers.
    """

    async def create_order(self, order: Order) -> Order:
        """Persist an order before broker submission, idempotently by client ID."""

    async def update_order(self, order: Order) -> Order:
        """Persist a broker status/fill update idempotently."""

    async def get_order_by_client_id(self, client_order_id: str) -> Order | None:
        """Load the durable order for a client id."""

    async def get_order_by_broker_id(self, broker_order_id: str) -> Order | None:
        """Load the durable order for a broker order id."""

    async def get_non_terminal_orders(
        self, *, account_id: UUID, mode: AccountMode
    ) -> list[Order]:
        """Return durable orders which still require broker reconciliation."""

    async def append_fill(self, fill: Fill) -> Fill:
        """Append one fill, returning the existing fill on duplicate broker ID."""

    async def get_fill_by_broker_id(self, broker_fill_id: str) -> Fill | None:
        """Load a fill by provider execution identifier."""

    async def get_fills(self, *, account_id: UUID, mode: AccountMode) -> list[Fill]:
        """Return durable fills for reconciliation."""

    async def get_positions(self, *, account_id: UUID, mode: AccountMode) -> list[Position]:
        """Return durable active positions for reconciliation."""

    async def get_position(
        self, *, account_id: UUID, instrument_id: UUID, mode: AccountMode
    ) -> Position | None:
        """Return the active one-way net position for the scope."""

    async def save_position(self, position: Position) -> Position:
        """Create or update the active position."""

    async def save_trade(self, trade: Trade) -> Trade:
        """Create or update a trade lifecycle aggregate idempotently."""

    async def get_trade_by_position(self, position_id: UUID) -> Trade | None:
        """Load the open trade associated with a net position."""
