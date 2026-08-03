from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from backend.persistence.repositories import (
    BotRecord,
    InMemorySupervisorRepositories,
    LifecycleUpdate,
    ReconciliationRecord,
)

_BOT_ID = UUID("00000000-0000-0000-0000-000000000001")
_ACCOUNT_ID = UUID("00000000-0000-0000-0000-000000000010")


def make_bot(
    bot_id: UUID | None = None,
    status: str = "stopped",
    desired_status: str = "running",
) -> BotRecord:
    return BotRecord(
        id=bot_id or uuid4(),
        name="momentum",
        account_id=uuid4(),
        broker="paper",
        mode="paper",
        instrument="BTCUSDT",
        timeframe="1m",
        desired_status=desired_status,
        status=status,
        last_error=None,
        started_at=None,
        stopped_at=None,
    )


@pytest.mark.asyncio
async def test_restore_candidates_exclude_stopped_bots() -> None:
    repository = InMemorySupervisorRepositories(
        bots=[make_bot(_BOT_ID), make_bot(status="stopped", desired_status="stopped")]
    )

    candidates = await repository.get_restore_candidates()

    assert [bot.id for bot in candidates] == [_BOT_ID]


@pytest.mark.asyncio
async def test_lifecycle_persistence_is_idempotent_and_updates_state() -> None:
    bot = make_bot(_BOT_ID)
    repository = InMemorySupervisorRepositories(bots=[bot])
    started_at = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
    update = LifecycleUpdate(
        desired_status="running",
        status="running",
        started_at=started_at,
    )

    first = await repository.persist_lifecycle(_BOT_ID, update)
    second = await repository.persist_lifecycle(_BOT_ID, update)

    assert first == second
    assert first is not None
    assert first.status == "running"
    assert first.started_at == started_at
    assert await repository.persist_lifecycle(uuid4(), update) is None


@pytest.mark.asyncio
async def test_reconciliation_record_is_idempotent() -> None:
    repository = InMemorySupervisorRepositories()
    rec_id = uuid4()
    result = ReconciliationRecord(
        id=rec_id,
        account_id=_ACCOUNT_ID,
        bot_id=_BOT_ID,
        status="matched",
        broker_snapshot={"balance": "100"},
    )

    first = await repository.record(result)
    second = await repository.record(
        ReconciliationRecord(
            id=rec_id,
            account_id=uuid4(),
            bot_id=None,
            status="failed",
        )
    )

    assert first == second
    assert await repository.get_reconciliation(rec_id) == result
    assert await repository.get_reconciliation(uuid4()) is None
