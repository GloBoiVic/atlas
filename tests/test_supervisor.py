from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
import structlog

from backend.core.clock import Clock
from backend.core.events import BotStatusChanged, EventBus
from backend.persistence.repositories import (
    BotRecord,
    InMemorySupervisorRepositories,
    LeaseRecord,
    LifecycleUpdate,
)
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
        stop_gate: asyncio.Event | None = None,
        fail_stop: bool = False,
    ) -> None:
        self.started = False
        self.stopped = False
        self.execution_enabled = False
        self.start_gate = start_gate
        self.fail_start = fail_start
        self.stop_gate = stop_gate
        self.fail_stop = fail_stop

    async def start(self) -> None:
        if self.start_gate is not None:
            await self.start_gate.wait()
        if self.fail_start:
            raise RuntimeError("feed failed")
        self.started = True

    async def stop(self) -> None:
        if self.stop_gate is not None:
            await self.stop_gate.wait()
        if self.fail_stop:
            raise RuntimeError("stop failed")
        self.stopped = True

    def set_execution_enabled(self, enabled: bool) -> None:
        self.execution_enabled = enabled


class FakeFactory:
    def __init__(
        self,
        start_gate: asyncio.Event | None = None,
        fail_start: bool = False,
        stop_gate: asyncio.Event | None = None,
        fail_stop: bool = False,
    ) -> None:
        self.pipelines: dict[str, FakePipeline] = {}
        self.start_gate = start_gate
        self.fail_start = fail_start
        self.stop_gate = stop_gate
        self.fail_stop = fail_stop

    def create_pipeline(self, bot: BotSnapshot) -> FakePipeline:
        pipeline = FakePipeline(self.start_gate, self.fail_start, self.stop_gate, self.fail_stop)
        self.pipelines[bot.id] = pipeline
        return pipeline


class FakeReconciler:
    def __init__(self, status: ReconciliationStatus = ReconciliationStatus.MATCHED) -> None:
        self.status = status
        self.calls: list[str] = []

    async def reconcile(self, bot: BotSnapshot) -> ReconciliationResult:
        self.calls.append(bot.id)
        return ReconciliationResult(status=self.status)


class FailingLifecycleRepositories(InMemorySupervisorRepositories):
    async def persist_lifecycle_if_owned(
        self,
        bot_id: str,
        worker_id: str,
        state: LifecycleUpdate,
        now: datetime | None = None,
    ) -> BotRecord | None:
        if state.status == "starting":
            raise RuntimeError("persistence failed")
        return await super().persist_lifecycle_if_owned(bot_id, worker_id, state, now)


class FailingRenewalRepositories(InMemorySupervisorRepositories):
    def __init__(self, failing_bot_id: str, bots: list[BotRecord]) -> None:
        super().__init__(bots=bots)
        self.failing_bot_id = failing_bot_id
        self.fail_renewal = False

    async def renew(self, bot_id: str, worker_id: str, now: datetime | None = None) -> bool:
        if self.fail_renewal and bot_id == self.failing_bot_id:
            raise RuntimeError("renewal failed")
        return await super().renew(bot_id, worker_id, now)


class GatedRenewalRepositories(InMemorySupervisorRepositories):
    def __init__(self, bots: list[BotRecord]) -> None:
        super().__init__(bots=bots)
        self.gate_next_renewal = False
        self.renewal_started = asyncio.Event()
        self.allow_renewal = asyncio.Event()

    async def renew(self, bot_id: str, worker_id: str, now: datetime | None = None) -> bool:
        if self.gate_next_renewal:
            self.gate_next_renewal = False
            self.renewal_started.set()
            await self.allow_renewal.wait()
            return False
        return await super().renew(bot_id, worker_id, now)


class GatedErrorRepositories(InMemorySupervisorRepositories):
    def __init__(self, bots: list[BotRecord]) -> None:
        super().__init__(bots=bots)
        self.error_started = asyncio.Event()
        self.allow_error = asyncio.Event()
        self.claim_count = 0

    async def persist_error_if_owned(
        self,
        bot_id: str,
        worker_id: str,
        state: LifecycleUpdate,
        now: datetime | None = None,
    ) -> BotRecord | None:
        self.error_started.set()
        await self.allow_error.wait()
        return await super().persist_error_if_owned(bot_id, worker_id, state, now)

    async def claim(
        self,
        bot_id: str,
        worker_id: str,
        now: datetime | None = None,
    ) -> LeaseRecord | None:
        self.claim_count += 1
        return await super().claim(bot_id, worker_id, now)


