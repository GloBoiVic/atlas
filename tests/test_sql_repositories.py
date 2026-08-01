from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import JSON, MetaData
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from backend.persistence.models import (
    Account,
    Bot,
    BotRun,
    ReconciliationRun,
    Strategy,
    StrategyVersion,
)
from backend.persistence.repositories.protocols import ReconciliationRecord
from backend.persistence.repositories.sqlalchemy import (
    SqlAlchemySupervisorRepositories,
    _claim_statement,
    _reconciliation_insert_statement,
)


def compile_postgresql(statement: object) -> str:
    return str(statement.compile(dialect=postgresql.dialect()))


def test_claim_uses_atomic_upsert_and_stale_lease_predicate():
    sql = compile_postgresql(
        _claim_statement("bot-1", "worker-a", datetime(2026, 8, 1, 12, 0, tzinfo=UTC))
    )

    assert "ON CONFLICT (bot_id) DO UPDATE" in sql
    assert "locked_at <=" in sql
    assert "RETURNING" in sql


def test_reconciliation_insert_uses_database_conflict_idempotency():
    result = ReconciliationRecord(
        id="reconciliation-1",
        account_id="account-1",
        bot_id="bot-1",
        status="matched",
    )

    sql = compile_postgresql(_reconciliation_insert_statement(result))

    assert "ON CONFLICT (id) DO NOTHING" in sql
    assert "RETURNING" in sql


@pytest.fixture
async def sqlite_repository():
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
        BotRun.__table__,
        ReconciliationRun.__table__,
    ):
        sqlite_table = table.to_metadata(sqlite_metadata)
        for column in sqlite_table.columns:
            if isinstance(column.type, JSONB):
                column.type = JSON()
    async with engine.begin() as connection:
        await connection.run_sync(sqlite_metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    repository = SqlAlchemySupervisorRepositories(factory)
    async with factory.begin() as session:
        session.add(Account(id="account-1", name="paper", broker="paper", mode="paper"))
        session.add(
            Bot(
                id="bot-1",
                name="momentum",
                account_id="account-1",
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
async def test_sqlite_claim_enforces_one_current_owner(sqlite_repository):
    now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)

    first = await sqlite_repository.claim("bot-1", "worker-a", now)
    other = await sqlite_repository.claim("bot-1", "worker-b", now + timedelta(seconds=1))

    assert first is not None
    assert other is None


@pytest.mark.asyncio
async def test_sqlite_claim_replaces_expired_lease(sqlite_repository):
    now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)

    await sqlite_repository.claim("bot-1", "worker-a", now)
    replacement = await sqlite_repository.claim("bot-1", "worker-b", now + timedelta(seconds=30))

    assert replacement is not None
    assert replacement.worker_id == "worker-b"


@pytest.mark.asyncio
async def test_sqlite_reconciliation_record_is_idempotent(sqlite_repository):
    result = ReconciliationRecord(
        id="reconciliation-1",
        account_id="account-1",
        bot_id="bot-1",
        status="matched",
    )

    first = await sqlite_repository.record(result)
    second = await sqlite_repository.record(
        ReconciliationRecord(
            id="reconciliation-1",
            account_id="account-1",
            bot_id="bot-1",
            status="failed",
        )
    )

    assert first == second
