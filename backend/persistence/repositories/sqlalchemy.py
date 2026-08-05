from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.data.models import Candle as CandleDomain
from backend.persistence.models import Bot, Candle, Instrument, ReconciliationRun
from backend.persistence.repositories.candle_semantics import validate_candle_query
from backend.persistence.repositories.protocols import (
    BotRecord,
    InstrumentRecord,
    LifecycleUpdate,
    ReconciliationRecord,
)


def _reconciliation_insert_statement(
    result: ReconciliationRecord,
    dialect_name: str = "postgresql",
) -> object:
    insert_statement = (
        sqlite_insert(ReconciliationRun)
        if dialect_name == "sqlite"
        else postgres_insert(ReconciliationRun)
    )
    return (
        insert_statement
        .values(
            id=result.id,
            account_id=result.account_id,
            bot_id=result.bot_id,
            status=result.status,
            broker_snapshot=dict(result.broker_snapshot),
            differences=dict(result.differences),
            started_at=result.started_at,
            completed_at=result.completed_at,
            error_message=result.error_message,
        )
        .on_conflict_do_nothing(index_elements=[ReconciliationRun.id])
        .returning(ReconciliationRun)
    )


def _candle_insert_statement(
    rows: list[dict[str, Any]],
    dialect_name: str = "postgresql",
) -> Any:
    insert_statement = (
        sqlite_insert(Candle) if dialect_name == "sqlite" else postgres_insert(Candle)
    )
    return insert_statement.values(rows).on_conflict_do_nothing(
        index_elements=[
            Candle.instrument_id,
            Candle.provider,
            Candle.timeframe,
            Candle.open_time,
            Candle.price_basis,
        ],
    ).returning(Candle.id)


def _bot_record(bot: Bot) -> BotRecord:
    return BotRecord(
        id=bot.id,
        name=bot.name,
        account_id=bot.account_id,
        broker=bot.broker,
        mode=bot.mode,
        instrument=bot.instrument,
        timeframe=bot.timeframe,
        desired_status=bot.desired_status,
        status=bot.status,
        last_error=bot.last_error,
        started_at=bot.started_at,
        stopped_at=bot.stopped_at,
    )


def _candle_domain(candle: Candle) -> CandleDomain:
    open_time = (
        candle.open_time
        if candle.open_time.tzinfo
        else candle.open_time.replace(tzinfo=UTC)
    )
    close_time = (
        None
        if candle.close_time is None
        else candle.close_time
        if candle.close_time.tzinfo
        else candle.close_time.replace(tzinfo=UTC)
    )
    return CandleDomain(
        instrument_id=candle.instrument_id,
        provider=candle.provider,
        timeframe=candle.timeframe,
        open_time=open_time,
        close_time=close_time,
        price_basis=candle.price_basis,
        open=candle.open,
        high=candle.high,
        low=candle.low,
        close=candle.close,
        base_volume=candle.base_volume,
        quote_volume=candle.quote_volume,
        trade_count=candle.trade_count,
        taker_buy_base_volume=candle.taker_buy_base_volume,
        taker_buy_quote_volume=candle.taker_buy_quote_volume,
        tick_volume=candle.tick_volume,
        is_complete=candle.is_complete,
    )


def _reconciliation_record(run: ReconciliationRun) -> ReconciliationRecord:
    return ReconciliationRecord(
        id=run.id,
        account_id=run.account_id,
        bot_id=run.bot_id,
        status=run.status,
        broker_snapshot=run.broker_snapshot,
        differences=run.differences,
        started_at=run.started_at,
        completed_at=run.completed_at,
        error_message=run.error_message,
    )


def _instrument_record(instrument: Instrument) -> InstrumentRecord:
    return InstrumentRecord(
        id=instrument.id,
        symbol=instrument.symbol,
        provider=instrument.provider,
        asset_type=instrument.asset_type,
        base_currency=instrument.base_currency,
        quote_currency=instrument.quote_currency,
        price_precision=instrument.price_precision,
        quantity_precision=instrument.quantity_precision,
        is_active=instrument.is_active or False,
        constraints=instrument.constraints,
    )