class CountingReleaseRepositories(InMemorySupervisorRepositories):
    def __init__(self, bots: list[BotRecord]) -> None:
        super().__init__(bots=bots)
        self.release_calls = 0

    async def release(
        self,
        bot_id: str,
        worker_id: str,
        now: datetime | None = None,
    ) -> bool:
        self.release_calls += 1
        return await super().release(bot_id, worker_id, now)


class GatedStopRepositories(InMemorySupervisorRepositories):
    def __init__(self, bots: list[BotRecord]) -> None:
        super().__init__(bots=bots)
        self.phase: str | None = None
        self.started = asyncio.Event()
        self.allow = asyncio.Event()

    async def persist_lifecycle_if_owned(
        self,
        bot_id: str,
        worker_id: str,
        state: LifecycleUpdate,
        now: datetime | None = None,
    ) -> BotRecord | None:
        if state.status == self.phase:
            self.started.set()
            await self.allow.wait()
        return await super().persist_lifecycle_if_owned(bot_id, worker_id, state, now)


class GatedReleaseRepositories(InMemorySupervisorRepositories):
    def __init__(self, bots: list[BotRecord]) -> None:
        super().__init__(bots=bots)
        self.started = asyncio.Event()
        self.allow = asyncio.Event()

    async def release(
        self,
        bot_id: str,
        worker_id: str,
        now: datetime | None = None,
    ) -> bool:
        self.started.set()
        await self.allow.wait()
        return await super().release(bot_id, worker_id, now)


class GatedStartupRepositories(InMemorySupervisorRepositories):
    def __init__(self, bots: list[BotRecord]) -> None:
        super().__init__(bots=bots)
        self.starting_started = asyncio.Event()
        self.allow_starting = asyncio.Event()
        self.gate_starting = True

    async def persist_lifecycle_if_owned(
        self,
        bot_id: str,
        worker_id: str,
        state: LifecycleUpdate,
        now: datetime | None = None,
    ) -> BotRecord | None:
        if self.gate_starting and state.status == "starting":
            self.gate_starting = False
            self.starting_started.set()
            await self.allow_starting.wait()
        return await super().persist_lifecycle_if_owned(bot_id, worker_id, state, now)


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
    stop_gate: asyncio.Event | None = None,
    fail_stop: bool = False,
) -> tuple[
    BotSupervisor,
    InMemorySupervisorRepositories,
    FakeFactory,
    FakeReconciler,
    FakeClock,
]:
    repositories = InMemorySupervisorRepositories(bots=bots)
    factory = FakeFactory(start_gate, fail_start, stop_gate, fail_stop)
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
    assert await asyncio.gather(supervisor.start(bot.id), supervisor.start(bot.id)) == [
        True,
        True,
    ]
    assert len(factory.pipelines) == 1
    await supervisor.shutdown()


@pytest.mark.asyncio
async def test_different_bots_start_independently() -> None:
    bots = [make_bot(), make_bot()]
    supervisor, _, factory, _, _ = make_supervisor(bots)
    assert await asyncio.gather(*(supervisor.start(bot.id) for bot in bots)) == [
        True,
        True,
    ]
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
async def test_start_failure_with_stop_failure_retains_unresolved_pipeline_and_lease() -> None:
    bot = make_bot()
    supervisor, repositories, factory, _, _ = make_supervisor(
        [bot],
        fail_start=True,
        fail_stop=True,
    )

    assert await supervisor.start(bot.id) is False

    pipeline = factory.pipelines[bot.id]
    current = await repositories.get(bot.id)
    assert current is not None and current.status == "error"
    assert current.last_error is not None and "cleanup unresolved" in current.last_error
    assert pipeline.execution_enabled is False
    assert pipeline.stopped is False
    assert bot.id in supervisor._pipelines
    assert await repositories.renew(bot.id, str(supervisor.worker_id)) is True
    assert await supervisor.start(bot.id) is False

    pipeline.fail_stop = False
    await supervisor.shutdown()


