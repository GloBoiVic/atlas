"""Runtime ownership and lifecycle supervision for isolated bot pipelines."""

import asyncio
from uuid import UUID

import structlog

from backend.core.clock import Clock
from backend.core.events import EventBus
from backend.persistence.repositories.protocols import (
    BotRecord,
    LifecycleUpdate,
    SupervisorRepositories,
)
from backend.worker.cleanup import await_cleanup
from backend.worker.errors import BotPipelineError
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
        self._pipelines: dict[UUID, BotPipeline] = {}
        self._locks: dict[UUID, asyncio.Lock] = {}
        self._stop_failures: set[UUID] = set()
        self._operations: set[asyncio.Task[object]] = set()
        self._shutting_down = False

    async def start(self, bot_id: UUID) -> bool:
        """Start, reconcile, and enable one bot pipeline."""
        return await self._start(bot_id)

    async def restore(self, bot_id: UUID) -> bool:
        """Explicitly restore one bot, including a previously paused bot."""
        return await self._start(bot_id)

    async def restore_active(self) -> list[UUID]:
        """Restore only persisted RUNNING and STARTING bots."""
        if self._shutting_down:
            return []
        candidates = await self.repositories.get_restore_candidates()
        bot_ids = [bot.id for bot in candidates if bot.status in {"running", "starting"}]
        await asyncio.gather(*(self.restore(bot_id) for bot_id in bot_ids))
        return bot_ids

    async def pause(self, bot_id: UUID) -> bool:
        """Disable execution while preserving the feed and strategy pipeline."""
        operation = asyncio.current_task()
        assert operation is not None
        self._operations.add(operation)
        try:
            await self._acquire_bot_lock(bot_id)
            try:
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
                record = await self.repositories.persist_lifecycle(
                    bot_id,
                    LifecycleUpdate(
                        desired_status="paused",
                        status="paused",
                        started_at=bot.started_at,
                        stopped_at=None,
                    ),
                )
                if record is None:
                    return False
                await publish_persisted_transition(self.event_bus, record)
                return True
            finally:
                self._release_bot_lock(bot_id)
        finally:
            self._operations.discard(operation)

    async def stop(self, bot_id: UUID) -> bool:
        """Stop one pipeline and persist STOPPED."""
        return await self._stop(bot_id)

    async def shutdown(self) -> None:
        """Gate new starts, finish operations, and stop owned pipelines."""
        self._shutting_down = True
        cancelled = False
        while self._operations:
            try:
                async def wait_for_operations() -> None:
                    await asyncio.gather(*tuple(self._operations), return_exceptions=True)

                await await_cleanup(wait_for_operations())
            except asyncio.CancelledError:
                cancelled = True
                logger.error(
                    "bot_shutdown_wait_cancelled",
                    bot_ids=sorted(set(self._pipelines)),
                )

        bot_ids = tuple(self._pipelines)
        async def stop_all() -> list[object]:
            return list(
                await asyncio.gather(
                    *(self._stop(bot_id) for bot_id in bot_ids),
                    return_exceptions=True,
                )
            )

        try:
            results = await await_cleanup(stop_all())
        except asyncio.CancelledError:
            cancelled = True
            results = [False] * len(bot_ids)
            logger.error(
                "bot_shutdown_cleanup_cancelled",
                bot_ids=list(bot_ids),
            )
        failures = [
            bot_id
            for bot_id, result in zip(bot_ids, results, strict=True)
            if isinstance(result, BaseException) or result is False
        ]
        unresolved = sorted(
            str(bid) for bid in (set(failures) | set(self._pipelines))
        )
        if cancelled:
            logger.error(
                "bot_shutdown_cancelled",
                bot_ids=list(bot_ids),
                unresolved_bot_ids=unresolved,
            )
            raise asyncio.CancelledError
        if failures:
            logger.error(
                "bot_shutdown_cleanup_unresolved",
                bot_ids=failures,
                unresolved_bot_ids=unresolved,
            )
            raise RuntimeError(
                "one or more bot pipelines could not be stopped: "
                + ", ".join(str(bid) for bid in failures)
            )

    async def _start(self, bot_id: UUID) -> bool:
        operation = asyncio.current_task()
        assert operation is not None
        self._operations.add(operation)
        pipeline: BotPipeline | None = None
        try:
            if self._shutting_down:
                return False
            await self._acquire_bot_lock(bot_id)
            try:
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
                ):
                    return True
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
                    strategy_version_id=bot_record.strategy_version_id,
                    config=bot_record.config,
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
                pipeline = existing_pipeline or self.factory.create_pipeline(bot)
                self._pipelines[bot_id] = pipeline
                pipeline.set_execution_enabled(False)
                if existing_pipeline is None:
                    await pipeline.start()
                result = await self.reconciler.reconcile(bot)
                await record_reconciliation(self.repositories, bot, result, self.clock)
                if not result.is_safe_to_execute:
                    raise BotPipelineError(result.error or f"reconciliation {result.status.value}")
                pipeline.set_execution_enabled(True)
                await self._persist(
                    bot_id,
                    LifecycleUpdate(
                        desired_status="running",
                        status="running",
                        started_at=self.clock.now(),
                        stopped_at=None,
                    ),
                )
                return True
            except asyncio.CancelledError:
                logger.error(
                    "bot_pipeline_start_cancelled",
                    bot_id=bot_id,
                    state="starting",
                )
                await await_cleanup(self._abort_start(bot_id, pipeline, "bot start cancelled"))
                raise
            except Exception as exception:
                logger.exception(
                    "bot_pipeline_start_failed",
                    bot_id=bot_id,
                    error=str(exception),
                )
                await self._abort_start(bot_id, pipeline, str(exception))
                return False
            finally:
                self._release_bot_lock(bot_id)
        finally:
            self._operations.discard(operation)

    async def _stop(self, bot_id: UUID) -> bool:
        operation = asyncio.current_task()
        assert operation is not None
        self._operations.add(operation)
        try:
            await self._acquire_bot_lock(bot_id)
            try:
                bot = await self.repositories.get(bot_id)
                if bot is None:
                    return False
                pipeline = self._pipelines.get(bot_id)
                if bot.status == "stopped" and pipeline is None:
                    return True
                if pipeline is not None:
                    pipeline.set_execution_enabled(False)
                return await await_cleanup(self._finalize_stop(bot_id, bot, pipeline))
            finally:
                self._release_bot_lock(bot_id)
        finally:
            self._operations.discard(operation)

    async def _abort_start(
        self,
        bot_id: UUID,
        pipeline: BotPipeline | None,
        error: str | None = None,
    ) -> bool:
        if pipeline is not None:
            pipeline.set_execution_enabled(False)
            try:
                await pipeline.stop()
            except asyncio.CancelledError:
                logger.error(
                    "bot_pipeline_cleanup_cancelled",
                    bot_id=bot_id,
                    state="starting",
                )
                self._stop_failures.add(bot_id)
                cleanup_error = error or "bot start cancelled"
                try:
                    await self._persist_error(
                        bot_id,
                        f"{cleanup_error}; pipeline cleanup unresolved: cancellation",
                    )
                except Exception:
                    logger.exception("bot_start_cleanup_error_persist_failed", bot_id=bot_id)
                return False
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
        self._stop_failures.discard(bot_id)
        return True

    async def _finalize_stop(
        self,
        bot_id: UUID,
        bot: BotRecord,
        pipeline: BotPipeline | None,
    ) -> bool:
        """Complete stop persistence and pipeline cleanup atomically to cancel."""
        try:
            record = await self.repositories.persist_lifecycle(
                bot_id,
                LifecycleUpdate(
                    desired_status="stopped",
                    status="stopping",
                    started_at=bot.started_at,
                    stopped_at=None,
                ),
            )
            if record is None:
                return False
            await publish_persisted_transition(self.event_bus, record)
            if pipeline is not None:
                await pipeline.stop()
            record = await self.repositories.persist_lifecycle(
                bot_id,
                LifecycleUpdate(
                    desired_status="stopped",
                    status="stopped",
                    stopped_at=self.clock.now(),
                ),
            )
            if record is None:
                raise BotPipelineError("stop completion lost bot persistence")
            await publish_persisted_transition(self.event_bus, record)
            self._pipelines.pop(bot_id, None)
            self._stop_failures.discard(bot_id)
            return True
        except Exception as exception:
            logger.exception("bot_stop_failed", bot_id=bot_id, error=str(exception))
            self._stop_failures.add(bot_id)
            await self._persist_stop_error(bot_id, exception)
            return False
        except asyncio.CancelledError:
            logger.error(
                "bot_stop_cleanup_cancelled",
                bot_id=bot_id,
                state="stopping",
            )
            self._stop_failures.add(bot_id)
            await self._persist_stop_error(bot_id, BotPipelineError("stop cleanup cancelled"))
            return False

    def _lock_for(self, bot_id: UUID) -> asyncio.Lock:
        return self._locks.setdefault(bot_id, asyncio.Lock())

    async def _acquire_bot_lock(self, bot_id: UUID) -> None:
        """Acquire the per-bot serialisation lock."""
        await self._lock_for(bot_id).acquire()

    def _release_bot_lock(self, bot_id: UUID) -> None:
        """Release the per-bot serialisation lock."""
        self._lock_for(bot_id).release()

    async def _persist(self, bot_id: UUID, state: LifecycleUpdate) -> None:
        record = await self.repositories.persist_lifecycle(bot_id, state)
        if record is None:
            raise BotPipelineError("bot persistence failed")
        await publish_persisted_transition(self.event_bus, record)

    async def _persist_error(self, bot_id: UUID, error: str) -> bool:
        return await persist_error(
            self.repositories,
            self.event_bus,
            bot_id,
            error,
            self.clock,
        )

    async def _persist_stop_error(self, bot_id: UUID, error: Exception) -> None:
        """Record a failed stop while retaining local ownership for cleanup retry."""
        try:
            await self._persist_error(bot_id, str(error))
        except Exception:
            logger.exception(
                "bot_stop_error_persist_failed",
                bot_id=bot_id,
                error=str(error),
            )
