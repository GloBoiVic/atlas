from dataclasses import replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

import pytest
from sqlalchemy import JSON, MetaData
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import Insert as PostgresInsert
from sqlalchemy.dialects.sqlite import Insert as SQLiteInsert
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from backend.persistence.models import (
    Account,
    Bot,
    ReconciliationRun,
    Strategy,
    StrategyVersion,
)
from backend.persistence.repositories.protocols import (
    BotIdentityConflictError,
    ReconciliationRecord,
)
from backend.persistence.repositories.sqlalchemy import (
    SqlAlchemySupervisorRepositories,
    _candle_insert_statement,
    _reconciliation_insert_statement,
)

_ACCOUNT_ID = UUID("00000000-0000-0000-0000-000000000010")
_BOT_ID = UUID("00000000-0000-0000-0000-000000000001")
_RECONCILIATION_ID = UUID("00000000-0000-0000-0000-000000000100")


def compile_postgresql(statement: object) -> str:
    return str(statement.compile(dialect=postgresql.dialect()))  # type: ignore[attr-defined,no-untyped-call]


def test_reconciliation_insert_uses_database_conflict_idempotency() -> None:
    result = ReconciliationRecord(
        id=_RECONCILIATION_ID,
        account_id=_ACCOUNT_ID,
        bot_id=_BOT_ID,
        status="matched",
    )

    sql = compile_postgresql(_reconciliation_insert_statement(result))

    assert "ON CONFLICT (id) DO NOTHING" in sql
    assert "RETURNING" in sql


def test_candle_insert_selects_database_dialect() -> None:
    rows = [
        {
            "instrument_id": _ACCOUNT_ID,
            "provider": "binance",
            "timeframe": "1m",
            "open_time": datetime(2026, 8, 1, tzinfo=UTC),
            "price_basis": "trade",
        }
    ]

    assert isinstance(_candle_insert_statement(rows, "postgresql"), PostgresInsert)
    assert isinstance(_candle_insert_statement(rows, "sqlite"), SQLiteInsert)


@pytest.fixture
async def sqlite_repository() -> "AsyncGenerator[object, None]":
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    sqlite_metadata = MetaData()
    for table in (
        Account.__table__,
        Strategy.__table__,
        StrategyVersion.__table__,
        Bot.__table__,
        ReconciliationRun.__table__,
    ):
        sqlite_table = table.to_metadata(sqlite_metadata)  # type: ignore[attr-defined]
        for column in sqlite_table.columns:
            if isinstance(column.type, JSONB):
                column.type = JSON()
    async with engine.begin() as connection:
        await connection.run_sync(sqlite_metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    repository = SqlAlchemySupervisorRepositories(factory)
    async with factory.begin() as session:
        session.add(
            Account(id=_ACCOUNT_ID, name="paper", broker="paper", mode="paper")
        )
        session.add(
            Bot(
                id=_BOT_ID,
                name="momentum",
                account_id=_ACCOUNT_ID,
                broker="paper",
                mode="paper",
                instrument="BTCUSDT",
                timeframe="1m",
                desired_status="running",
                status="stopped",
            )
        )
    yield repository
    await engine.dispose()


@pytest.mark.asyncio
async def test_sqlite_reconciliation_record_is_idempotent(
    sqlite_repository: SqlAlchemySupervisorRepositories,
) -> None:
    result = ReconciliationRecord(
        id=_RECONCILIATION_ID,
        account_id=_ACCOUNT_ID,
        bot_id=_BOT_ID,
        status="matched",
    )

    first = await sqlite_repository.record(result)
    second = await sqlite_repository.record(
        ReconciliationRecord(
            id=_RECONCILIATION_ID,
            account_id=_ACCOUNT_ID,
            bot_id=_BOT_ID,
            status="failed",
        )
    )

    assert first == second


@pytest.mark.asyncio
async def test_sqlite_lifecycle_persistence_updates_bot(
    sqlite_repository: SqlAlchemySupervisorRepositories,
) -> None:
    from backend.persistence.repositories.protocols import LifecycleUpdate

    now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
    result = await sqlite_repository.persist_lifecycle(
        _BOT_ID,
        LifecycleUpdate(
            desired_status="running",
            status="running",
            started_at=now,
        ),
    )

    assert result is not None
    assert result.status == "running"
    assert result.desired_status == "running"
    assert isinstance(result.id, UUID)


@pytest.mark.asyncio
async def test_sqlite_get_restore_candidates_excludes_stopped(
    sqlite_repository: SqlAlchemySupervisorRepositories,
) -> None:
    candidates = await sqlite_repository.get_restore_candidates()
    assert [c.id for c in candidates] == [_BOT_ID]


@pytest.mark.asyncio
async def test_sqlite_update_rejects_duplicate_bot_identity(
    sqlite_repository: SqlAlchemySupervisorRepositories,
) -> None:
    first = await sqlite_repository.get(_BOT_ID)
    assert first is not None
    second = await sqlite_repository.create(
        replace(first, id=UUID("00000000-0000-0000-0000-000000000002"), name="second")
    )

    with pytest.raises(BotIdentityConflictError):
        await sqlite_repository.update_configuration(second.id, replace(second, name=first.name))