@pytest.mark.asyncio
async def test_start_abort_releases_before_same_bot_start_can_reclaim() -> None:
    bot = make_bot()
    stop_gate = asyncio.Event()
    supervisor, repositories, factory, _, _ = make_supervisor(
        [bot],
        fail_start=True,
        stop_gate=stop_gate,
    )

    aborted = asyncio.create_task(supervisor.start(bot.id))
    while bot.id not in factory.pipelines:
        await asyncio.sleep(0)
    retry = asyncio.create_task(supervisor.start(bot.id))
    await asyncio.sleep(0)
    assert retry.done() is False

    factory.fail_start = False
    stop_gate.set()
    assert await aborted is False
    assert await retry is True
    assert await repositories.renew(bot.id, str(supervisor.worker_id)) is True
    await supervisor.shutdown()


@pytest.mark.asyncio
async def test_cancelled_start_with_stop_failure_retains_unresolved_pipeline_and_lease() -> None:
    bot = make_bot()
    start_gate = asyncio.Event()
    supervisor, repositories, factory, _, _ = make_supervisor(
        [bot],
        start_gate=start_gate,
        fail_stop=True,
    )
    starting = asyncio.create_task(supervisor.start(bot.id))
    while bot.id not in factory.pipelines:
        await asyncio.sleep(0)

    starting.cancel()
    with pytest.raises(asyncio.CancelledError):
        await starting

    pipeline = factory.pipelines[bot.id]
    current = await repositories.get(bot.id)
    assert current is not None and current.status == "error"
    assert current.last_error is not None and "cleanup unresolved" in current.last_error
    assert pipeline.execution_enabled is False
    assert pipeline.stopped is False
    assert bot.id in supervisor._pipelines
    assert await repositories.renew(bot.id, str(supervisor.worker_id)) is True
    assert await supervisor.start(bot.id) is False

    pipeline.fail_stop = False
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
    assert current is not None and current.status == "running"
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


@pytest.mark.asyncio
async def test_stop_persists_stopped_for_pre_existing_error() -> None:
    bot = make_bot(status="error")
    supervisor, repositories, _, _, _ = make_supervisor([bot])

    assert await supervisor.stop(bot.id) is True
    current = await repositories.get(bot.id)
    assert current is not None and current.status == "stopped"

    await supervisor.shutdown()


@pytest.mark.asyncio
async def test_shutdown_persists_stopped_for_owned_error_pipeline() -> None:
    bot = make_bot()
    supervisor, repositories, factory, _, _ = make_supervisor([bot])
    assert await supervisor.start(bot.id) is True
    await repositories.persist_lifecycle(
        bot.id,
        LifecycleUpdate(desired_status="running", status="error", last_error="test failure"),
    )

    await supervisor.shutdown()
    current = await repositories.get(bot.id)
    assert current is not None and current.status == "stopped"
    assert factory.pipelines[bot.id].stopped is True


@pytest.mark.asyncio
async def test_startup_renews_claimed_lease_while_pipeline_is_starting() -> None:
    bot = make_bot()
    gate = asyncio.Event()
    supervisor, repositories, factory, _, _ = make_supervisor([bot], start_gate=gate)
    starting = asyncio.create_task(supervisor.start(bot.id))
    while bot.id not in factory.pipelines:
        await asyncio.sleep(0)

    await supervisor.heartbeat_once()
    lease = repositories._leases[bot.id]  # type: ignore[attr-defined]
    assert lease.last_heartbeat_at is not None
    gate.set()
    assert await starting is True
    await supervisor.shutdown()


@pytest.mark.asyncio
async def test_ownership_loss_during_startup_never_enables_or_persists_running() -> None:
    bot = make_bot()
    gate = asyncio.Event()
    supervisor, repositories, factory, _, _ = make_supervisor([bot], start_gate=gate)
    starting = asyncio.create_task(supervisor.start(bot.id))
    while bot.id not in factory.pipelines:
        await asyncio.sleep(0)

    await repositories.release(bot.id, str(supervisor.worker_id))
    gate.set()
    heartbeat = asyncio.create_task(supervisor.heartbeat_once())
    assert await starting is False
    await heartbeat
    current = await repositories.get(bot.id)
    assert current is not None and current.status == "starting"
    assert factory.pipelines[bot.id].execution_enabled is False
    assert factory.pipelines[bot.id].stopped is True
    await supervisor.shutdown()