class SqlAlchemySupervisorRepositories:
    """SQLAlchemy repositories that own sessions and transaction boundaries."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_restore_candidates(self) -> list[BotRecord]:
        async with self._session_factory() as session:
            result = await session.execute(select(Bot).where(Bot.desired_status != "stopped"))
            return [_bot_record(bot) for bot in result.scalars().all()]

    async def get(self, bot_id: UUID) -> BotRecord | None:
        async with self._session_factory() as session:
            bot = await session.get(Bot, bot_id)
            return _bot_record(bot) if bot is not None else None

    async def persist_lifecycle(self, bot_id: UUID, state: LifecycleUpdate) -> BotRecord | None:
        async with self._session_factory.begin() as session:
            bot = await session.get(Bot, bot_id)
            if bot is None:
                return None
            bot.desired_status = state.desired_status
            bot.status = state.status
            bot.last_error = state.last_error
            bot.started_at = state.started_at
            bot.stopped_at = state.stopped_at
            await session.flush()
            return _bot_record(bot)

    async def record(self, result: ReconciliationRecord) -> ReconciliationRecord:
        async with self._session_factory.begin() as session:
            dialect_name = session.get_bind().dialect.name
            stmt = _reconciliation_insert_statement(result, dialect_name)
            inserted = await session.execute(stmt)  # type: ignore[call-overload]
            run = inserted.scalar_one_or_none()
            if run is None:
                run = await session.get(ReconciliationRun, result.id)
            if run is None:
                raise RuntimeError("reconciliation insert did not produce a row")
            return _reconciliation_record(run)

    async def get_reconciliation(self, reconciliation_id: UUID) -> ReconciliationRecord | None:
        async with self._session_factory() as session:
            run = await session.get(ReconciliationRun, reconciliation_id)
            return _reconciliation_record(run) if run is not None else None


class SqlAlchemyInstrumentRepository:
    """Provider-aware instrument lookup and upsert.

    ``resolve`` is read-safe for existing instruments — it uses a select-then-insert
    strategy so that a caller who supplies no metadata never overwrites fields on an
    existing record.  ``upsert`` is the explicit metadata-update path.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def resolve(
        self,
        *,
        symbol: str,
        provider: str,
        asset_type: str | None = None,
    ) -> InstrumentRecord:
        async with self._session_factory() as session:
            existing = await session.execute(
                select(Instrument).where(
                    Instrument.symbol == symbol,
                    Instrument.provider == provider,
                )
            )
            row = existing.scalar_one_or_none()
            if row is not None:
                return _instrument_record(row)

        # Not found — insert without overwriting any concurrent insert.
        async with self._session_factory.begin() as session:
            dialect_name = session.get_bind().dialect.name
            insert_statement = (
                sqlite_insert(Instrument)
                if dialect_name == "sqlite"
                else postgres_insert(Instrument)
            )
            stmt = (
                insert_statement
                .values(
                    symbol=symbol,
                    provider=provider,
                    asset_type=asset_type or "crypto",
                    price_precision=8,
                    quantity_precision=8,
                )
                .on_conflict_do_nothing(
                    index_elements=[Instrument.symbol, Instrument.provider],
                )
                .returning(Instrument)
            )
            result = await session.execute(stmt)
            inserted = result.scalar_one_or_none()
            if inserted is not None:
                return _instrument_record(inserted)

            # A concurrent insert won the race — fetch the row they created.
            existing_after = await session.execute(
                select(Instrument).where(
                    Instrument.symbol == symbol,
                    Instrument.provider == provider,
                )
            )
            row_after = existing_after.scalar_one()
            return _instrument_record(row_after)

    async def get(self, instrument_id: UUID) -> InstrumentRecord | None:
        async with self._session_factory() as session:
            row = await session.get(Instrument, instrument_id)
            return _instrument_record(row) if row is not None else None

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
        async with self._session_factory.begin() as session:
            stmt = (
                postgres_insert(Instrument)
                .values(
                    symbol=symbol,
                    provider=provider,
                    asset_type=asset_type,
                    base_currency=base_currency,
                    quote_currency=quote_currency,
                    price_precision=price_precision,
                    quantity_precision=quantity_precision,
                    constraints=constraints_dict,
                )
                .on_conflict_do_update(
                    index_elements=[Instrument.symbol, Instrument.provider],
                    set_={
                        "asset_type": asset_type,
                        "base_currency": base_currency,
                        "quote_currency": quote_currency,
                        "price_precision": price_precision,
                        "quantity_precision": quantity_precision,
                        "constraints": constraints_dict,
                        "is_active": True,
                    },
                )
                .returning(Instrument)
            )
            result = await session.execute(stmt)
            instrument = result.scalar_one()
            return _instrument_record(instrument)


class SqlAlchemyCandleRepository:
    """Bulk-insert candles with conflict-safe no-op deduplication."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save_many(self, candles: list[CandleDomain]) -> int:
        if not candles:
            return 0
        rows = [
            {
                "instrument_id": c.instrument_id,
                "provider": c.provider,
                "timeframe": c.timeframe,
                "open_time": c.open_time,
                "close_time": c.close_time,
                "price_basis": c.price_basis,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "base_volume": c.base_volume,
                "quote_volume": c.quote_volume,
                "trade_count": c.trade_count,
                "taker_buy_base_volume": c.taker_buy_base_volume,
                "taker_buy_quote_volume": c.taker_buy_quote_volume,
                "tick_volume": c.tick_volume,
                "is_complete": c.is_complete,
            }
            for c in candles
        ]
        async with self._session_factory.begin() as session:
            dialect_name = session.get_bind().dialect.name
            stmt = _candle_insert_statement(rows, dialect_name)
            result = await session.execute(stmt)
            # RETURNING is reliable across the supported PostgreSQL/SQLite dialects;
            # unlike rowcount it remains correct when drivers report -1/unknown.
            return len(result.all())

    async def get_candles(
        self,
        instrument_id: UUID,
        timeframe: str,
        start: datetime,
        end: datetime,
        price_basis: str = "trade",
    ) -> list[CandleDomain]:
        validate_candle_query(instrument_id, timeframe, start, end, price_basis)
        stmt = (
            select(Candle)
            .join(Instrument, Instrument.id == Candle.instrument_id)
            .where(
                Candle.instrument_id == instrument_id,
                Instrument.provider == Candle.provider,
                Candle.timeframe == timeframe,
                Candle.price_basis == price_basis,
                Candle.is_complete.is_(True),
                Candle.open_time >= start,
                Candle.open_time <= end,
            )
            .order_by(Candle.open_time, Candle.id)
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            return [_candle_domain(candle) for candle in result.scalars().all()]
