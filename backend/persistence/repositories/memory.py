import asyncio
from datetime import UTC, datetime, timedelta

from backend.persistence.repositories.protocols import (
    BotRecord,
    LeaseRecord,
    LifecycleUpdate,
    ReconciliationRecord,
)

LEASE_TIMEOUT = timedelta(seconds=30)


class InMemorySupervisorRepositories:
    """Deterministic repository implementation for tests and local runtimes."""

    def __init__(
        self,
        bots: list[BotRecord] | None = None,
        reconciliations: list[ReconciliationRecord] | None = None,
    ) -> None:
        self._bots = {bot.id: bot for bot in bots or []}
        self._leases: dict[str, LeaseRecord] = {}
        self._reconciliations = {
            result.id: result for result in reconciliations or []
        }
        self._lease_lock = asyncio.Lock()
        self._bot_lock = asyncio.Lock()

    async def get_restore_candidates(self) -> list[BotRecord]:
        async with self._bot_lock:
            return [bot for bot in self._bots.values() if bot.desired_status != "stopped"]

    async def get(self, bot_id: str) -> BotRecord | None:
        async with self._bot_lock:
            return self._bots.get(bot_id)

    async def persist_lifecycle(self, bot_id: str, state: LifecycleUpdate) -> BotRecord | None:
        async with self._bot_lock:
            bot = self._bots.get(bot_id)
            if bot is None:
                return None
            updated = BotRecord(
                id=bot.id,
                name=bot.name,
                account_id=bot.account_id,
                broker=bot.broker,
                mode=bot.mode,
                instrument=bot.instrument,
                timeframe=bot.timeframe,
                desired_status=state.desired_status,
                status=state.status,
                last_error=state.last_error,
                started_at=state.started_at,
                stopped_at=state.stopped_at,
            )
            self._bots[bot_id] = updated
            return updated

    async def persist_error_if_owned(
        self,
        bot_id: str,
        worker_id: str,
        state: LifecycleUpdate,
        now: datetime | None = None,
    ) -> BotRecord | None:
        current_time = now or datetime.now(UTC)
        async with self._lease_lock:
            lease = self._leases.get(bot_id)
            if (
                lease is None
                or lease.worker_id != worker_id
                or lease.locked_at <= current_time - LEASE_TIMEOUT
            ):
                return None
            async with self._bot_lock:
                bot = self._bots.get(bot_id)
                if bot is None:
                    return None
                updated = BotRecord(
                    id=bot.id,
                    name=bot.name,
                    account_id=bot.account_id,
                    broker=bot.broker,
                    mode=bot.mode,
                    instrument=bot.instrument,
                    timeframe=bot.timeframe,
                    desired_status=state.desired_status,
                    status=state.status,
                    last_error=state.last_error,
                    started_at=state.started_at,
                    stopped_at=state.stopped_at,
                )
                self._bots[bot_id] = updated
                return updated

    async def claim(
        self,
        bot_id: str,
        worker_id: str,
        now: datetime | None = None,
    ) -> LeaseRecord | None:
        claim_time = now or datetime.now(UTC)
        async with self._lease_lock:
            existing = self._leases.get(bot_id)
            if (
                existing is not None
                and existing.worker_id != worker_id
                and existing.locked_at > claim_time - LEASE_TIMEOUT
            ):
                return None
            if existing is None:
                existing = LeaseRecord(
                    id=f"run-{bot_id}",
                    bot_id=bot_id,
                    worker_id=worker_id,
                    locked_at=claim_time,
                    status="starting",
                    started_at=claim_time,
                    last_heartbeat_at=claim_time,
                )
            else:
                existing = LeaseRecord(
                    id=existing.id,
                    bot_id=bot_id,
                    worker_id=worker_id,
                    locked_at=claim_time,
                    status="starting",
                    started_at=existing.started_at,
                    last_heartbeat_at=claim_time,
                )
            self._leases[bot_id] = existing
            return existing

    async def renew(self, bot_id: str, worker_id: str, now: datetime | None = None) -> bool:
        heartbeat = now or datetime.now(UTC)
        async with self._lease_lock:
            lease = self._leases.get(bot_id)
            if lease is None or lease.worker_id != worker_id:
                return False
            self._leases[bot_id] = LeaseRecord(
                id=lease.id,
                bot_id=lease.bot_id,
                worker_id=lease.worker_id,
                locked_at=heartbeat,
                status=lease.status,
                started_at=lease.started_at,
                last_heartbeat_at=heartbeat,
            )
            return True

    async def release(self, bot_id: str, worker_id: str, now: datetime | None = None) -> bool:
        del now
        async with self._lease_lock:
            lease = self._leases.get(bot_id)
            if lease is None or lease.worker_id != worker_id:
                return False
            del self._leases[bot_id]
            return True

    async def record(self, result: ReconciliationRecord) -> ReconciliationRecord:
        async with self._bot_lock:
            self._reconciliations.setdefault(result.id, result)
            return self._reconciliations[result.id]

    async def get_reconciliation(self, reconciliation_id: str) -> ReconciliationRecord | None:
        async with self._bot_lock:
            return self._reconciliations.get(reconciliation_id)
