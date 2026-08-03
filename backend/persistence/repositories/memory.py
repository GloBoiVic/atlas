import asyncio
from datetime import datetime
from uuid import UUID, uuid4

from backend.data.models import Candle as CandleDomain
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
        self._reconciliations = {
            result.id: result for result in reconciliations or []
        }
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
        self._candles: set[tuple[UUID, str, str, datetime, str]] = set()
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
                    self._candles.add(key)
                    inserted += 1
        return inserted

    def contains(self, candle: CandleDomain) -> bool:
        """Check whether a specific candle was persisted (for test inspection)."""
        return self._make_key(candle) in self._candles
