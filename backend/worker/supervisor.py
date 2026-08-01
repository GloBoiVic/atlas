"""Runtime ownership and lifecycle supervision for isolated bot pipelines."""

import asyncio
from contextlib import suppress
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
        candidates = await self.repositories.get_restore_candidates()
        bot_ids = [
            bot.id
            for bot in candidates
            if bot.status in {"running", "starting"}
        ]
        await asyncio.gather(*(self.restore(bot_id) for bot_id in bot_ids))
        return bot_ids

    async def pause(self, bot_id: str) -> bool:
        """Disable execution while preserving the feed and strategy pipeline."""
        async with self._lock_for(bot_id):
            bot = await self.repositories.get(bot_id)
            if bot is None:
                return False
            pipeline = self._pipelines.get(bot_id)
            if bot.status == "paused" and pipeline is not None:
                return True
            if pipeline is not None:
                pipeline.set_execution_enabled(False)
            await self._persist(
                bot_id,
                LifecycleUpdate(
                    desired_status="paused",
                    status="paused",
                    last_error=None,
                    started_at=bot.started_at,
                    stopped_at=None,
                ),
            )
            return True

    async def stop(self, bot_id: str) -> bool:
        """Stop one pipeline, persist STOPPED, and release its lease."""
        async with self._lock_for(bot_id):
            bot = await self.repositories.get(bot_id)
            if bot is None:
                return False
            pipeline = self._pipelines.get(bot_id)
            if bot.status == "stopped" and pipeline is None:
                await self.repositories.release(bot_id, str(self.worker_id), self.clock.now())
                return True
            if pipeline is not None:
                pipeline.set_execution_enabled(False)
            await self._persist(
                bot_id,
                LifecycleUpdate(
                    desired_status="stopped",
                    status="stopping",
                    last_error=None,
                    started_at=bot.started_at,
                    stopped_at=None,
                ),
            )
            try:
                if pipeline is not None:
                    await pipeline.stop()
            except Exception as exception:
                logger.exception(
                    "bot_pipeline_stop_failed",
                    bot_id=bot_id,
                    worker_id=str(self.worker_id),
                    error=str(exception),
                )
            finally:
                self._pipelines.pop(bot_id, None)
                await self._persist(
                    bot_id,
                    LifecycleUpdate(
                        desired_status="stopped",
                        status="stopped",
                        last_error=None,
                        stopped_at=self.clock.now(),
                    ),
                )
                await self.repositories.release(bot_id, str(self.worker_id), self.clock.now())
            return True

    async def heartbeat_once(self) -> None:
        """Renew all owned leases once, failing closed on ownership loss."""
        bot_ids = tuple(self._pipelines)
        await asyncio.gather(*(self._heartbeat_bot(bot_id) for bot_id in bot_ids))

    async def shutdown(self) -> None:
        """Stop every owned pipeline and release every owned lease."""
        self._shutting_down = True
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._heartbeat_task
            self._heartbeat_task = None
        await asyncio.gather(*(self.stop(bot_id) for bot_id in tuple(self._pipelines)))

    async def _start(self, bot_id: str) -> bool:
        async with self._lock_for(bot_id):
            bot_record = await self.repositories.get(bot_id)
            if bot_record is None:
                return False
            existing_pipeline = self._pipelines.get(bot_id)
            if (
                existing_pipeline is not None
                and bot_record.status == "running"
                and existing_pipeline.execution_enabled
            ):
                return True
            lease = await self.repositories.claim(bot_id, str(self.worker_id), self.clock.now())
            if lease is None:
                logger.warning(
                    "bot_lease_unavailable",
                    bot_id=bot_id,
                    worker_id=str(self.worker_id),
                )
                return False
            self._ensure_heartbeat_task()
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
            pipeline = existing_pipeline
            had_existing_pipeline = pipeline is not None
            try:
                if pipeline is None:
                    pipeline = self.factory.create_pipeline(bot)
                pipeline.set_execution_enabled(False)
                if not had_existing_pipeline:
                    await pipeline.start()
                result = await self.reconciler.reconcile(bot)
                await self._record_reconciliation(bot, result)
                if not result.is_safe_to_execute:
                    message = result.error or f"reconciliation {result.status.value}"
                    pipeline.set_execution_enabled(False)
                    await self._persist_error(bot_id, message)
                    if not had_existing_pipeline:
                        await pipeline.stop()
                    return False
                pipeline.set_execution_enabled(True)
                self._pipelines[bot_id] = pipeline
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
                if pipeline is not None:
                    pipeline.set_execution_enabled(False)
                raise
            except Exception as exception:
                logger.exception(
                    "bot_pipeline_start_failed",
                    bot_id=bot_id,
                    worker_id=str(self.worker_id),
                    error=str(exception),
                )
                if pipeline is not None and not had_existing_pipeline:
                    pipeline.set_execution_enabled(False)
                    try:
                        await pipeline.stop()
                    except Exception:
                        logger.exception("bot_pipeline_cleanup_failed", bot_id=bot_id)
                await self._persist_error(bot_id, str(exception))
                return False
            finally:
                if bot_id not in self._pipelines:
                    await self.repositories.release(bot_id, str(self.worker_id), self.clock.now())

    async def _heartbeat_bot(self, bot_id: str) -> None:
        async with self._lock_for(bot_id):
            if bot_id not in self._pipelines:
                return
            owned = await self.repositories.renew(bot_id, str(self.worker_id), self.clock.now())
            if owned:
                return
            pipeline = self._pipelines.pop(bot_id, None)
            if pipeline is not None:
                pipeline.set_execution_enabled(False)
            await self._persist_error(bot_id, "bot lease ownership lost")
            logger.error(
                "bot_lease_ownership_lost",
                bot_id=bot_id,
                worker_id=str(self.worker_id),
            )

    async def _heartbeat_loop(self) -> None:
        try:
            while not self._shutting_down:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                await self.heartbeat_once()
        except asyncio.CancelledError:
            raise

    def _ensure_heartbeat_task(self) -> None:
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    def _lock_for(self, bot_id: str) -> asyncio.Lock:
        return self._locks.setdefault(bot_id, asyncio.Lock())

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
