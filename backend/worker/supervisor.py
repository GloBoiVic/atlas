"""Runtime ownership and lifecycle supervision for isolated bot pipelines."""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress
from typing import Final
from uuid import uuid4

import structlog

from backend.core.clock import Clock
from backend.core.events import EventBus
from backend.persistence.repositories.protocols import (
    BotRecord,
    LifecycleUpdate,
    SupervisorRepositories,
)
from backend.worker.cleanup import await_cleanup
from backend.worker.errors import LeaseOwnershipLost
from backend.worker.lifecycle import (
    persist_error,
    publish_persisted_transition,
    record_reconciliation,
)
from backend.worker.protocols import (
    BotPipeline,
    BotSnapshot,
    PipelineFactory,
    Reconciler,
)

logger = structlog.get_logger(__name__)

HEARTBEAT_INTERVAL: Final[float] = 10.0


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
        self._lease_generations: dict[str, int] = {}
        self._ownership_lost: set[str] = set()
        self._stop_failures: set[str] = set()
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
                    pipeline = self._pipelines.get(bot_id)
                    if pipeline is not None:
                        pipeline.set_execution_enabled(False)
                    return True
                pipeline = self._pipelines.get(bot_id)
                if pipeline is not None:
                    pipeline.set_execution_enabled(False)
                record = await self.repositories.persist_lifecycle_if_owned(
                    bot_id,
                    str(self.worker_id),
                    LifecycleUpdate(
                        desired_status="paused",
                        status="paused",
                        started_at=bot.started_at,
                        stopped_at=None,
                    ),
                    self.clock.now(),
                )
                if record is None:
                    return False
                await publish_persisted_transition(self.event_bus, str(self.worker_id), record)
                return True
        finally:
            self._operations.discard(operation)

    async def stop(self, bot_id: str) -> bool:
        """Stop one pipeline, persist STOPPED, and release its lease."""
        return await self._stop(bot_id)

    async def heartbeat_once(self) -> None:
        """Renew all claimed leases without allowing one bot to stop the loop."""
        await asyncio.gather(
            *(
                self._heartbeat_bot(bot_id, self._lease_generations[bot_id])
                for bot_id in tuple(self._claimed)
            ),
            return_exceptions=True,
        )

    async def shutdown(self) -> None:
        """Gate new starts, finish operations, and stop owned pipelines."""
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
        failures = [
            bot_id
            for bot_id, result in zip(bot_ids, results, strict=True)
            if isinstance(result, Exception) or result is False
        ]
        if failures:
            logger.error(
                "bot_shutdown_cleanup_unresolved",
                bot_ids=list(failures),
                worker_id=str(self.worker_id),
            )
            raise RuntimeError(
                "one or more bot pipelines could not be stopped: " + ", ".join(failures)
            )

    async def _start(self, bot_id: str) -> bool:
        operation = asyncio.current_task()
        assert operation is not None
        self._operations.add(operation)
        pipeline: BotPipeline | None = None
        claimed = False
        success = False
        abort_cleanup_succeeded = False
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
                if bot_id in self._stop_failures:
                    return False
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
                self._lease_generations[bot_id] = self._lease_generations.get(bot_id, 0) + 1
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
                await record_reconciliation(self.repositories, bot, result, self.clock)
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
                abort_cleanup_succeeded = await await_cleanup(
                    self._abort_start(bot_id, pipeline)
                )
            raise
        except Exception as exception:
            logger.exception(
                "bot_pipeline_start_failed",
                bot_id=bot_id,
                worker_id=str(self.worker_id),
                error=str(exception),
            )
            if claimed:
                abort_cleanup_succeeded = await self._abort_start(
                    bot_id,
                    pipeline,
                    str(exception),
                )
            return False
        finally:
            if claimed and not success and abort_cleanup_succeeded:
                await await_cleanup(self._release_claim(bot_id))
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
                if bot.status == "stopped" and pipeline is None:
                    return await await_cleanup(self._release_claim(bot_id))
                if bot_id not in self._claimed:
                    lease = await self.repositories.claim(
                        bot_id, str(self.worker_id), self.clock.now()
                    )
                    if lease is None:
                        return False
                    self._claimed.add(bot_id)
                    self._lease_generations[bot_id] = self._lease_generations.get(bot_id, 0) + 1
                    self._ensure_heartbeat_task()
                if pipeline is not None:
                    pipeline.set_execution_enabled(False)
                return await await_cleanup(self._finalize_stop(bot_id, bot, pipeline))
        finally:
            self._operations.discard(operation)

    async def _heartbeat_bot(self, bot_id: str, generation: int) -> None:
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
            await self._handle_lease_failure(bot_id, generation, str(exception))
            return
        if owned:
            bot = await self.repositories.get(bot_id)
            if bot is not None and (
                bot.status in {"paused", "stopped"} or bot.desired_status in {"paused", "stopped"}
            ):
                await self._handle_lease_failure(
                    bot_id, generation, "bot lifecycle changed externally"
                )
            return
        await self._handle_lease_failure(bot_id, generation, "bot lease ownership lost")

    async def _handle_lease_failure(self, bot_id: str, generation: int, error: str) -> None:
        async with self._bot_lock(bot_id):
            bot = await self.repositories.get(bot_id)
            if (
                generation != self._lease_generations.get(bot_id)
                or bot_id not in self._claimed
                or bot is None
            ):
                return
            self._ownership_lost.add(bot_id)
            pipeline = self._pipelines.get(bot_id)
            if pipeline is not None:
                pipeline.set_execution_enabled(False)
            await await_cleanup(self._finalize_lease_failure(bot_id, pipeline, bot, error))
        logger.error("bot_lease_ownership_lost", bot_id=bot_id, worker_id=str(self.worker_id))

    async def _finalize_lease_failure(
        self,
        bot_id: str,
        pipeline: BotPipeline | None,
        bot: BotRecord,
        error: str,
    ) -> None:
        """Fail closed and finish local cleanup without an interruptible await."""
        if bot.status not in {"paused", "stopped"} and bot.desired_status not in {
            "paused",
            "stopped",
        }:
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
                self._stop_failures.add(bot_id)
                return
        # Release is owner-conditional, so a false result clears local ownership without
        # touching a lease that may now belong to another worker.
        if not await self._release_claim(bot_id):
            self._stop_failures.add(bot_id)
            return
        if pipeline is not None:
            self._pipelines.pop(bot_id, None)
        self._stop_failures.discard(bot_id)

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
    ) -> bool:
        async with self._bot_lock(bot_id):
            if pipeline is not None:
                pipeline.set_execution_enabled(False)
                try:
                    await pipeline.stop()
                except Exception as exception:
                    logger.exception("bot_pipeline_cleanup_failed", bot_id=bot_id)
                    self._stop_failures.add(bot_id)
                    cleanup_error = error or "bot start cancelled"
                    try:
                        await self._persist_error(
                            bot_id,
                            f"{cleanup_error}; pipeline cleanup unresolved: {exception}",
                        )
                    except Exception:
                        logger.exception("bot_start_cleanup_error_persist_failed", bot_id=bot_id)
                    return False
                self._pipelines.pop(bot_id, None)
            if error is not None:
                try:
                    await self._persist_error(bot_id, error)
                except Exception:
                    logger.exception("bot_start_error_persist_failed", bot_id=bot_id)
            return True

    async def _finalize_stop(
        self,
        bot_id: str,
        bot: BotRecord,
        pipeline: BotPipeline | None,
    ) -> bool:
        """Complete stop persistence, pipeline cleanup, and lease release atomically to cancel."""
        try:
            record = await self.repositories.persist_lifecycle_if_owned(
                bot_id,
                str(self.worker_id),
                LifecycleUpdate(
                    desired_status="stopped",
                    status="stopping",
                    started_at=bot.started_at,
                    stopped_at=None,
                ),
                self.clock.now(),
            )
            if record is None:
                return False
            await publish_persisted_transition(self.event_bus, str(self.worker_id), record)
            if pipeline is not None:
                await pipeline.stop()
            record = await self.repositories.persist_lifecycle_if_owned(
                bot_id,
                str(self.worker_id),
                LifecycleUpdate(
                    desired_status="stopped",
                    status="stopped",
                    stopped_at=self.clock.now(),
                ),
                self.clock.now(),
            )
            if record is None:
                raise RuntimeError("stop completion lost lease ownership")
            await publish_persisted_transition(self.event_bus, str(self.worker_id), record)
            if not await self._release_claim(bot_id):
                raise RuntimeError("stop completion could not release lease")
            self._pipelines.pop(bot_id, None)
            self._stop_failures.discard(bot_id)
            return True
        except Exception as exception:
            logger.exception("bot_stop_failed", bot_id=bot_id, error=str(exception))
            self._stop_failures.add(bot_id)
            await self._persist_stop_error(bot_id, exception)
            return False

    async def _release_claim(self, bot_id: str) -> bool:
        if bot_id not in self._claimed:
            return True
        try:
            released = await self.repositories.release(
                bot_id,
                str(self.worker_id),
                self.clock.now(),
            )
        except Exception:
            logger.exception("bot_lease_release_failed", bot_id=bot_id)
            return False
        # A false result means the repository no longer considers this worker the owner.
        self._claimed.discard(bot_id)
        if released:
            self._ownership_lost.discard(bot_id)
        return True

    def _ensure_heartbeat_task(self) -> None:
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    def _lock_for(self, bot_id: str) -> asyncio.Lock:
        return self._locks.setdefault(bot_id, asyncio.Lock())

    @asynccontextmanager
    async def _bot_lock(self, bot_id: str) -> AsyncGenerator[None]:
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
        await publish_persisted_transition(self.event_bus, str(self.worker_id), record)

    async def _persist_error(self, bot_id: str, error: str) -> bool:
        return await persist_error(
            self.repositories,
            self.event_bus,
            bot_id,
            str(self.worker_id),
            error,
            self.clock,
        )

    async def _persist_stop_error(self, bot_id: str, error: Exception) -> None:
        """Record a failed stop while retaining local ownership for cleanup retry."""
        try:
            await self._persist_error(bot_id, str(error))
        except Exception:
            logger.exception(
                "bot_stop_error_persist_failed",
                bot_id=bot_id,
                worker_id=str(self.worker_id),
                error=str(error),
            )