@pytest.mark.asyncio
async def test_shutdown_waits_for_inflight_start_and_stops_pipeline_started_during_shutdown() -> (
    None
):
    bot = make_bot()
    gate = asyncio.Event()
    supervisor, repositories, factory, _, _ = make_supervisor([bot], start_gate=gate)
    starting = asyncio.create_task(supervisor.start(bot.id))
    while bot.id not in factory.pipelines:
        await asyncio.sleep(0)

    shutting_down = asyncio.create_task(supervisor.shutdown())
    await asyncio.sleep(0)
    gate.set()
    assert await starting is False
    await shutting_down
    assert factory.pipelines[bot.id].stopped is True
    assert await repositories.renew(bot.id, str(supervisor.worker_id)) is False


@pytest.mark.asyncio
async def test_cancelled_start_disables_stops_and_releases_created_pipeline() -> None:
    bot = make_bot()
    gate = asyncio.Event()
    supervisor, repositories, factory, _, _ = make_supervisor([bot], start_gate=gate)
    starting = asyncio.create_task(supervisor.start(bot.id))
    while bot.id not in factory.pipelines:
        await asyncio.sleep(0)

    starting.cancel()
    with pytest.raises(asyncio.CancelledError):
        await starting
    pipeline = factory.pipelines[bot.id]
    assert pipeline.execution_enabled is False
    assert pipeline.stopped is True
    current = await repositories.get(bot.id)
    assert current is not None and current.status == "error"
    assert await repositories.renew(bot.id, str(supervisor.worker_id)) is False
    await supervisor.shutdown()


@pytest.mark.asyncio
async def test_stale_starting_persistence_cannot_overwrite_reclaimed_owner() -> None:
    bot = make_bot()
    repositories = GatedStartupRepositories([bot])
    clock = FakeClock()
    old_factory = FakeFactory()
    old_supervisor = BotSupervisor(
        repositories,
        old_factory,
        FakeReconciler(),
        clock,
        EventBus(),
    )

    old_start = asyncio.create_task(old_supervisor.start(bot.id))
    await repositories.starting_started.wait()

    clock.advance(30)
    new_factory = FakeFactory()
    new_supervisor = BotSupervisor(
        repositories,
        new_factory,
        FakeReconciler(),
        clock,
        EventBus(),
    )
    assert await new_supervisor.start(bot.id) is True

    repositories.allow_starting.set()
    assert await old_start is False
    current = await repositories.get(bot.id)
    assert current is not None and current.status == "running"
    assert new_factory.pipelines[bot.id].execution_enabled is True
    assert await repositories.renew(bot.id, str(new_supervisor.worker_id), clock.now()) is True

    await old_supervisor.shutdown()
    await new_supervisor.shutdown()


@pytest.mark.asyncio
async def test_cancelled_shutdown_finishes_cleanup_before_propagating() -> None:
    bot = make_bot()
    stop_gate = asyncio.Event()
    supervisor, repositories, factory, _, _ = make_supervisor([bot], stop_gate=stop_gate)
    assert await supervisor.start(bot.id) is True

    shutting_down = asyncio.create_task(supervisor.shutdown())
    while (await repositories.get(bot.id)).status != "stopping":  # type: ignore[union-attr]
        await asyncio.sleep(0)
    shutting_down.cancel()
    await asyncio.sleep(0)
    assert factory.pipelines[bot.id].stopped is False

    stop_gate.set()
    with pytest.raises(asyncio.CancelledError):
        await shutting_down

    current = await repositories.get(bot.id)
    assert current is not None and current.status == "stopped"
    assert factory.pipelines[bot.id].stopped is True
    assert await repositories.renew(bot.id, str(supervisor.worker_id)) is False


