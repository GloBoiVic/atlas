"""Runtime ownership and lifecycle supervision for isolated bot pipelines."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from typing import Final
from uuid import UUID, uuid4

import structlog

from backend.core.account_mode import AccountMode
from backend.core.clock import Clock
from backend.core.events import BotStatusChanged, EventBus
from backend.persistence.repositories.protocols import (
    LifecycleUpdate,
    ReconciliationRecord,
    SupervisorRepositories,
)
from backend.worker.protocols import (
    BotPipeline,
    BotSnapshot,
    PipelineFactory,
    Reconciler,
    ReconciliationResult,
)

logger = structlog.get_logger(__name__)

HEARTBEAT_INTERVAL: Final[float] = 10.0


class LeaseOwnershipLost(RuntimeError):
    """Raised when a supervisor can no longer prove ownership of a bot."""


class BotSupervisor:
    """Own isolated bot pipelines and their durable lifecycle state."""

    def __init__(
        self,
        repositories: SupervisorRepositories,
        factory: PipelineFactory,
        reconciler: Reconciler,
        clock: Clock,
        event_bus: EventBus,
    ) -> None:
        self.repositories = repositories
        self.factory = factory
        self.reconciler = reconciler
        self.clock = clock
        self.event_bus = event_bus
        self.worker_id = uuid4()
        self._pipelines: dict[str, BotPipeline] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._lock_holders: dict[str, asyncio.Task[object]] = {}
        self._claimed: set[str] = set()
        self._ownership_lost: set[str] = set()
        self._operations: set[asyncio.Task[object]] = set()
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._shutting_down = False

    async def start(self, bot_id: str) -> bool:
        """Claim, start, reconcile, and enable one bot pipeline."""
        return await self._start(bot_id)

    async def restore(self, bot_id: str) -> bool:
        """Explicitly restore one bot, including a previously paused bot."""
        return await self._start(bot_id)

    async def restore_active(self) -> list[str]:
        """Restore only persisted RUNNING and STARTING bots."""
        if self._shutting_down:
            return []
        candidates = await self.repositories.get_restore_candidates()
        bot_ids = [bot.id for bot in candidates if bot.status in {"running", "starting"}]
        await asyncio.gather(*(self.restore(bot_id) for bot_id in bot_ids))
        return bot_ids

    async def pause(self, bot_id: str) -> bool:
        """Disable execution while preserving the feed and strategy pipeline."""
        operation = asyncio.current_task()
        assert operation is not None
        self._operations.add(operation)
        try:
            async with self._bot_lock(bot_id):
                bot = await self.repositories.get(bot_id)
                if bot is None:
                    return False
                if bot.status == "paused":
                    return True
                pipeline = self._pipelines.get(bot_id)
                if pipeline is not None:
                    pipeline.set_execution_enabled(False)
                await self._persist(
                    bot_id,
                    LifecycleUpdate(
                        desired_status="paused",
                        status="paused",
                        started_at=bot.started_at,
                        stopped_at=None,
                    ),
                )
                return True
        finally:
            self._operations.discard(operation)

    async def stop(self, bot_id: str) -> bool:
        """Stop one pipeline, persist STOPPED, and release its lease."""
        return await self._stop(bot_id)

    async def heartbeat_once(self) -> None:
        """Renew all claimed leases without allowing one bot to stop the loop."""
        await asyncio.gather(
            *(self._heartbeat_bot(bot_id) for bot_id in tuple(self._claimed)),
            return_exceptions=True,
        )

    async def shutdown(self) -> None:
        """Gate new starts, finish operations, stop pipelines, and release all leases."""
        self._shutting_down = True
        while self._operations:
            await asyncio.gather(*tuple(self._operations), return_exceptions=True)

        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._heartbeat_task
            self._heartbeat_task = None

        bot_ids = tuple(self._claimed | set(self._pipelines))
        results = await asyncio.gather(
            *(self._stop(bot_id) for bot_id in bot_ids),
            return_exceptions=True,
        )
        # A failed stop/persistence operation must not prevent other leases from release.
        await asyncio.gather(
            *(self._release_claim(bot_id) for bot_id in tuple(self._claimed)),
            return_exceptions=True,
        )
        failures = [result for result in results if isinstance(result, Exception)]
        if failures:
            raise failures[0]

    async def _start(self, bot_id: str) -> bool:
        operation = asyncio.current_task()
        assert operation is not None
        self._operations.add(operation)
        pipeline: BotPipeline | None = None
        claimed = False
        success = False
        try:
            if self._shutting_down:
                return False
            async with self._bot_lock(bot_id):
                if self._shutting_down:
                    return False
                bot_record = await self.repositories.get(bot_id)
                if bot_record is None:
                    return False
                existing_pipeline = self._pipelines.get(bot_id)
                if (
                    existing_pipeline is not None
                    and bot_record.status == "running"
                    and existing_pipeline.execution_enabled
                    and bot_id not in self._ownership_lost
                ):
                    return True
                lease = await self.repositories.claim(bot_id, str(self.worker_id), self.clock.now())
                if lease is None:
                    return False
                claimed = True
                self._claimed.add(bot_id)
                self._ownership_lost.discard(bot_id)
                self._ensure_heartbeat_task()
                await self._assert_owned(bot_id)
                bot = BotSnapshot(
                    id=bot_record.id,
                    name=bot_record.name,
                    account_id=bot_record.account_id,
                    broker=bot_record.broker,
                    mode=bot_record.mode,
                    instrument=bot_record.instrument,
                    timeframe=bot_record.timeframe,
                    desired_status="running",
                    status="starting",
                    last_error=bot_record.last_error,
                )
                await self._persist(
                    bot_id,
                    LifecycleUpdate(
                        desired_status="running",
                        status="starting",
                        started_at=self.clock.now(),
                        stopped_at=None,
                    ),
                )
                await self._assert_owned(bot_id)
                pipeline = existing_pipeline or self.factory.create_pipeline(bot)
                self._pipelines[bot_id] = pipeline
                pipeline.set_execution_enabled(False)
                if existing_pipeline is None:
                    await pipeline.start()
                await self._assert_owned(bot_id)
                result = await self.reconciler.reconcile(bot)
                await self._assert_owned(bot_id)
                await self._record_reconciliation(bot, result)
                await self._assert_owned(bot_id)
                if not result.is_safe_to_execute:
                    raise RuntimeError(result.error or f"reconciliation {result.status.value}")
                pipeline.set_execution_enabled(True)
                await self._assert_owned(bot_id)
                await self._persist(
                    bot_id,
                    LifecycleUpdate(
                        desired_status="running",
                        status="running",
                        started_at=self.clock.now(),
                        stopped_at=None,
                    ),
                )
                await self._assert_owned(bot_id)
                success = True
                return True
        except asyncio.CancelledError:
            if claimed:
                await asyncio.shield(self._abort_start(bot_id, pipeline))
            raise
        except Exception as exception:
            logger.exception(
                "bot_pipeline_start_failed",
                bot_id=bot_id,
                worker_id=str(self.worker_id),
                error=str(exception),
            )
            if claimed:
                await self._abort_start(bot_id, pipeline, str(exception))
            return False
        finally:
            if claimed and not success:
                await asyncio.shield(self._release_claim(bot_id))
            self._operations.discard(operation)

    async def _stop(self, bot_id: str) -> bool:
        operation = asyncio.current_task()
        assert operation is not None
        self._operations.add(operation)
        try:
            async with self._bot_lock(bot_id):
                bot = await self.repositories.get(bot_id)
                if bot is None:
                    return False
                pipeline = self._pipelines.get(bot_id)
                failure_owned = bot_id in self._ownership_lost or bot.status == "error"
                if bot.status == "stopped" and pipeline is None:
                    await self._release_claim(bot_id)
                    return True
                if pipeline is not None:
                    pipeline.set_execution_enabled(False)
                failure: BaseException | None = None
                try:
                    if not failure_owned:
                        await self._persist(
                            bot_id,
                            LifecycleUpdate(
                                desired_status="stopped",
                                status="stopping",
                                started_at=bot.started_at,
                                stopped_at=None,
                            ),
                        )
                    if pipeline is not None:
                        await pipeline.stop()
                except asyncio.CancelledError as exception:
                    failure = exception
                except Exception as exception:
                    failure = exception
                    logger.exception("bot_stop_failed", bot_id=bot_id, error=str(exception))
                finally:
                    self._pipelines.pop(bot_id, None)
                    try:
                        if not failure_owned:
                            await self._persist(
                                bot_id,
                                LifecycleUpdate(
                                    desired_status="stopped",
                                    status="stopped",
                                    stopped_at=self.clock.now(),
                                ),
                            )
                    except asyncio.CancelledError as exception:
                        failure = failure or exception
                    except Exception as exception:
                        failure = failure or exception
                        logger.exception(
                            "bot_stop_persist_failed",
                            bot_id=bot_id,
                            error=str(exception),
                        )
                    await asyncio.shield(self._release_claim(bot_id))
                if failure is not None:
                    raise failure
                return True
        finally:
            self._operations.discard(operation)

    async def _heartbeat_bot(self, bot_id: str) -> None:
        try:
            owned = await self.repositories.renew(bot_id, str(self.worker_id), self.clock.now())
        except Exception as exception:
            logger.exception(
                "bot_lease_renewal_failed",
                bot_id=bot_id,
                worker_id=str(self.worker_id),
                error=str(exception),
                error_type=type(exception).__name__,
            )
            await self._handle_lease_failure(bot_id, str(exception))
            return
        if owned:
            return
        await self._handle_lease_failure(bot_id, "bot lease ownership lost")

    async def _handle_lease_failure(self, bot_id: str, error: str) -> None:
        self._ownership_lost.add(bot_id)
        async with self._bot_lock(bot_id):
            pipeline = self._pipelines.get(bot_id)
            if pipeline is not None:
                pipeline.set_execution_enabled(False)
            try:
                await self._persist_error(bot_id, error)
            except Exception:
                logger.exception("bot_lease_loss_persist_failed", bot_id=bot_id)
            if pipeline is not None:
                try:
                    await pipeline.stop()
                except Exception:
                    logger.exception(
                        "bot_lease_loss_cleanup_failed",
                        bot_id=bot_id,
                        worker_id=str(self.worker_id),
                    )
                finally:
                    self._pipelines.pop(bot_id, None)
            await self._release_claim(bot_id)
        logger.error("bot_lease_ownership_lost", bot_id=bot_id, worker_id=str(self.worker_id))

    async def _heartbeat_loop(self) -> None:
        try:
            while not self._shutting_down:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                await self.heartbeat_once()
        except asyncio.CancelledError:
            raise

    async def _assert_owned(self, bot_id: str) -> None:
        if self._shutting_down or bot_id in self._ownership_lost:
            raise LeaseOwnershipLost("bot lease ownership lost")
        if not await self.repositories.renew(bot_id, str(self.worker_id), self.clock.now()):
            self._ownership_lost.add(bot_id)
            raise LeaseOwnershipLost("bot lease ownership lost")

    async def _abort_start(
        self,
        bot_id: str,
        pipeline: BotPipeline | None,
        error: str | None = None,
    ) -> None:
        async with self._bot_lock(bot_id):
            if pipeline is not None:
                pipeline.set_execution_enabled(False)
                self._pipelines.pop(bot_id, None)
                try:
                    await pipeline.stop()
                except Exception:
                    logger.exception("bot_pipeline_cleanup_failed", bot_id=bot_id)
            if error is not None:
                try:
                    await self._persist_error(bot_id, error)
                except Exception:
                    logger.exception("bot_start_error_persist_failed", bot_id=bot_id)
            await self._release_claim(bot_id)

    async def _release_claim(self, bot_id: str) -> None:
        if bot_id not in self._claimed:
            return
        try:
            released = await self.repositories.release(
                bot_id,
                str(self.worker_id),
                self.clock.now(),
            )
        except Exception:
            logger.exception("bot_lease_release_failed", bot_id=bot_id)
            return
        if released:
            self._claimed.discard(bot_id)
            self._ownership_lost.discard(bot_id)

    def _ensure_heartbeat_task(self) -> None:
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    def _lock_for(self, bot_id: str) -> asyncio.Lock:
        return self._locks.setdefault(bot_id, asyncio.Lock())

    @asynccontextmanager
    async def _bot_lock(self, bot_id: str) -> AsyncIterator[None]:
        """Serialize bot operations while allowing failure handling to be reentrant."""
        operation = asyncio.current_task()
        assert operation is not None
        if self._lock_holders.get(bot_id) is operation:
            yield
            return
        lock = self._lock_for(bot_id)
        await lock.acquire()
        self._lock_holders[bot_id] = operation
        try:
            yield
        finally:
            self._lock_holders.pop(bot_id, None)
            lock.release()

    async def _persist(self, bot_id: str, state: LifecycleUpdate) -> None:
        record = await self.repositories.persist_lifecycle(bot_id, state)
        if record is None:
            return
        logger.info(
            "bot_status_changed",
            bot_id=bot_id,
            worker_id=str(self.worker_id),
            status=record.status,
            desired_status=record.desired_status,
        )
        await self.event_bus.publish(
            BotStatusChanged(
                account_id=_as_uuid(record.account_id),
                bot_id=_as_uuid(record.id),
                mode=AccountMode(record.mode),
            ),
        )

    async def _persist_error(self, bot_id: str, error: str) -> None:
        bot = await self.repositories.get(bot_id)
        if bot is None:
            return
        await self._persist(
            bot_id,
            LifecycleUpdate(
                desired_status=bot.desired_status,
                status="error",
                last_error=error,
                started_at=bot.started_at,
                stopped_at=bot.stopped_at,
            ),
        )

    async def _record_reconciliation(self, bot: BotSnapshot, result: ReconciliationResult) -> None:
        await self.repositories.record(
            ReconciliationRecord(
                account_id=bot.account_id,
                bot_id=bot.id,
                status=result.status.value,
                broker_snapshot=result.broker_snapshot,
                differences=result.differences,
                started_at=self.clock.now(),
                completed_at=self.clock.now(),
                error_message=result.error,
            ),
        )


def _as_uuid(value: str) -> UUID:
    """Convert repository IDs at the domain-event boundary."""
    return UUID(value)
