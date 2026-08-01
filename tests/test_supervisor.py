from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
import structlog

from backend.core.clock import Clock
from backend.core.events import BotStatusChanged, EventBus
from backend.persistence.repositories import BotRecord, InMemorySupervisorRepositories
from backend.worker.protocols import (
    BotSnapshot,
    ReconciliationResult,
    ReconciliationStatus,
)
from backend.worker.supervisor import BotSupervisor


@pytest.fixture(autouse=True)
def isolate_structured_logging() -> None:
    structlog.configure(logger_factory=structlog.ReturnLoggerFactory())


class FakeClock(Clock):
    def __init__(self) -> None:
        self.current = datetime(2026, 1, 1, tzinfo=UTC)

    def now(self) -> datetime:
        return self.current

    def advance(self, seconds: int) -> None:
        self.current += timedelta(seconds=seconds)


class FakePipeline:
    def __init__(
        self,
        start_gate: asyncio.Event | None = None,
        fail_start: bool = False,
    ) -> None:
        self.started = False
        self.stopped = False
        self.execution_enabled = False
        self.start_gate = start_gate
        self.fail_start = fail_start

    async def start(self) -> None:
        if self.start_gate is not None:
            await self.start_gate.wait()
        if self.fail_start:
            raise RuntimeError("feed failed")
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    def set_execution_enabled(self, enabled: bool) -> None:
        self.execution_enabled = enabled


class FakeFactory:
    def __init__(
        self,
        start_gate: asyncio.Event | None = None,
        fail_start: bool = False,
    ) -> None:
        self.pipelines: dict[str, FakePipeline] = {}
        self.start_gate = start_gate
        self.fail_start = fail_start

    def create_pipeline(self, bot: BotSnapshot) -> FakePipeline:
        pipeline = FakePipeline(self.start_gate, self.fail_start)
        self.pipelines[bot.id] = pipeline
        return pipeline


class FakeReconciler:
    def __init__(self, status: ReconciliationStatus = ReconciliationStatus.MATCHED) -> None:
        self.status = status
        self.calls: list[str] = []

    async def reconcile(self, bot: BotSnapshot) -> ReconciliationResult:
        self.calls.append(bot.id)
        return ReconciliationResult(status=self.status)


def make_bot(
    *,
    status: str = "stopped",
    desired_status: str = "running",
) -> BotRecord:
    return BotRecord(
        id=str(uuid4()),
        name="momentum",
        account_id=str(uuid4()),
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


def make_supervisor(
    bots: list[BotRecord],
    *,
    status: ReconciliationStatus = ReconciliationStatus.MATCHED,
    start_gate: asyncio.Event | None = None,
    fail_start: bool = False,
) -> tuple[BotSupervisor, InMemorySupervisorRepositories, FakeFactory, FakeReconciler, FakeClock]:
    repositories = InMemorySupervisorRepositories(bots=bots)
    factory = FakeFactory(start_gate, fail_start)
    reconciler = FakeReconciler(status)
    clock = FakeClock()
    supervisor = BotSupervisor(repositories, factory, reconciler, clock, EventBus())
    return supervisor, repositories, factory, reconciler, clock


@pytest.mark.asyncio
async def test_start_claims_before_factory_and_enables_only_after_match() -> None:
    bot = make_bot()
    supervisor, repositories, factory, reconciler, _ = make_supervisor([bot])
    lease_seen = False
    original_create = factory.create_pipeline

    def create_pipeline(snapshot: BotSnapshot) -> FakePipeline:
        nonlocal lease_seen
        lease_seen = awaitable_lease_check(repositories, snapshot.id, supervisor.worker_id)
        return original_create(snapshot)

    factory.create_pipeline = create_pipeline  # type: ignore[method-assign]

    assert await supervisor.start(bot.id) is True
    current = await repositories.get(bot.id)
    assert lease_seen is True
    assert current is not None and current.status == "running"
    assert factory.pipelines[bot.id].execution_enabled is True
    assert reconciler.calls == [bot.id]
    await supervisor.shutdown()


def awaitable_lease_check(
    repositories: InMemorySupervisorRepositories,
    bot_id: str,
    worker_id: object,
) -> bool:
    lease = repositories._leases.get(bot_id)  # type: ignore[attr-defined]
    return lease is not None and lease.worker_id == str(worker_id)


@pytest.mark.asyncio
async def test_concurrent_same_bot_start_is_idempotent() -> None:
    bot = make_bot()
    supervisor, _, factory, _, _ = make_supervisor([bot])
    assert await asyncio.gather(supervisor.start(bot.id), supervisor.start(bot.id)) == [True, True]
    assert len(factory.pipelines) == 1
    await supervisor.shutdown()


@pytest.mark.asyncio
async def test_different_bots_start_independently() -> None:
    bots = [make_bot(), make_bot()]
    supervisor, _, factory, _, _ = make_supervisor(bots)
    assert await asyncio.gather(*(supervisor.start(bot.id) for bot in bots)) == [True, True]
    assert all(pipeline.started for pipeline in factory.pipelines.values())
    await supervisor.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [ReconciliationStatus.MISMATCHED, ReconciliationStatus.FAILED])