@pytest.mark.asyncio
async def test_cancelled_shutdown_reports_and_retains_unresolved_cleanup() -> None:
    bot = make_bot()
    supervisor, repositories, factory, _, _ = make_supervisor([bot], fail_stop=True)
    assert await supervisor.start(bot.id) is True

    shutting_down = asyncio.create_task(supervisor.shutdown())
    await asyncio.sleep(0)
    with pytest.raises(asyncio.CancelledError):
        shutting_down.cancel()
        await shutting_down

    assert bot.id in supervisor._claimed
    assert bot.id in supervisor._pipelines
    current = await repositories.get(bot.id)
    assert current is not None and current.status == "error"
    assert factory.pipelines[bot.id].stopped is False

    factory.pipelines[bot.id].fail_stop = False
    await supervisor.shutdown()


@pytest.mark.asyncio
async def test_cancelled_stop_waits_for_pipeline_before_stopped_and_release() -> None:
    bot = make_bot()
    stop_gate = asyncio.Event()
    supervisor, repositories, factory, _, _ = make_supervisor([bot], stop_gate=stop_gate)
    assert await supervisor.start(bot.id) is True
    stopped_at_events: list[bool] = []

    async def observe_transition(event: BotStatusChanged) -> None:
        del event
        stopped_at_events.append(factory.pipelines[bot.id].stopped)

    supervisor.event_bus.subscribe(BotStatusChanged, observe_transition)

    stopping = asyncio.create_task(supervisor.stop(bot.id))
    await asyncio.sleep(0)
    stopping.cancel()
    await asyncio.sleep(0)

    assert factory.pipelines[bot.id].stopped is False
    current = await repositories.get(bot.id)
    assert current is not None and current.status == "stopping"
    assert await repositories.renew(bot.id, str(supervisor.worker_id)) is True

    stop_gate.set()
    with pytest.raises(asyncio.CancelledError):
        await stopping

    current = await repositories.get(bot.id)
    assert current is not None and current.status == "stopped"
    assert stopped_at_events[-1] is True
    assert factory.pipelines[bot.id].execution_enabled is False
    assert await repositories.renew(bot.id, str(supervisor.worker_id)) is False
    await supervisor.shutdown()


@pytest.mark.asyncio
async def test_cancelled_stop_waits_for_stopping_persistence() -> None:
    bot = make_bot()
    repositories = GatedStopRepositories([bot])
    supervisor, _, factory, _, _ = make_supervisor([bot])
    supervisor.repositories = repositories
    assert await supervisor.start(bot.id) is True
    repositories.phase = "stopping"

    stopping = asyncio.create_task(supervisor.stop(bot.id))
    await repositories.started.wait()
    stopping.cancel()
    await asyncio.sleep(0)
    current = await repositories.get(bot.id)
    assert current is not None and current.status == "running"
    repositories.allow.set()
    with pytest.raises(asyncio.CancelledError):
        await stopping

    current = await repositories.get(bot.id)
    assert current is not None and current.status == "stopped"
    assert factory.pipelines[bot.id].stopped is True
    assert await repositories.renew(bot.id, str(supervisor.worker_id)) is False
    await supervisor.shutdown()


@pytest.mark.asyncio
async def test_cancelled_stop_waits_for_stopped_persistence_and_blocks_start_until_done() -> None:
    bot = make_bot()
    repositories = GatedStopRepositories([bot])
    supervisor, _, factory, _, _ = make_supervisor([bot])
    supervisor.repositories = repositories
    assert await supervisor.start(bot.id) is True
    repositories.phase = "stopped"

    stopping = asyncio.create_task(supervisor.stop(bot.id))
    await repositories.started.wait()
    stopping.cancel()
    await asyncio.sleep(0)
    assert (await repositories.get(bot.id)).status == "stopping"  # type: ignore[union-attr]
    blocked_start = asyncio.create_task(supervisor.start(bot.id))
    await asyncio.sleep(0)
    assert blocked_start.done() is False
    blocked_start.cancel()
    with pytest.raises(asyncio.CancelledError):
        await blocked_start
    repositories.allow.set()
    with pytest.raises(asyncio.CancelledError):
        await stopping

    current = await repositories.get(bot.id)
    assert current is not None and current.status == "stopped"
    assert factory.pipelines[bot.id].stopped is True
    assert await repositories.renew(bot.id, str(supervisor.worker_id)) is False
    await supervisor.shutdown()


