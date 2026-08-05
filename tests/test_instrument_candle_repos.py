# mypy: disable-error-code="no-untyped-def"
"""Tests for InstrumentRepository and CandleRepository implementations.

Covers both the SQLAlchemy (PostgreSQL-aware) and in-memory implementations.
"""

from collections.abc import AsyncGenerator
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, TypedDict
from uuid import UUID

import pytest
from sqlalchemy import JSON, MetaData
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from backend.backtester.models import (
    BacktestConfig,
    BacktestResult,
    BacktestRun,
    BacktestStatus,
    BacktestTrade,
)
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
_STRATEGY_VERSION_ID = UUID("a0000000-0000-0000-0000-000000000003")


class BacktestConfigValues(TypedDict):
    instrument_id: UUID
    account_id: UUID
    strategy_version_id: UUID
    timeframe: str
    start_date: datetime
    end_date: datetime
    strategy_parameters: dict[str, Any]
    risk_config: dict[str, Any]
    execution_config: dict[str, Any]
    initial_balance: Decimal


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

    @pytest.mark.asyncio
    async def test_get_candles_applies_inclusive_bounds_order_and_complete_only(self, repo) -> None:
        candles = [
            make_candle(open_time=datetime(2026, 1, 1, hour, tzinfo=UTC))
            for hour in (2, 0, 1)
        ]
        incomplete = replace(
            candles[0],
            open_time=datetime(2026, 1, 1, 3, tzinfo=UTC),
            is_complete=False,
        )
        await repo.save_many(candles + [incomplete])

        result = await repo.get_candles(
            _INSTRUMENT_ID,
            "1m",
            datetime(2026, 1, 1, 0, tzinfo=UTC),
            datetime(2026, 1, 1, 1, tzinfo=UTC),
        )

        assert [candle.open_time.hour for candle in result] == [0, 1]

    @pytest.mark.asyncio
    async def test_get_candles_selects_price_basis_and_deduplicates_identity(self, repo) -> None:
        trade = make_candle()
        mid = replace(trade, price_basis="mid", close=Decimal("50100"))
        await repo.save_many([trade, replace(trade, close=Decimal("99999")), mid])

        result = await repo.get_candles(
            _INSTRUMENT_ID, "1m", trade.open_time, trade.open_time, price_basis="mid"
        )

        assert result == [mid]

    @pytest.mark.asyncio
    async def test_get_candles_rejects_non_utc_bounds_and_allows_empty_range(self, repo) -> None:
        with pytest.raises(ValueError, match="start must be UTC"):
            await repo.get_candles(
                _INSTRUMENT_ID,
                "1m",
                datetime(2026, 1, 1),
                datetime(2026, 1, 1, tzinfo=UTC),
            )

        result = await repo.get_candles(
            _INSTRUMENT_ID,
            "1m",
            datetime(2025, 1, 1, tzinfo=UTC),
            datetime(2025, 1, 2, tzinfo=UTC),
        )
        assert result == []


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

    @pytest.mark.asyncio
    async def test_get_candles_matches_in_memory_read_semantics(self, repo) -> None:
        first = make_candle(open_time=datetime(2026, 1, 1, 0, tzinfo=UTC))
        second = make_candle(open_time=datetime(2026, 1, 1, 1, tzinfo=UTC))
        mid = replace(second, price_basis="mid")
        incomplete = replace(
            first,
            open_time=datetime(2026, 1, 1, 2, tzinfo=UTC),
            is_complete=False,
        )
        await repo.save_many([second, first, incomplete, mid])

        result = await repo.get_candles(
            _INSTRUMENT_ID,
            "1m",
            first.open_time,
            second.open_time,
        )

        assert [candle.open_time for candle in result] == [first.open_time, second.open_time]
        assert all(candle.is_complete for candle in result)

    @pytest.mark.asyncio
    async def test_get_candles_matches_in_memory_repository_for_identical_data(self, repo) -> None:
        candles = [
            make_candle(open_time=datetime(2026, 1, 1, hour, tzinfo=UTC))
            for hour in (3, 0, 2, 1)
        ]
        candles.extend(
            [
                replace(
                    candles[0],
                    is_complete=False,
                    open_time=datetime(2026, 1, 1, 4, tzinfo=UTC),
                ),
                replace(candles[0], price_basis="mid"),
            ]
        )
        memory_repo = InMemoryCandleRepository()
        await repo.save_many(candles)
        await memory_repo.save_many(candles)

        sql_result = await repo.get_candles(
            _INSTRUMENT_ID,
            "1m",
            datetime(2026, 1, 1, 1, tzinfo=UTC),
            datetime(2026, 1, 1, 3, tzinfo=UTC),
        )
        memory_result = await memory_repo.get_candles(
            _INSTRUMENT_ID,
            "1m",
            datetime(2026, 1, 1, 1, tzinfo=UTC),
            datetime(2026, 1, 1, 3, tzinfo=UTC),
        )

        assert sql_result == memory_result

    @pytest.mark.asyncio
    async def test_get_candles_uses_price_basis_and_validates_utc(self, repo) -> None:
        candle = make_candle()
        await repo.save_many([candle, replace(candle, price_basis="mid")])

        result = await repo.get_candles(
            _INSTRUMENT_ID,
            "1m",
            candle.open_time,
            candle.open_time,
            price_basis="mid",
        )
        assert [item.price_basis for item in result] == ["mid"]

        with pytest.raises(ValueError, match="end must be UTC"):
            await repo.get_candles(
                _INSTRUMENT_ID,
                "1m",
                candle.open_time,
                datetime(2026, 1, 1),
            )

        assert (
            await repo.get_candles(
                _INSTRUMENT_ID,
                "1m",
                datetime(2025, 1, 1, tzinfo=UTC),
                datetime(2025, 1, 2, tzinfo=UTC),
            )
            == []
        )


