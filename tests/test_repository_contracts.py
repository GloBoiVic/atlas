"""Contract tests for Feature 03 repository protocols.

These tests validate the documented contracts using in-memory implementations.
PostgreSQL-specific execution (conflict idempotency, rowcount accuracy) must
be validated against a live database in Codespaces.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from backend.data.models import Candle as CandleDomain
from backend.persistence.repositories.protocols import InstrumentRecord

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@dataclass
class _FakeRow:
    """Simulates a persisted candle row for conflict checks."""
    instrument_id: UUID
    provider: str
    timeframe: str
    open_time: datetime
    price_basis: str


def _make_candle(
    instrument_id: UUID | None = None,
    open_time: datetime | None = None,
    provider: str = "binance",
    timeframe: str = "1h",
    price_basis: str = "trade",
) -> CandleDomain:
    return CandleDomain(
        instrument_id=instrument_id or uuid4(),
        provider=provider,
        timeframe=timeframe,
        open_time=open_time or datetime(2026, 1, 1, tzinfo=UTC),
        price_basis=price_basis,
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("90"),
        close=Decimal("105"),
        base_volume=Decimal("1000"),
    )


# ---------------------------------------------------------------------------
# In-memory CandleRepository for contract testing
# ---------------------------------------------------------------------------


class _InMemoryCandleRepository:
    """In-memory implementation that enforces CandleRepository contract."""

    def __init__(self) -> None:
        self._rows: dict[tuple[object, ...], _FakeRow] = {}
        self._insert_count = 0

    async def save_many(self, candles: list[CandleDomain]) -> int:
        if not candles:
            return 0
        inserted = 0
        for c in candles:
            key = (c.instrument_id, c.provider, c.timeframe, c.open_time, c.price_basis)
            if key not in self._rows:
                self._rows[key] = _FakeRow(
                    instrument_id=c.instrument_id,
                    provider=c.provider,
                    timeframe=c.timeframe,
                    open_time=c.open_time,
                    price_basis=c.price_basis,
                )
                inserted += 1
        return inserted


# ---------------------------------------------------------------------------
# save_many contract
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_many_empty_returns_zero() -> None:
    repo = _InMemoryCandleRepository()
    count = await repo.save_many([])
    assert count == 0, "save_many([]) must return 0"


@pytest.mark.asyncio
async def test_save_many_returns_inserted_count() -> None:
    repo = _InMemoryCandleRepository()
    candle = _make_candle()
    count = await repo.save_many([candle])
    assert count == 1, "save_many with one new candle must return 1"


@pytest.mark.asyncio
async def test_save_many_conflict_is_no_op() -> None:
    """Duplicate candle returns 0 inserted — existing rows are retained unchanged."""
    repo = _InMemoryCandleRepository()
    instrument_id = uuid4()
    open_time = datetime(2026, 1, 1, tzinfo=UTC)
    candle = _make_candle(instrument_id=instrument_id, open_time=open_time)

    first = await repo.save_many([candle])
    assert first == 1

    # same identity — should be no-op
    second = await repo.save_many([candle])
    assert second == 0, "duplicate save_many must return 0 (no-op)"


@pytest.mark.asyncio
async def test_save_many_different_instrument_distinct() -> None:
    """Different instrument_id is not a conflict — count reflects all."""
    repo = _InMemoryCandleRepository()
    open_time = datetime(2026, 1, 1, tzinfo=UTC)
    a = _make_candle(instrument_id=uuid4(), open_time=open_time)
    b = _make_candle(instrument_id=uuid4(), open_time=open_time)

    count = await repo.save_many([a, b])
    assert count == 2, "two distinct candles must return 2"


@pytest.mark.asyncio
async def test_save_many_mixed_known_and_new_returns_partial_count() -> None:
    """Only unknown candles count toward the inserted total."""
    repo = _InMemoryCandleRepository()
    instrument_id = uuid4()
    open_time = datetime(2026, 1, 1, tzinfo=UTC)
    existing = _make_candle(instrument_id=instrument_id, open_time=open_time)
    await repo.save_many([existing])

    new_open_time = datetime(2026, 1, 2, tzinfo=UTC)
    new_candle = _make_candle(instrument_id=instrument_id, open_time=new_open_time)

    count = await repo.save_many([existing, new_candle])
    assert count == 1, "mixed batch: only the new candle counts"


# ---------------------------------------------------------------------------
# InstrumentRepository resolve / upsert contract
# ---------------------------------------------------------------------------


class _InMemoryInstrumentRepository:
    """In-memory implementation that reveals the resolve-defect pattern."""

    def __init__(self) -> None:
        self._instruments: dict[tuple[str, str], InstrumentRecord] = {}

    async def resolve(
        self,
        *,
        symbol: str,
        provider: str,
        asset_type: str | None = None,
    ) -> InstrumentRecord:
        """Get-or-create: if existing, return as-is; otherwise create."""
        key = (symbol, provider)
        existing = self._instruments.get(key)
        if existing is not None:
            return existing
        return await self.upsert(
            symbol=symbol,
            provider=provider,
            asset_type=asset_type or "crypto",
        )

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
        key = (symbol, provider)
        existing = self._instruments.get(key)
        if existing is not None:
            record = InstrumentRecord(
                id=existing.id,
                symbol=symbol,
                provider=provider,
                asset_type=asset_type,
                base_currency=base_currency,
                quote_currency=quote_currency,
                price_precision=price_precision,
                quantity_precision=quantity_precision,
                is_active=True,
                constraints=constraints or {},
            )
        else:
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
                constraints=constraints or {},
            )
        self._instruments[key] = record
        return record


@pytest.mark.asyncio
async def test_resolve_returns_existing_without_modification() -> None:
    """resolve must NOT overwrite fields on an existing record.

    This is the contract: 'If the row exists, returns it.'
    """
    repo = _InMemoryInstrumentRepository()

    # Create an instrument as forex
    created = await repo.upsert(
        symbol="EURUSD",
        provider="oanda",
        asset_type="forex",
        base_currency="EUR",
        quote_currency="USD",
    )
    assert created.asset_type == "forex"

    # Resolve without specifying asset_type — must NOT overwrite
    resolved = await repo.resolve(
        symbol="EURUSD",
        provider="oanda",
        # asset_type deliberately omitted
    )
    assert resolved.asset_type == "forex", (
        f"resolve overwrote asset_type: got {resolved.asset_type!r}, expected 'forex'"
    )
    assert resolved.base_currency == "EUR"
    assert resolved.quote_currency == "USD"
    assert resolved.id == created.id


@pytest.mark.asyncio
async def test_resolve_creates_when_missing() -> None:
    repo = _InMemoryInstrumentRepository()
    resolved = await repo.resolve(
        symbol="BTCUSDT",
        provider="binance",
    )
    assert resolved.provider == "binance"
    assert resolved.symbol == "BTCUSDT"
    assert resolved.asset_type == "crypto"


@pytest.mark.asyncio
async def test_upsert_updates_fields_on_conflict() -> None:
    repo = _InMemoryInstrumentRepository()
    await repo.upsert(
        symbol="ETHUSDT",
        provider="binance",
        asset_type="crypto",
        price_precision=2,
    )
    second = await repo.upsert(
        symbol="ETHUSDT",
        provider="binance",
        asset_type="crypto",
        price_precision=5,
        constraints={"min_qty": "0.01"},
    )
    assert second.price_precision == 5
    assert second.constraints == {"min_qty": "0.01"}
