# mypy: disable-error-code="no-untyped-def"
"""Tests for InstrumentRepository and CandleRepository implementations.

Covers both the SQLAlchemy (PostgreSQL-aware) and in-memory implementations.
"""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import JSON, MetaData
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from backend.data.models import Candle as CandleDomain
from backend.persistence.models import Candle as OrmCandle
from backend.persistence.models import Instrument as OrmInstrument
from backend.persistence.repositories.memory import (
    InMemoryCandleRepository,
    InMemoryInstrumentRepository,
)
from backend.persistence.repositories.protocols import InstrumentRecord
from backend.persistence.repositories.sqlalchemy import (
    SqlAlchemyCandleRepository,
    SqlAlchemyInstrumentRepository,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_INSTRUMENT_ID = UUID("a0000000-0000-0000-0000-000000000001")
_OTHER_ID = UUID("a0000000-0000-0000-0000-000000000002")


def make_candle(
    instrument_id: UUID = _INSTRUMENT_ID,
    provider: str = "binance",
    timeframe: str = "1m",
    open_time: datetime | None = None,
    open_price: Decimal = Decimal("50000"),
    high: Decimal | None = None,
    low: Decimal | None = None,
    close: Decimal | None = None,
    base_volume: Decimal = Decimal("10"),
) -> CandleDomain:
    if open_time is None:
        open_time = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    return CandleDomain(
        instrument_id=instrument_id,
        provider=provider,
        timeframe=timeframe,
        open_time=open_time,
        open=open_price,
        high=high or open_price,
        low=low or open_price,
        close=close or open_price,
        base_volume=base_volume,
        is_complete=True,
    )


# ---------------------------------------------------------------------------
# 1. Regression: resolve must not overwrite existing instrument fields
# ---------------------------------------------------------------------------


class TestSqlAlchemyInstrumentRepositoryResolve:
    """Verify that ``resolve`` on the SQLAlchemy repo never clobbers an existing
    row when the caller does not supply metadata.
    """

    @pytest.fixture
    async def repo(self) -> AsyncGenerator[SqlAlchemyInstrumentRepository, None]:
        engine = create_async_engine(
            "sqlite+aiosqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        sqlite_metadata = MetaData()
        sqlite_table = OrmInstrument.__table__.to_metadata(sqlite_metadata)  # type: ignore[attr-defined]
        for col in sqlite_table.columns:
            if isinstance(col.type, JSONB):
                col.type = JSON()
        async with engine.begin() as conn:
            await conn.run_sync(sqlite_metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        repo = SqlAlchemyInstrumentRepository(factory)
        yield repo
        await engine.dispose()

    @pytest.mark.asyncio
    async def test_resolve_creates_new_instrument(self, repo) -> None:
        record = await repo.resolve(symbol="BTCUSDT", provider="binance")
        assert record.symbol == "BTCUSDT"
        assert record.provider == "binance"
        assert record.asset_type == "crypto"

    @pytest.mark.asyncio
    async def test_resolve_existing_does_not_overwrite_asset_type(self, repo) -> None:
        # First insert with an explicit upsert that sets a known asset_type.
        await repo.upsert(
            symbol="ETHUSDT",
            provider="binance",
            asset_type="crypto",
            price_precision=2,
            quantity_precision=5,
        )

        # Now resolve without providing asset_type — must NOT overwrite.
        record = await repo.resolve(symbol="ETHUSDT", provider="binance")

        assert record.asset_type == "crypto"
        assert record.price_precision == 2
        assert record.quantity_precision == 5

    @pytest.mark.asyncio
    async def test_resolve_existing_does_not_overwrite_constraints(self, repo) -> None:
        await repo.upsert(
            symbol="BNBUSDT",
            provider="binance",
            asset_type="crypto",
            constraints={"min_qty": "0.01", "tick_size": "0.1"},
        )

        record = await repo.resolve(symbol="BNBUSDT", provider="binance")

        assert record.constraints == {"min_qty": "0.01", "tick_size": "0.1"}
        assert record.is_active is True

    @pytest.mark.asyncio
    async def test_resolve_idempotent_across_repeated_calls(self, repo) -> None:
        first = await repo.resolve(symbol="ADAUSDT", provider="binance")
        second = await repo.resolve(symbol="ADAUSDT", provider="binance")

        assert first.id == second.id
        assert first.symbol == second.symbol


# ---------------------------------------------------------------------------
# 2. InMemoryInstrumentRepository contract tests
# ---------------------------------------------------------------------------


class TestInMemoryInstrumentRepository:
    @pytest.fixture
    def repo(self) -> InMemoryInstrumentRepository:
        return InMemoryInstrumentRepository()

    @pytest.mark.asyncio
    async def test_resolve_creates_new_instrument(self, repo) -> None:
        record = await repo.resolve(symbol="BTCUSDT", provider="binance")

        assert isinstance(record, InstrumentRecord)
        assert isinstance(record.id, UUID)
        assert record.symbol == "BTCUSDT"
        assert record.provider == "binance"
        assert record.asset_type == "crypto"

    @pytest.mark.asyncio
    async def test_resolve_returns_same_instrument_twice(self, repo) -> None:
        first = await repo.resolve(symbol="ETHUSDT", provider="binance")
        second = await repo.resolve(symbol="ETHUSDT", provider="binance")

        assert first.id == second.id
        assert first.asset_type == second.asset_type

    @pytest.mark.asyncio
    async def test_resolve_does_not_overwrite_existing_asset_type(self, repo) -> None:
        # Insert via upsert with explicit metadata.
        await repo.upsert(
            symbol="ETHUSDT",
            provider="binance",
            asset_type="crypto",
            price_precision=2,
        )
        # Resolve without asset_type — must keep existing values.
        record = await repo.resolve(symbol="ETHUSDT", provider="binance")

        assert record.asset_type == "crypto"
        assert record.price_precision == 2

    @pytest.mark.asyncio
    async def test_resolve_with_explicit_asset_type_on_new_record(self, repo) -> None:
        record = await repo.resolve(
            symbol="NEWCOIN", provider="binance", asset_type="crypto"
        )
        assert record.asset_type == "crypto"

    @pytest.mark.asyncio
    async def test_upsert_creates_new_instrument(self, repo) -> None:
        record = await repo.upsert(
            symbol="SOLUSDT",
            provider="binance",
            asset_type="crypto",
            price_precision=3,
            quantity_precision=4,
            constraints={"tick_size": "0.001"},
        )

        assert record.symbol == "SOLUSDT"
        assert record.price_precision == 3
        assert record.constraints == {"tick_size": "0.001"}

    @pytest.mark.asyncio
    async def test_upsert_updates_existing_instrument(self, repo) -> None:
        # Create via resolve
        first = await repo.resolve(symbol="DOGEUSDT", provider="binance")
        assert first.price_precision == 8

        # Upsert with new metadata — should update.
        updated = await repo.upsert(
            symbol="DOGEUSDT",
            provider="binance",
            asset_type="crypto",
            price_precision=5,
            constraints={"min_qty": "1"},
        )

        assert updated.id == first.id
        assert updated.price_precision == 5
        assert updated.constraints == {"min_qty": "1"}
        assert updated.is_active is True

    @pytest.mark.asyncio
    async def test_different_providers_are_independent(self, repo) -> None:
        binance = await repo.resolve(symbol="BTCUSDT", provider="binance")
        oanda = await repo.resolve(symbol="BTCUSDT", provider="oanda")

        assert binance.id != oanda.id
        assert binance.provider == "binance"
        assert oanda.provider == "oanda"


# ---------------------------------------------------------------------------
# 3. InMemoryCandleRepository contract tests
# ---------------------------------------------------------------------------


class TestInMemoryCandleRepository:
    @pytest.fixture
    def repo(self) -> InMemoryCandleRepository:
        return InMemoryCandleRepository()

    @pytest.mark.asyncio
    async def test_save_many_returns_inserted_count_for_new_candles(self, repo) -> None:
        candles = [
            make_candle(open_time=datetime(2026, 1, 1, 0, 0, tzinfo=UTC)),
            make_candle(open_time=datetime(2026, 1, 1, 1, 0, tzinfo=UTC)),
            make_candle(open_time=datetime(2026, 1, 1, 2, 0, tzinfo=UTC)),
        ]

        inserted = await repo.save_many(candles)

        assert inserted == 3
        assert repo.count == 3

    @pytest.mark.asyncio
    async def test_save_many_deduplicates_on_unique_key(self, repo) -> None:
        candles = [
            make_candle(open_time=datetime(2026, 1, 1, 0, 0, tzinfo=UTC)),
            make_candle(open_time=datetime(2026, 1, 1, 1, 0, tzinfo=UTC)),
        ]

        first = await repo.save_many(candles)
        second = await repo.save_many(candles)

        assert first == 2
        assert second == 0  # All duplicates
        assert repo.count == 2

    @pytest.mark.asyncio
    async def test_save_many_deduplicates_exact_timestamp_values(self, repo) -> None:
        first = make_candle(
            open_time=datetime(2262, 4, 11, 23, 47, 16, 854775, tzinfo=UTC)
        )
        second = make_candle(
            open_time=datetime(2262, 4, 11, 23, 47, 16, 854776, tzinfo=UTC)
        )

        inserted = await repo.save_many([first, second])

        assert inserted == 2
        assert repo.count == 2

    @pytest.mark.asyncio
    async def test_save_many_partial_deduplication(self, repo) -> None:
        existing = [
            make_candle(open_time=datetime(2026, 1, 1, 0, 0, tzinfo=UTC)),
        ]
        await repo.save_many(existing)

        batch = [
            make_candle(open_time=datetime(2026, 1, 1, 0, 0, tzinfo=UTC)),  # dup
            make_candle(open_time=datetime(2026, 1, 1, 1, 0, tzinfo=UTC)),  # new
            make_candle(open_time=datetime(2026, 1, 1, 2, 0, tzinfo=UTC)),  # new
        ]

        inserted = await repo.save_many(batch)

        assert inserted == 2
        assert repo.count == 3

    @pytest.mark.asyncio
    async def test_save_many_empty_list_returns_zero(self, repo) -> None:
        assert await repo.save_many([]) == 0
        assert repo.count == 0

    @pytest.mark.asyncio
    async def test_uniqueness_scoped_to_instrument_provider_timeframe_open_time_price_basis(
        self, repo
    ) -> None:
        """Different values for each uniqueness column produce distinct rows."""
        base = make_candle(open_time=datetime(2026, 1, 1, 0, 0, tzinfo=UTC))
        await repo.save_many([base])

        # Same candle again — dedup.
        assert await repo.save_many([base]) == 0

        # Different instrument_id.
        diff_inst = make_candle(
            instrument_id=_OTHER_ID, open_time=datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
        )
        assert await repo.save_many([diff_inst]) == 1
        assert repo.count == 2

        # Different provider.
        diff_prov = make_candle(
            provider="oanda", open_time=datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
        )
        assert await repo.save_many([diff_prov]) == 1

        # Different timeframe.
        diff_tf = make_candle(
            timeframe="1h", open_time=datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
        )
        assert await repo.save_many([diff_tf]) == 1

        # Different open_time.
        diff_ot = make_candle(open_time=datetime(2026, 1, 1, 3, 0, tzinfo=UTC))
        assert await repo.save_many([diff_ot]) == 1

        # Different price_basis.
        c = make_candle(open_time=datetime(2026, 1, 1, 0, 0, tzinfo=UTC))
        diff_pb = CandleDomain(
            instrument_id=c.instrument_id,
            provider=c.provider,
            timeframe=c.timeframe,
            open_time=c.open_time,
            price_basis="mid",
            open=c.open,
            high=c.high,
            low=c.low,
            close=c.close,
            base_volume=c.base_volume,
            is_complete=True,
        )
        assert await repo.save_many([diff_pb]) == 1

    def test_contains_method(self, repo) -> None:
        """``contains`` is a test-inspection helper (not in the protocol)."""
        import asyncio

        candle = make_candle()
        asyncio.run(repo.save_many([candle]))
        assert repo.contains(candle) is True

        other = make_candle(open_time=datetime(2026, 1, 1, 5, 0, tzinfo=UTC))
        assert repo.contains(other) is False


# ---------------------------------------------------------------------------
# 4. SqlAlchemyCandleRepository SQLite fixture coverage
# ---------------------------------------------------------------------------


class TestSqlAlchemyCandleRepository:
    @pytest.fixture
    async def repo(self) -> AsyncGenerator[SqlAlchemyCandleRepository, None]:
        engine = create_async_engine(
            "sqlite+aiosqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        sqlite_metadata = MetaData()
        for table in (OrmInstrument.__table__, OrmCandle.__table__):
            sqlite_table = table.to_metadata(sqlite_metadata)  # type: ignore[attr-defined]
            for column in sqlite_table.columns:
                if isinstance(column.type, JSONB):
                    column.type = JSON()
        async with engine.begin() as connection:
            await connection.run_sync(sqlite_metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory.begin() as session:
            session.add(
                OrmInstrument(
                    id=_INSTRUMENT_ID,
                    symbol="BTCUSDT",
                    provider="binance",
                    asset_type="crypto",
                    price_precision=8,
                    quantity_precision=8,
                )
            )
        yield SqlAlchemyCandleRepository(factory)
        await engine.dispose()

    @pytest.mark.asyncio
    async def test_save_many_returns_actual_count_for_new_candles(self, repo) -> None:
        candles = [
            make_candle(open_time=datetime(2026, 1, 1, hour, tzinfo=UTC))
            for hour in range(3)
        ]

        assert await repo.save_many(candles) == 3

    @pytest.mark.asyncio
    async def test_save_many_returns_zero_for_repeat_duplicate_batch(self, repo) -> None:
        candles = [make_candle(open_time=datetime(2026, 1, 1, tzinfo=UTC))]

        assert await repo.save_many(candles) == 1
        assert await repo.save_many(candles) == 0

    @pytest.mark.asyncio
    async def test_save_many_ignores_same_batch_duplicates(self, repo) -> None:
        candle = make_candle(open_time=datetime(2026, 1, 1, tzinfo=UTC))
        duplicate = make_candle(
            open_time=candle.open_time,
            open_price=Decimal("50001"),
        )

        assert await repo.save_many([candle, duplicate]) == 1
        assert await repo.save_many([candle]) == 0
        assert await repo.save_many([duplicate]) == 0

    @pytest.mark.asyncio
    async def test_save_many_returns_new_count_for_partial_duplicate_batch(self, repo) -> None:
        existing = make_candle(open_time=datetime(2026, 1, 1, tzinfo=UTC))
        await repo.save_many([existing])
        batch = [
            existing,
            make_candle(open_time=datetime(2026, 1, 1, 1, tzinfo=UTC)),
            make_candle(open_time=datetime(2026, 1, 1, 2, tzinfo=UTC)),
        ]

        assert await repo.save_many(batch) == 2

    @pytest.mark.asyncio
    async def test_save_many_returns_zero_for_empty_batch(self, repo) -> None:
        assert await repo.save_many([]) == 0
