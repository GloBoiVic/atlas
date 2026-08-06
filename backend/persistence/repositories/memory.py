from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from backend.core.account_mode import AccountMode

if TYPE_CHECKING:
    from backend.data.models import Candle as CandleDomain
    from backend.execution.models import Fill, Order, Position, Trade
    from backend.execution.paper_broker import FundingAdjustment
    from backend.journal.models import JournalEntry

from backend.persistence.repositories.candle_semantics import validate_candle_query
from backend.persistence.repositories.protocols import (
    BotRecord,
    CandleRepository,
    InstrumentRecord,
    InstrumentRepository,
    LifecycleUpdate,
    ReconciliationRecord,
)


class InMemorySupervisorRepositories:
    """Deterministic repository implementation for tests and local runtimes."""

    def __init__(
        self,
        bots: list[BotRecord] | None = None,
        reconciliations: list[ReconciliationRecord] | None = None,
    ) -> None:
        self._bots = {bot.id: bot for bot in bots or []}
        self._reconciliations = {result.id: result for result in reconciliations or []}
        self._bot_lock = asyncio.Lock()

    async def get_restore_candidates(self) -> list[BotRecord]:
        async with self._bot_lock:
            return [bot for bot in self._bots.values() if bot.desired_status != "stopped"]

    async def get(self, bot_id: UUID) -> BotRecord | None:
        async with self._bot_lock:
            return self._bots.get(bot_id)

    async def persist_lifecycle(self, bot_id: UUID, state: LifecycleUpdate) -> BotRecord | None:
        async with self._bot_lock:
            return self._update_bot(bot_id, state)

    def _update_bot(self, bot_id: UUID, state: LifecycleUpdate) -> BotRecord | None:
        bot = self._bots.get(bot_id)
        if bot is None:
            return None
        updated = BotRecord(
            id=bot.id,
            name=bot.name,
            account_id=bot.account_id,
            broker=bot.broker,
            mode=bot.mode,
            instrument=bot.instrument,
            timeframe=bot.timeframe,
            desired_status=state.desired_status,
            status=state.status,
            last_error=state.last_error,
            started_at=state.started_at,
            stopped_at=state.stopped_at,
        )
        self._bots[bot_id] = updated
        return updated

    async def record(self, result: ReconciliationRecord) -> ReconciliationRecord:
        async with self._bot_lock:
            self._reconciliations.setdefault(result.id, result)
            return self._reconciliations[result.id]

    async def get_reconciliation(self, reconciliation_id: UUID) -> ReconciliationRecord | None:
        async with self._bot_lock:
            return self._reconciliations.get(reconciliation_id)


class InMemoryInstrumentRepository(InstrumentRepository):
    """Deterministic instrument repository for tests.

    ``resolve`` is select-then-insert: it never overwrites fields of an existing
    record when the caller supplies no metadata.  ``upsert`` unconditionally
    updates every field for the matching ``(symbol, provider)`` key, matching the
    SQLAlchemy ``ON CONFLICT DO UPDATE`` semantics.
    """

    def __init__(
        self,
        instruments: list[InstrumentRecord] | None = None,
    ) -> None:
        self._instruments: dict[UUID, InstrumentRecord] = {}
        self._by_provider_symbol: dict[tuple[str, str], UUID] = {}
        self._lock = asyncio.Lock()
        if instruments:
            for instrument in instruments:
                self._instruments[instrument.id] = instrument
                self._by_provider_symbol[(instrument.provider, instrument.symbol)] = instrument.id

    async def resolve(
        self,
        *,
        symbol: str,
        provider: str,
        asset_type: str | None = None,
    ) -> InstrumentRecord:
        async with self._lock:
            key = (provider, symbol)
            existing_id = self._by_provider_symbol.get(key)
            if existing_id is not None:
                return self._instruments[existing_id]
            # Insert new record with minimal defaults.
            record = InstrumentRecord(
                id=uuid4(),
                symbol=symbol,
                provider=provider,
                asset_type=asset_type or "crypto",
                base_currency=None,
                quote_currency=None,
                price_precision=8,
                quantity_precision=8,
                is_active=True,
                constraints={},
            )
            self._instruments[record.id] = record
            self._by_provider_symbol[key] = record.id
            return record

    async def get(self, instrument_id: UUID) -> InstrumentRecord | None:
        async with self._lock:
            return self._instruments.get(instrument_id)

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
        constraints_dict = constraints or {}
        async with self._lock:
            key = (provider, symbol)
            existing_id = self._by_provider_symbol.get(key)
            if existing_id is not None:
                # Update every field — matches ON CONFLICT DO UPDATE semantics.
                updated = InstrumentRecord(
                    id=existing_id,
                    symbol=symbol,
                    provider=provider,
                    asset_type=asset_type,
                    base_currency=base_currency,
                    quote_currency=quote_currency,
                    price_precision=price_precision,
                    quantity_precision=quantity_precision,
                    is_active=True,
                    constraints=dict(constraints_dict),
                )
                self._instruments[existing_id] = updated
                return updated
            # Insert new.
            record = InstrumentRecord(
                id=uuid4(),
                symbol=symbol,
                provider=provider,
                asset_type=asset_type,
                base_currency=base_currency,
                quote_currency=quote_currency,
                price_precision=price_precision,
                quantity_precision=quantity_precision,
                is_active=True,
                constraints=dict(constraints_dict),
            )
            self._instruments[record.id] = record
            self._by_provider_symbol[key] = record.id
            return record


