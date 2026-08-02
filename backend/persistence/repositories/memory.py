import asyncio

from backend.persistence.repositories.protocols import (
    BotRecord,
    LifecycleUpdate,
    ReconciliationRecord,
)


class InMemorySupervisorRepositories:
    """Deterministic repository implementation for tests and local runtimes."""

    def __init__(
        self,
        bots: list[BotRecord] | None = None,
        reconciliations: list[ReconciliationRecord] | None = None,
    ) -> None:
        self._bots = {bot.id: bot for bot in bots or []}
        self._reconciliations = {
            result.id: result for result in reconciliations or []
        }
        self._bot_lock = asyncio.Lock()

    async def get_restore_candidates(self) -> list[BotRecord]:
        async with self._bot_lock:
            return [bot for bot in self._bots.values() if bot.desired_status != "stopped"]

    async def get(self, bot_id: str) -> BotRecord | None:
        async with self._bot_lock:
            return self._bots.get(bot_id)

    async def persist_lifecycle(self, bot_id: str, state: LifecycleUpdate) -> BotRecord | None:
        async with self._bot_lock:
            return self._update_bot(bot_id, state)

    def _update_bot(self, bot_id: str, state: LifecycleUpdate) -> BotRecord | None:
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

    async def record(self, result: ReconciliationRecord) -> ReconciliationRecord:
        async with self._bot_lock:
            self._reconciliations.setdefault(result.id, result)
            return self._reconciliations[result.id]

    async def get_reconciliation(self, reconciliation_id: str) -> ReconciliationRecord | None:
        async with self._bot_lock:
            return self._reconciliations.get(reconciliation_id)