@pytest.mark.asyncio
async def test_cancelled_stop_waits_for_lease_release() -> None:
    bot = make_bot()
    repositories = GatedReleaseRepositories([bot])
    supervisor, _, factory, _, _ = make_supervisor([bot])
    supervisor.repositories = repositories
    assert await supervisor.start(bot.id) is True

    stopping = asyncio.create_task(supervisor.stop(bot.id))
    await repositories.started.wait()
    stopping.cancel()
    await asyncio.sleep(0)
    current = await repositories.get(bot.id)
    assert current is not None and current.status == "stopped"
    assert factory.pipelines[bot.id].stopped is True
    blocked_start = asyncio.create_task(supervisor.start(bot.id))
    await asyncio.sleep(0)
    assert blocked_start.done() is False
    blocked_start.cancel()
    with pytest.raises(asyncio.CancelledError):
        await blocked_start
    repositories.allow.set()
    with pytest.raises(asyncio.CancelledError):
        await stopping

    assert bot.id not in supervisor._claimed
    assert await repositories.renew(bot.id, str(supervisor.worker_id)) is False
    await supervisor.shutdown()


@pytest.mark.asyncio
async def test_cancelled_lease_loss_cleanup_stops_pipeline_and_releases_local_claim() -> None:
    bot = make_bot()
    stop_gate = asyncio.Event()
    supervisor, repositories, factory, _, _ = make_supervisor([bot], stop_gate=stop_gate)
    assert await supervisor.start(bot.id) is True
    cleanup = asyncio.create_task(
        supervisor._handle_lease_failure(
            bot.id,
            supervisor._lease_generations[bot.id],
            "lease lost",
        )
    )
    while (await repositories.get(bot.id)).status != "error":  # type: ignore[union-attr]
        await asyncio.sleep(0)
    blocked_start = asyncio.create_task(supervisor.start(bot.id))
    await asyncio.sleep(0)
    assert blocked_start.done() is False
    blocked_start.cancel()
    with pytest.raises(asyncio.CancelledError):
        await blocked_start
    cleanup.cancel()
    await asyncio.sleep(0)
    assert factory.pipelines[bot.id].stopped is False
    stop_gate.set()
    with pytest.raises(asyncio.CancelledError):
        await cleanup

    current = await repositories.get(bot.id)
    assert current is not None and current.status == "error"
    assert factory.pipelines[bot.id].stopped is True
    assert bot.id not in supervisor._claimed
    assert await supervisor.start(bot.id) is True
    await supervisor.shutdown()


@pytest.mark.asyncio
async def test_failed_pipeline_stop_persists_error_and_retains_ownership() -> None:
    bot = make_bot()
    supervisor, repositories, factory, _, _ = make_supervisor([bot], fail_stop=True)
    assert await supervisor.start(bot.id) is True

    assert await supervisor.stop(bot.id) is False
    current = await repositories.get(bot.id)
    assert current is not None and current.status == "error"
    assert bot.id in supervisor._claimed
    assert bot.id in supervisor._pipelines
    assert await repositories.renew(bot.id, str(supervisor.worker_id)) is True

    remote = BotSupervisor(
        repositories,
        FakeFactory(),
        FakeReconciler(),
        supervisor.clock,
        EventBus(),
    )
    assert await remote.start(bot.id) is False
    await remote.shutdown()

    with pytest.raises(RuntimeError, match="could not be stopped"):
        await supervisor.shutdown()


@pytest.mark.asyncio
async def test_pause_without_pipeline_is_idempotent() -> None:
    bot = make_bot(status="paused", desired_status="paused")
    supervisor, repositories, _, _, _ = make_supervisor([bot])
    events: list[BotStatusChanged] = []

    async def collect(event: BotStatusChanged) -> None:
        events.append(event)

    supervisor.event_bus.subscribe(BotStatusChanged, collect)
    assert await supervisor.pause(bot.id) is True
    assert await supervisor.pause(bot.id) is True
    assert events == []
    await supervisor.shutdown()