class InMemoryCandleRepository(CandleRepository):
    """Deterministic candle repository for tests.

    ``save_many`` deduplicates on
    ``(instrument_id, provider, timeframe, open_time, price_basis)`` and returns
    the count of candles that were actually inserted (not the batch size).  The
    no-op-on-conflict behaviour matches the SQLAlchemy ``ON CONFLICT DO NOTHING``.
    """

    def __init__(self) -> None:
        self._candles: dict[tuple[UUID, str, str, datetime, str], CandleDomain] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _make_key(candle: CandleDomain) -> tuple[UUID, str, str, datetime, str]:
        return (
            candle.instrument_id,
            candle.provider,
            candle.timeframe,
            candle.open_time,
            candle.price_basis,
        )

    @property
    def count(self) -> int:
        """Total unique candles stored (for test inspection)."""
        return len(self._candles)

    async def save_many(self, candles: list[CandleDomain]) -> int:
        if not candles:
            return 0
        inserted = 0
        async with self._lock:
            for candle in candles:
                key = self._make_key(candle)
                if key not in self._candles:
                    self._candles[key] = candle
                    inserted += 1
        return inserted

    def contains(self, candle: CandleDomain) -> bool:
        """Check whether a specific candle was persisted (for test inspection)."""
        return self._make_key(candle) in self._candles

    async def get_candles(
        self,
        instrument_id: UUID,
        timeframe: str,
        start: datetime,
        end: datetime,
        price_basis: str = "trade",
    ) -> list[CandleDomain]:
        validate_candle_query(instrument_id, timeframe, start, end, price_basis)
        async with self._lock:
            matching = [
                candle
                for candle in self._candles.values()
                if candle.instrument_id == instrument_id
                and candle.timeframe == timeframe
                and candle.price_basis == price_basis
                and candle.is_complete
                and start <= candle.open_time <= end
            ]
        return sorted(matching, key=lambda candle: (candle.open_time, self._make_key(candle)))


class InMemoryJournalRepository:
    """Concurrency-safe journal repository used by service and contract tests."""

    def __init__(self, entries: list[JournalEntry] | None = None) -> None:
        self._entries = {entry.id: entry for entry in entries or []}
        self._by_trade_id = {entry.trade_id: entry.id for entry in entries or []}
        self._lock = asyncio.Lock()

    async def create(self, entry: JournalEntry) -> JournalEntry:
        async with self._lock:
            existing_id = self._by_trade_id.get(entry.trade_id)
            if existing_id is not None:
                return self._entries[existing_id]
            self._entries[entry.id] = entry
            self._by_trade_id[entry.trade_id] = entry.id
            return entry

    async def save(self, entry: JournalEntry) -> JournalEntry:
        return await self.create(entry)

    async def get(self, entry_id: UUID) -> JournalEntry | None:
        async with self._lock:
            return self._entries.get(entry_id)

    async def get_by_trade_id(self, trade_id: UUID) -> JournalEntry | None:
        async with self._lock:
            entry_id = self._by_trade_id.get(trade_id)
            return self._entries.get(entry_id) if entry_id is not None else None

    async def list_entries(
        self,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        bot_id: UUID | None = None,
    ) -> list[JournalEntry]:
        from backend.persistence.repositories.journal import _validate_range

        _validate_range(start, end)
        async with self._lock:
            entries = [
                entry
                for entry in self._entries.values()
                if (start is None or entry.opened_at >= start)
                and (end is None or entry.opened_at <= end)
                and (bot_id is None or entry.bot_id == bot_id)
            ]
        return sorted(entries, key=lambda entry: (entry.opened_at, entry.id))

    async def update_notes(self, entry_id: UUID, notes: str | None) -> JournalEntry | None:
        async with self._lock:
            entry = self._entries.get(entry_id)
            if entry is None:
                return None
            updated = replace(entry, notes=notes, updated_at=datetime.now(UTC))
            self._entries[entry_id] = updated
            return updated


