from datetime import UTC, datetime

import pytest

from backend.persistence.repositories import (
    BotRecord,
    InMemorySupervisorRepositories,
    LifecycleUpdate,
    ReconciliationRecord,
)


def make_bot(bot_id: str = "bot-1", desired_status: str = "running") -> BotRecord:
    return BotRecord(
        id=bot_id,
        name="momentum",
        account_id="account-1",
        broker="paper",
        mode="paper",
        instrument="BTCUSDT",
        timeframe="1m",
        desired_status=desired_status,
        status="stopped",
        last_error=None,
        started_at=None,
        stopped_at=None,
    )


@pytest.mark.asyncio
async def test_restore_candidates_exclude_stopped_bots() -> None:
    repository = InMemorySupervisorRepositories(
        bots=[make_bot("running"), make_bot("stopped", "stopped")]
    )

    candidates = await repository.get_restore_candidates()

    assert [bot.id for bot in candidates] == ["running"]


@pytest.mark.asyncio
async def test_lifecycle_persistence_is_idempotent_and_updates_state() -> None:
    repository = InMemorySupervisorRepositories(bots=[make_bot()])
    started_at = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
    update = LifecycleUpdate(
        desired_status="running",
        status="running",
        started_at=started_at,
    )

    first = await repository.persist_lifecycle("bot-1", update)
    second = await repository.persist_lifecycle("bot-1", update)

    assert first == second
    assert first is not None
    assert first.status == "running"
    assert first.started_at == started_at
    assert await repository.persist_lifecycle("missing", update) is None


@pytest.mark.asyncio
async def test_reconciliation_record_is_idempotent() -> None:
    repository = InMemorySupervisorRepositories()
    result = ReconciliationRecord(
        id="reconciliation-1",
        account_id="account-1",
        bot_id="bot-1",
        status="matched",
        broker_snapshot={"balance": "100"},
    )

    first = await repository.record(result)
    second = await repository.record(
        ReconciliationRecord(
            id="reconciliation-1",
            account_id="account-other",
            bot_id=None,
            status="failed",
        )
    )

    assert first == second
    assert await repository.get_reconciliation("reconciliation-1") == result
    assert await repository.get_reconciliation("missing") is None