async def test_reconciliation_failure_persists_error_and_stays_disabled(
    status: ReconciliationStatus,
) -> None:
    bot = make_bot()
    supervisor, repositories, factory, _, _ = make_supervisor([bot], status=status)
    assert await supervisor.start(bot.id) is False
    current = await repositories.get(bot.id)
    assert current is not None and current.status == "error"
    assert factory.pipelines[bot.id].execution_enabled is False
    assert factory.pipelines[bot.id].stopped is True
    await supervisor.shutdown()


@pytest.mark.asyncio
async def test_pipeline_failure_persists_error_without_retrying() -> None:
    bot = make_bot()
    supervisor, repositories, factory, reconciler, _ = make_supervisor([bot], fail_start=True)
    assert await supervisor.start(bot.id) is False
    assert await supervisor.start(bot.id) is False
    current = await repositories.get(bot.id)
    assert current is not None and current.status == "error"
    assert reconciler.calls == []
    assert factory.pipelines[bot.id].execution_enabled is False
    await supervisor.shutdown()


@pytest.mark.asyncio
async def test_pause_preserves_pipeline_and_disables_only_execution() -> None:
    bot = make_bot()
    supervisor, repositories, factory, _, _ = make_supervisor([bot])
    await supervisor.start(bot.id)
    pipeline = factory.pipelines[bot.id]
    assert await supervisor.pause(bot.id) is True
    assert pipeline.started is True and pipeline.stopped is False
    assert pipeline.execution_enabled is False
    current = await repositories.get(bot.id)
    assert current is not None and current.status == "paused"
    assert await supervisor.restore(bot.id) is True
    assert pipeline.execution_enabled is True
    await supervisor.shutdown()


@pytest.mark.asyncio
async def test_auto_restore_excludes_paused_and_error_bots() -> None:
    bots = [
        make_bot(status="running"),
        make_bot(status="starting"),
        make_bot(status="paused", desired_status="paused"),
        make_bot(status="error"),
    ]
    supervisor, _, factory, _, _ = make_supervisor(bots)
    restored = await supervisor.restore_active()
    assert set(restored) == {bots[0].id, bots[1].id}
    assert set(factory.pipelines) == set(restored)
    await supervisor.shutdown()


@pytest.mark.asyncio
async def test_heartbeat_ownership_loss_fails_closed() -> None:
    bot = make_bot()
    supervisor, repositories, factory, _, _ = make_supervisor([bot])
    await supervisor.start(bot.id)
    await repositories.release(bot.id, str(supervisor.worker_id))
    await supervisor.heartbeat_once()
    current = await repositories.get(bot.id)
    assert current is not None and current.status == "error"
    assert factory.pipelines[bot.id].execution_enabled is False
    await supervisor.shutdown()


@pytest.mark.asyncio
async def test_lifecycle_events_follow_persisted_transitions_and_shutdown_releases() -> None:
    bot = make_bot()
    supervisor, repositories, factory, _, _ = make_supervisor([bot])
    events: list[BotStatusChanged] = []

    async def collect(event: BotStatusChanged) -> None:
        events.append(event)

    supervisor.event_bus.subscribe(BotStatusChanged, collect)
    await supervisor.start(bot.id)
    await supervisor.stop(bot.id)
    assert [event.bot_id for event in events] == [UUID(bot.id)] * 4
    assert factory.pipelines[bot.id].stopped is True
    await supervisor.shutdown()
    current = await repositories.get(bot.id)
    assert current is not None and current.status == "stopped"
    assert await repositories.renew(bot.id, str(supervisor.worker_id)) is False