class InMemoryExecutionRepository:
    """Concurrency-safe execution repository used by broker and repository tests."""

    def __init__(self) -> None:
        self._orders: dict[str, Order] = {}
        self._broker_orders: dict[str, Order] = {}
        self._fills: dict[str, Fill] = {}
        self._positions: dict[tuple[UUID, UUID, AccountMode], Position] = {}
        self._trades: dict[UUID, Trade] = {}
        self._reconciliations: dict[UUID, ReconciliationRecord] = {}
        self._funding: dict[tuple[UUID, UUID, AccountMode, object], FundingAdjustment] = {}
        self._lock = asyncio.Lock()

    async def create_order(self, order: Order) -> Order:
        async with self._lock:
            existing = self._orders.get(order.client_order_id)
            if existing is not None:
                return existing
            self._orders[order.client_order_id] = order
            if order.broker_order_id:
                self._broker_orders[order.broker_order_id] = order
            return order

    async def get_order_by_client_id(self, client_order_id: str) -> Order | None:
        async with self._lock:
            return self._orders.get(client_order_id)

    async def get_order_by_broker_id(self, broker_order_id: str) -> Order | None:
        async with self._lock:
            return self._broker_orders.get(broker_order_id)

    async def get_non_terminal_orders(
        self, *, account_id: UUID, mode: AccountMode
    ) -> list[Order]:
        async with self._lock:
            return [
                order
                for order in self._orders.values()
                if order.account_id == account_id
                and (order.mode or mode) == mode
                and order.status.value not in {"filled", "canceled", "rejected", "expired"}
            ]

    async def get_orders(self, *, account_id: UUID, mode: AccountMode) -> list[Order]:
        async with self._lock:
            return [
                order
                for order in self._orders.values()
                if order.account_id == account_id and order.mode == mode
            ]

    async def update_order(self, order: Order) -> Order:
        async with self._lock:
            self._orders[order.client_order_id] = order
            if order.broker_order_id:
                self._broker_orders[order.broker_order_id] = order
            return order

    async def append_fill(self, fill: Fill) -> Fill:
        async with self._lock:
            if fill.broker_fill_id is not None:
                existing = self._fills.get(fill.broker_fill_id)
                if existing is not None:
                    return existing
                self._fills[fill.broker_fill_id] = fill
            return fill

    async def get_fill_by_broker_id(self, broker_fill_id: str) -> Fill | None:
        async with self._lock:
            return self._fills.get(broker_fill_id)

    async def get_fills(self, *, account_id: UUID, mode: AccountMode) -> list[Fill]:
        async with self._lock:
            order_modes = {
                order.id: order.mode or AccountMode.PAPER for order in self._orders.values()
            }
            return [
                fill
                for fill in self._fills.values()
                if fill.account_id == account_id and order_modes.get(fill.order_id) == mode
            ]

    async def save_funding_adjustment(self, adjustment: FundingAdjustment) -> FundingAdjustment:
        timestamp = adjustment.funding_timestamp or adjustment.applied_at
        if adjustment.instrument_id is None:
            raise ValueError("funding adjustment requires an instrument")
        key = (adjustment.account_id, adjustment.instrument_id, adjustment.mode, timestamp)
        async with self._lock:
            existing = self._funding.get(key)
            if existing is not None:
                return existing
            self._funding[key] = adjustment
            return adjustment

    async def get_funding_adjustments(
        self, *, account_id: UUID, instrument_id: UUID | None, mode: AccountMode
    ) -> list[FundingAdjustment]:
        async with self._lock:
            return sorted(
                (
                    adjustment
                    for adjustment in self._funding.values()
                    if adjustment.account_id == account_id
                    and (instrument_id is None or adjustment.instrument_id == instrument_id)
                    and adjustment.mode == mode
                ),
                key=lambda adjustment: adjustment.funding_timestamp or adjustment.applied_at,
            )

    async def get_positions(self, *, account_id: UUID, mode: AccountMode) -> list[Position]:
        async with self._lock:
            return [
                position
                for position in self._positions.values()
                if position.account_id == account_id and position.mode == mode
            ]

    async def get_position(
        self, *, account_id: UUID, instrument_id: UUID, mode: AccountMode
    ) -> Position | None:
        async with self._lock:
            return self._positions.get((account_id, instrument_id, mode))

    async def save_position(self, position: Position) -> Position:
        async with self._lock:
            key = (position.account_id, position.instrument_id, position.mode)
            if position.status.value == "closed":
                self._positions.pop(key, None)
            else:
                self._positions[key] = position
            return position

    async def save_trade(self, trade: Trade) -> Trade:
        async with self._lock:
            self._trades[trade.id] = trade
            return trade

    async def get_trade_by_position(self, position_id: UUID) -> Trade | None:
        async with self._lock:
            return next(
                (
                    trade
                    for trade in self._trades.values()
                    if trade.position_id == position_id and trade.status.value == "entered"
                ),
                None,
            )

    async def record(self, result: ReconciliationRecord) -> ReconciliationRecord:
        async with self._lock:
            self._reconciliations.setdefault(result.id, result)
            return self._reconciliations[result.id]

    async def get_reconciliation(self, reconciliation_id: UUID) -> ReconciliationRecord | None:
        async with self._lock:
            return self._reconciliations.get(reconciliation_id)
