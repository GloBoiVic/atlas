import asyncio
from datetime import UTC, datetime, timedelta

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
async def test_claim_is_owned_and_current_worker_can_reclaim() -> None:
    repository = InMemorySupervisorRepositories()
    now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)

    first = await repository.claim("bot-1", "worker-a", now)
    same_worker = await repository.claim("bot-1", "worker-a", now + timedelta(seconds=1))
    other_worker = await repository.claim("bot-1", "worker-b", now + timedelta(seconds=2))

    assert first is not None
    assert same_worker is not None
    assert same_worker.worker_id == "worker-a"
    assert other_worker is None


@pytest.mark.asyncio
async def test_expired_lease_can_be_claimed_by_another_worker() -> None:
    repository = InMemorySupervisorRepositories()
    now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)

    await repository.claim("bot-1", "worker-a", now)
    replacement = await repository.claim("bot-1", "worker-b", now + timedelta(seconds=30))

    assert replacement is not None
    assert replacement.worker_id == "worker-b"


@pytest.mark.asyncio
async def test_error_persistence_requires_current_lease_owner() -> None:
    repository = InMemorySupervisorRepositories(bots=[make_bot()])
    now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
    await repository.claim("bot-1", "worker-a", now)
    await repository.claim("bot-1", "worker-b", now + timedelta(seconds=30))

    result = await repository.persist_error_if_owned(
        "bot-1",
        "worker-a",
        LifecycleUpdate(desired_status="running", status="error", last_error="stale"),
        now + timedelta(seconds=30),
    )

    assert result is None
    current = await repository.get("bot-1")
    assert current is not None and current.status == "stopped"


@pytest.mark.asyncio
async def test_renew_and_release_require_current_owner() -> None:
    repository = InMemorySupervisorRepositories()
    now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
    await repository.claim("bot-1", "worker-a", now)

    assert await repository.renew("bot-1", "worker-b", now) is False
    assert await repository.release("bot-1", "worker-b", now) is False
    assert await repository.renew("bot-1", "worker-a", now + timedelta(seconds=10)) is True
    assert await repository.release("bot-1", "worker-a", now + timedelta(seconds=11)) is True
    assert await repository.claim("bot-1", "worker-b", now + timedelta(seconds=11)) is not None


@pytest.mark.asyncio
async def test_concurrent_claims_have_one_winner() -> None:
    repository = InMemorySupervisorRepositories()
    now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)

    results = await asyncio.gather(
        repository.claim("bot-1", "worker-a", now),
        repository.claim("bot-1", "worker-b", now),
    )

    assert sum(result is not None for result in results) == 1


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