@pytest.mark.asyncio
async def test_start_releases_claim_when_starting_persistence_fails() -> None:
    bot = make_bot()
    repositories = FailingLifecycleRepositories(bots=[bot])
    factory = FakeFactory()
    supervisor = BotSupervisor(repositories, factory, FakeReconciler(), FakeClock(), EventBus())

    assert await supervisor.start(bot.id) is False
    assert await repositories.renew(bot.id, str(supervisor.worker_id)) is False
    await supervisor.shutdown()


@pytest.mark.asyncio
async def test_heartbeat_renewal_failure_isolated_to_one_bot() -> None:
    bots = [make_bot(), make_bot()]
    repositories = FailingRenewalRepositories(bots[0].id, bots)
    factory = FakeFactory()
    supervisor = BotSupervisor(repositories, factory, FakeReconciler(), FakeClock(), EventBus())
    assert await asyncio.gather(*(supervisor.start(bot.id) for bot in bots)) == [
        True,
        True,
    ]

    repositories.fail_renewal = True
    await supervisor.heartbeat_once()
    assert factory.pipelines[bots[0].id].execution_enabled is False
    assert factory.pipelines[bots[0].id].stopped is True
    failed = await repositories.get(bots[0].id)
    assert failed is not None and failed.status == "error"
    assert factory.pipelines[bots[1].id].execution_enabled is True
    current = await repositories.get(bots[1].id)
    assert current is not None and current.status == "running"
    repositories.fail_renewal = False
    assert await repositories.renew(bots[0].id, str(supervisor.worker_id)) is False
    await supervisor.shutdown()


@pytest.mark.asyncio
async def test_false_release_clears_claimed_bookkeeping() -> None:
    bot = make_bot()
    repositories = CountingReleaseRepositories([bot])
    supervisor = BotSupervisor(
        repositories,
        FakeFactory(),
        FakeReconciler(),
        FakeClock(),
        EventBus(),
    )
    assert await supervisor.start(bot.id) is True

    await repositories.release(bot.id, str(supervisor.worker_id))
    release_calls = repositories.release_calls
    await supervisor.heartbeat_once()
    assert bot.id not in supervisor._claimed
    assert repositories.release_calls == release_calls + 1

    await supervisor.heartbeat_once()
    assert repositories.release_calls == release_calls + 1
    await supervisor.shutdown()


@pytest.mark.asyncio
async def test_lease_failure_holds_bot_lock_before_concurrent_start_can_reclaim() -> None:
    bot = make_bot()
    repositories = GatedErrorRepositories([bot])
    supervisor = BotSupervisor(
        repositories,
        FakeFactory(),
        FakeReconciler(),
        FakeClock(),
        EventBus(),
    )
    assert await supervisor.start(bot.id) is True
    failure = asyncio.create_task(
        supervisor._handle_lease_failure(
            bot.id,
            supervisor._lease_generations[bot.id],
            "lease lost",
        )
    )
    await repositories.error_started.wait()
    starting = asyncio.create_task(supervisor.start(bot.id))
    await asyncio.sleep(0)
    assert starting.done() is False
    assert repositories.claim_count == 1
    assert bot.id in repositories._leases  # type: ignore[attr-defined]
    repositories.allow_error.set()
    await failure
    assert await starting is True
    await supervisor.shutdown()


@pytest.mark.asyncio
async def test_concurrent_stop_cannot_overwrite_lease_failure_error() -> None:
    bot = make_bot()
    repositories = GatedErrorRepositories([bot])
    supervisor = BotSupervisor(
        repositories,
        FakeFactory(),
        FakeReconciler(),
        FakeClock(),
        EventBus(),
    )
    assert await supervisor.start(bot.id) is True
    failure = asyncio.create_task(
        supervisor._handle_lease_failure(
            bot.id,
            supervisor._lease_generations[bot.id],
            "lease lost",
        )
    )
    await repositories.error_started.wait()
    stopping = asyncio.create_task(supervisor.stop(bot.id))
    await asyncio.sleep(0)
    assert stopping.done() is False
    repositories.allow_error.set()
    await failure
    assert await stopping is True
    current = await repositories.get(bot.id)
    assert current is not None and current.status == "stopped"
    await supervisor.shutdown()


