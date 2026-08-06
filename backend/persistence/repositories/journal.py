"""SQLAlchemy implementation of journal persistence."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.journal.models import JournalDirection, JournalEntry
from backend.persistence.models import JournalEntryModel


def _validate_range(start: datetime | None, end: datetime | None) -> None:
    for value, name in ((start, "start"), (end, "end")):
        if value is not None and (
            value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value)
        ):
            raise ValueError(f"{name} must be UTC")
    if start is not None and end is not None and start > end:
        raise ValueError("start must not be after end")


def _domain(row: JournalEntryModel) -> JournalEntry:
    return JournalEntry(
        id=row.id,
        account_id=row.account_id,
        bot_id=row.bot_id,
        strategy_version_id=row.strategy_version_id,
        trade_id=row.trade_id,
        instrument_id=row.instrument_id,
        symbol=row.symbol,
        direction=JournalDirection(row.direction),
        entry_price=row.entry_price,
        exit_price=row.exit_price,
        quantity=row.quantity,
        pnl=row.pnl,
        strategy_name=row.strategy_name,
        signal=row.signal,
        market_conditions=row.market_conditions,
        notes=row.notes,
        risk_metadata=row.risk_metadata,
        opened_at=row.opened_at,
        closed_at=row.closed_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _row(entry: JournalEntry) -> JournalEntryModel:
    return JournalEntryModel(
        id=entry.id,
        account_id=entry.account_id,
        bot_id=entry.bot_id,
        strategy_version_id=entry.strategy_version_id,
        trade_id=entry.trade_id,
        instrument_id=entry.instrument_id,
        symbol=entry.symbol,
        direction=entry.direction.value,
        entry_price=entry.entry_price,
        exit_price=entry.exit_price,
        quantity=entry.quantity,
        pnl=entry.pnl,
        strategy_name=entry.strategy_name,
        signal=entry.signal,
        market_conditions=entry.market_conditions,
        notes=entry.notes,
        risk_metadata=entry.risk_metadata,
        opened_at=entry.opened_at,
        closed_at=entry.closed_at,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


class SqlAlchemyJournalRepository:
    """Journal repository with operation-owned async sessions."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create(self, entry: JournalEntry) -> JournalEntry:
        async with self._session_factory.begin() as session:
            values = {
                column.name: getattr(entry, column.name)
                for column in JournalEntryModel.__table__.columns
                if column.name not in {"created_at", "updated_at"}
            }
            values["direction"] = entry.direction.value
            dialect_name = session.get_bind().dialect.name
            insert_statement = (
                sqlite_insert(JournalEntryModel)
                if dialect_name == "sqlite"
                else postgres_insert(JournalEntryModel)
            )
            stmt = (
                insert_statement.values(values)
                .on_conflict_do_nothing(index_elements=[JournalEntryModel.trade_id])
                .returning(JournalEntryModel)
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if row is None:
                existing_result = await session.execute(
                    select(JournalEntryModel).where(
                        JournalEntryModel.trade_id == entry.trade_id
                    )
                )
                row = existing_result.scalar_one()
            return _domain(row)

    async def save(self, entry: JournalEntry) -> JournalEntry:
        return await self.create(entry)

    async def get(self, entry_id: UUID) -> JournalEntry | None:
        async with self._session_factory() as session:
            row = await session.get(JournalEntryModel, entry_id)
            return _domain(row) if row is not None else None

    async def get_by_trade_id(self, trade_id: UUID) -> JournalEntry | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(JournalEntryModel).where(JournalEntryModel.trade_id == trade_id)
            )
            row = result.scalar_one_or_none()
            return _domain(row) if row is not None else None

    async def list_entries(
        self,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        bot_id: UUID | None = None,
    ) -> list[JournalEntry]:
        _validate_range(start, end)
        stmt = select(JournalEntryModel)
        if start is not None:
            stmt = stmt.where(JournalEntryModel.opened_at >= start)
        if end is not None:
            stmt = stmt.where(JournalEntryModel.opened_at <= end)
        if bot_id is not None:
            stmt = stmt.where(JournalEntryModel.bot_id == bot_id)
        stmt = stmt.order_by(JournalEntryModel.opened_at, JournalEntryModel.id)
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            return [_domain(row) for row in result.scalars().all()]

    async def update_notes(self, entry_id: UUID, notes: str | None) -> JournalEntry | None:
        async with self._session_factory.begin() as session:
            row = await session.get(JournalEntryModel, entry_id)
            if row is None:
                return None
            row.notes = notes
            row.updated_at = datetime.now(UTC)
            await session.flush()
            return _domain(row)
