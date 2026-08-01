from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import or_, select, update
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.sql.dml import Insert

from backend.persistence.models import Bot, BotRun, ReconciliationRun
from backend.persistence.repositories.protocols import (
    BotRecord,
    LeaseRecord,
    LifecycleUpdate,
    ReconciliationRecord,
)

if TYPE_CHECKING:
    from sqlalchemy.engine import CursorResult

LEASE_TIMEOUT = timedelta(seconds=30)


def _insert_for_dialect(dialect_name: str) -> Any:
    if dialect_name == "sqlite":
        return cast("Insert", sqlite_insert(BotRun))
    return cast("Insert", postgres_insert(BotRun))


def _claim_statement(
    bot_id: str,
    worker_id: str,
    claim_time: datetime,
    dialect_name: str = "postgresql",
) -> Insert:
    expiry = claim_time - LEASE_TIMEOUT
    insert_statement: Any = _insert_for_dialect(dialect_name)
    return cast(
        "Insert",
        insert_statement.values(
            bot_id=bot_id,
            worker_id=worker_id,
            locked_at=claim_time,
            status="starting",
            started_at=claim_time,
            last_heartbeat_at=claim_time,
        )
        .on_conflict_do_update(
            index_elements=[BotRun.bot_id],
            set_={
                "worker_id": worker_id,
                "locked_at": claim_time,
                "status": "starting",
                "last_heartbeat_at": claim_time,
            },
            where=or_(
                BotRun.worker_id.is_(None),
                BotRun.worker_id == worker_id,
                BotRun.locked_at <= expiry,
            ),
        )
        .returning(BotRun)
    )


def _reconciliation_insert_statement(
    result: ReconciliationRecord,
    dialect_name: str = "postgresql",
) -> Insert:
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


def _lease_record(run: BotRun) -> LeaseRecord:
    if run.worker_id is None or run.locked_at is None:
        raise ValueError("cannot expose an unclaimed bot run as a lease")
    return LeaseRecord(
        id=run.id,
        bot_id=run.bot_id,
        worker_id=run.worker_id,
        locked_at=run.locked_at,
        status=run.status,
        started_at=run.started_at,
        last_heartbeat_at=run.last_heartbeat_at,
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

    async def persist_lifecycle_if_owned(
        self,
        bot_id: str,
        worker_id: str,
        state: LifecycleUpdate,
        now: datetime | None = None,
    ) -> BotRecord | None:
        current_time = now or datetime.now(UTC)
        async with self._session_factory.begin() as session:
            lease = (
                await session.execute(
                    select(BotRun)
                    .where(BotRun.bot_id == bot_id)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if (
                lease is None
                or lease.worker_id != worker_id
                or lease.locked_at is None
                or lease.locked_at <= current_time - LEASE_TIMEOUT
            ):
                return None

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

    async def persist_error_if_owned(
        self,
        bot_id: str,
        worker_id: str,
        state: LifecycleUpdate,
        now: datetime | None = None,
    ) -> BotRecord | None:
        current_time = now or datetime.now(UTC)
        async with self._session_factory.begin() as session:
            lease = (
                await session.execute(
                    select(BotRun)
                    .where(BotRun.bot_id == bot_id)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if (
                lease is None
                or lease.worker_id != worker_id
                or lease.locked_at is None
                or lease.locked_at <= current_time - LEASE_TIMEOUT
            ):
                return None

            bot = (
                await session.execute(select(Bot).where(Bot.id == bot_id))
            ).scalar_one_or_none()
            if bot is None:
                return None
            bot.desired_status = state.desired_status
            bot.status = "error"
            bot.last_error = state.last_error
            bot.started_at = state.started_at
            bot.stopped_at = state.stopped_at
            await session.flush()
            return _bot_record(bot)

    async def claim(
        self,
        bot_id: str,
        worker_id: str,
        now: datetime | None = None,
    ) -> LeaseRecord | None:
        claim_time = now or datetime.now(UTC)
        async with self._session_factory.begin() as session:
            dialect_name = session.get_bind().dialect.name
            result = await session.execute(
                _claim_statement(bot_id, worker_id, claim_time, dialect_name)
            )
            run = result.scalar_one_or_none()
            return _lease_record(run) if run is not None else None

    async def renew(self, bot_id: str, worker_id: str, now: datetime | None = None) -> bool:
        heartbeat = now or datetime.now(UTC)
        async with self._session_factory.begin() as session:
            result = cast(
                "CursorResult[object]",
                await session.execute(
                    update(BotRun)
                    .where(BotRun.bot_id == bot_id, BotRun.worker_id == worker_id)
                    .values(locked_at=heartbeat, last_heartbeat_at=heartbeat)
                ),
            )
            return result.rowcount == 1

    async def release(self, bot_id: str, worker_id: str, now: datetime | None = None) -> bool:
        del now
        async with self._session_factory.begin() as session:
            result = cast(
                "CursorResult[object]",
                await session.execute(
                    update(BotRun)
                    .where(BotRun.bot_id == bot_id, BotRun.worker_id == worker_id)
                    .values(worker_id=None, locked_at=None, status="stopped")
                ),
            )
            return result.rowcount == 1

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