@pytest.mark.asyncio
async def test_stale_heartbeat_failure_after_stop_cannot_affect_reclaimed_runtime() -> None:
    bot = make_bot()
    repositories = GatedRenewalRepositories([bot])
    factory = FakeFactory()
    supervisor = BotSupervisor(
        repositories,
        factory,
        FakeReconciler(),
        FakeClock(),
        EventBus(),
    )
    assert await supervisor.start(bot.id) is True
    old_pipeline = factory.pipelines[bot.id]

    repositories.gate_next_renewal = True
    heartbeat = asyncio.create_task(supervisor.heartbeat_once())
    await repositories.renewal_started.wait()
    assert await supervisor.stop(bot.id) is True
    assert await supervisor.start(bot.id) is True
    new_pipeline = factory.pipelines[bot.id]

    repositories.allow_renewal.set()
    await heartbeat

    current = await repositories.get(bot.id)
    assert current is not None and current.status == "running"
    assert old_pipeline.stopped is True
    assert new_pipeline.execution_enabled is True
    await supervisor.shutdown()


@pytest.mark.asyncio
async def test_stale_heartbeat_failure_after_cross_worker_reclaim_cannot_mutate_new_owner() -> None:
    bot = make_bot()
    repositories = GatedRenewalRepositories([bot])
    clock = FakeClock()
    old_factory = FakeFactory()
    old_supervisor = BotSupervisor(
        repositories,
        old_factory,
        FakeReconciler(),
        clock,
        EventBus(),
    )
    assert await old_supervisor.start(bot.id) is True
    old_pipeline = old_factory.pipelines[bot.id]

    repositories.gate_next_renewal = True
    heartbeat = asyncio.create_task(old_supervisor.heartbeat_once())
    await repositories.renewal_started.wait()

    clock.advance(30)
    new_factory = FakeFactory()
    new_supervisor = BotSupervisor(
        repositories,
        new_factory,
        FakeReconciler(),
        clock,
        EventBus(),
    )
    assert await new_supervisor.start(bot.id) is True
    new_pipeline = new_factory.pipelines[bot.id]
    assert bot.id in old_supervisor._claimed
    assert await repositories.renew(bot.id, str(new_supervisor.worker_id), clock.now()) is True

    repositories.allow_renewal.set()
    await heartbeat

    current = await repositories.get(bot.id)
    assert current is not None and current.status == "running"
    assert old_pipeline.stopped is True
    assert new_pipeline.execution_enabled is True
    assert await repositories.renew(bot.id, str(new_supervisor.worker_id), clock.now()) is True
    await old_supervisor.shutdown()
    await new_supervisor.shutdown()


@pytest.mark.asyncio
async def test_remote_pause_and_stop_cannot_mutate_owner_lifecycle() -> None:
    bot = make_bot()
    owner, repositories, owner_factory, _, clock = make_supervisor([bot])
    remote = BotSupervisor(repositories, FakeFactory(), FakeReconciler(), clock, EventBus())
    assert await owner.start(bot.id) is True

    assert await remote.pause(bot.id) is False
    assert await remote.stop(bot.id) is False
    current = await repositories.get(bot.id)
    assert current is not None and current.status == "running"
    assert owner_factory.pipelines[bot.id].execution_enabled is True

    await owner.shutdown()
    await remote.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("external_status", ["paused", "stopped"])
async def test_heartbeat_stops_pipeline_after_external_lifecycle_change(
    external_status: str,
) -> None:
    bot = make_bot()
    owner, repositories, factory, _, clock = make_supervisor([bot])
    assert await owner.start(bot.id) is True
    pipeline = factory.pipelines[bot.id]

    await repositories.persist_lifecycle(
        bot.id,
        LifecycleUpdate(desired_status=external_status, status=external_status),
    )
    await owner.heartbeat_once()

    current = await repositories.get(bot.id)
    assert current is not None and current.status == external_status
    assert pipeline.execution_enabled is False
    assert pipeline.stopped is True
    assert await repositories.renew(bot.id, str(owner.worker_id), clock.now()) is False
    await owner.shutdown()