class TestBacktestContracts:
    def test_config_validates_utc_and_decimal_execution_values(self) -> None:
        values: BacktestConfigValues = {
            "instrument_id": _INSTRUMENT_ID,
            "account_id": _OTHER_ID,
            "strategy_version_id": _STRATEGY_VERSION_ID,
            "timeframe": "1m",
            "start_date": datetime(2026, 1, 1, tzinfo=UTC),
            "end_date": datetime(2026, 1, 2, tzinfo=UTC),
            "strategy_parameters": {"period": 5},
            "risk_config": {},
            "execution_config": {
                "fee_rate": Decimal("0.0005"),
                "slippage_rate": Decimal("0.0005"),
                "fill_model": "next_candle_open",
                "protective_trigger_rule": "stop_loss_first",
            },
            "initial_balance": Decimal("1000"),
        }
        config = BacktestConfig(**values)
        assert config.execution_config["fee_rate"] == Decimal("0.0005")

        with pytest.raises(TypeError, match="fee_rate must be a Decimal"):
            BacktestConfig(
                instrument_id=values["instrument_id"],
                account_id=values["account_id"],
                strategy_version_id=values["strategy_version_id"],
                timeframe=values["timeframe"],
                start_date=values["start_date"],
                end_date=values["end_date"],
                strategy_parameters=values["strategy_parameters"],
                risk_config=values["risk_config"],
                execution_config={**values["execution_config"], "fee_rate": 0.1},
                initial_balance=values["initial_balance"],
            )

    def test_trade_validates_fields_and_freezes_signal_metadata(self) -> None:
        trade = BacktestTrade(
            backtest_run_id=_OTHER_ID,
            instrument_id=_INSTRUMENT_ID,
            symbol="BTCUSDT",
            direction="buy",
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            entry_time=datetime(2026, 1, 1, tzinfo=UTC),
            exit_price=Decimal("50100"),
            pnl=Decimal("10"),
            exit_time=datetime(2026, 1, 1, 1, tzinfo=UTC),
            signal_metadata={"reason": "breakout"},
        )

        assert trade.net_pnl == Decimal("10")
        with pytest.raises(TypeError, match="metadata is immutable"):
            trade.signal_metadata["reason"] = "other"

        open_trade = BacktestTrade(
            backtest_run_id=_OTHER_ID,
            instrument_id=_INSTRUMENT_ID,
            symbol="BTCUSDT",
            direction="buy",
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            entry_time=datetime(2026, 1, 1, tzinfo=UTC),
        )
        assert open_trade.exit_price is None
        assert open_trade.exit_time is None
        assert open_trade.net_pnl is None

    @pytest.mark.parametrize(
        ("field_name", "value", "error"),
        [
            ("quantity", Decimal("0"), "quantity must be positive"),
            ("entry_time", datetime(2026, 1, 1), "entry_time must be UTC"),
            ("entry_price", 50000, "entry_price must be a Decimal"),
            ("backtest_run_id", "not-a-uuid", "backtest_run_id must be a UUID"),
        ],
    )
    def test_trade_rejects_invalid_values(
        self, field_name: str, value: object, error: str
    ) -> None:
        trade_values: dict[str, Any] = {
            "backtest_run_id": _OTHER_ID,
            "instrument_id": _INSTRUMENT_ID,
            "symbol": "BTCUSDT",
            "direction": "buy",
            "entry_price": Decimal("50000"),
            "quantity": Decimal("0.1"),
            "entry_time": datetime(2026, 1, 1, tzinfo=UTC),
        }
        trade_values[field_name] = value

        with pytest.raises((TypeError, ValueError), match=error):
            BacktestTrade(**trade_values)

    def test_run_validates_status_timestamps_and_freezes_config(self) -> None:
        run = BacktestRun(
            id=UUID("a0000000-0000-0000-0000-000000000004"),
            strategy_name="breakout",
            strategy_version="1.0.0",
            strategy_commit_sha="a" * 40,
            strategy_parameters={"period": 20},
            instrument_id=_INSTRUMENT_ID,
            symbol="BTCUSDT",
            timeframe="1m",
            data_source="database",
            dataset_id="dataset-1",
            start_date=datetime(2026, 1, 1, tzinfo=UTC),
            end_date=datetime(2026, 1, 2, tzinfo=UTC),
            risk_config={"risk_per_trade": Decimal("0.01")},
            execution_config={"fee_rate": Decimal("0.0005")},
            fill_model="next_candle_open",
            status=BacktestStatus.PENDING,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )

        assert run.result is None
        assert run.last_processed_timestamp is None
        with pytest.raises(TypeError, match="metadata is immutable"):
            run.strategy_parameters["period"] = 10

    def test_run_rejects_invalid_status_and_timestamp(self) -> None:
        run_values: dict[str, Any] = {
            "id": UUID("a0000000-0000-0000-0000-000000000004"),
            "strategy_name": "breakout",
            "strategy_version": "1.0.0",
            "strategy_commit_sha": "a" * 40,
            "strategy_parameters": {},
            "instrument_id": _INSTRUMENT_ID,
            "symbol": "BTCUSDT",
            "timeframe": "1m",
            "data_source": "database",
            "dataset_id": "dataset-1",
            "start_date": datetime(2026, 1, 1, tzinfo=UTC),
            "end_date": datetime(2026, 1, 2, tzinfo=UTC),
            "risk_config": {},
            "execution_config": {},
            "fill_model": "next_candle_open",
            "status": BacktestStatus.PENDING,
            "created_at": datetime(2026, 1, 1, tzinfo=UTC),
        }

        run_values["status"] = "pending"
        with pytest.raises(TypeError, match="status must be a BacktestStatus"):
            BacktestRun(**run_values)

        run_values["status"] = BacktestStatus.PENDING
        run_values["created_at"] = datetime(2026, 1, 1)
        with pytest.raises(ValueError, match="created_at must be UTC"):
            BacktestRun(**run_values)

    def test_status_and_result_contracts_preserve_decimal_metrics(self) -> None:
        result = BacktestResult(
            total_return=Decimal("0.125"),
            total_pnl=Decimal("125"),
            starting_equity=Decimal("1000"),
            ending_equity=Decimal("1125"),
        )
        assert BacktestStatus.PENDING.value == "pending"
        assert result.total_return == Decimal("0.125")
