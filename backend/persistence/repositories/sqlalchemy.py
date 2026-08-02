from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.persistence.models import Bot, ReconciliationRun
from backend.persistence.repositories.protocols import (
    BotRecord,
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


class SqlAlchemySupervisorRepositories:
    """SQLAlchemy repositories that own sessions and transaction boundaries."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_restore_candidates(self) -> list[BotRecord]:
        async with self._session_factory() as session:
            result = await session.execute(select(Bot).where(Bot.desired_status != "stopped"))
            return [_bot_record(bot) for bot in result.scalars().all()]

    async def get(self, bot_id: str) -> BotRecord | None:
        async with self._session_factory() as session:
            bot = await session.get(Bot, bot_id)
            return _bot_record(bot) if bot is not None else None

    async def persist_lifecycle(self, bot_id: str, state: LifecycleUpdate) -> BotRecord | None:
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
            inserted = await session.execute(
                _reconciliation_insert_statement(result, dialect_name)
            )
            run = inserted.scalar_one_or_none()
            if run is None:
                run = await session.get(ReconciliationRun, result.id)
            if run is None:
                raise RuntimeError("reconciliation insert did not produce a row")
            return _reconciliation_record(run)

    async def get_reconciliation(self, reconciliation_id: str) -> ReconciliationRecord | None:
        async with self._session_factory() as session:
            run = await session.get(ReconciliationRun, reconciliation_id)
            return _reconciliation_record(run) if run is not None else None
