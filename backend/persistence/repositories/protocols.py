from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class BotRecord:
    """Persistence-neutral bot data needed by the supervisor."""

    id: str
    name: str
    account_id: str
    broker: str
    mode: str
    instrument: str
    timeframe: str
    desired_status: str
    status: str
    last_error: str | None
    started_at: datetime | None
    stopped_at: datetime | None


@dataclass(frozen=True, slots=True)
class LifecycleUpdate:
    """The complete supervisor-owned lifecycle state of a bot."""

    desired_status: str
    status: str
    last_error: str | None = None
    started_at: datetime | None = None
    stopped_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class LeaseRecord:
    """A bot run lease and its current owner."""

    id: str
    bot_id: str
    worker_id: str
    locked_at: datetime
    status: str
    started_at: datetime
    last_heartbeat_at: datetime | None


@dataclass(frozen=True, slots=True)
class ReconciliationRecord:
    """A broker reconciliation result, represented without ORM objects."""

    account_id: str
    bot_id: str | None
    status: str
    broker_snapshot: Mapping[str, object] = field(default_factory=dict)
    differences: Mapping[str, object] = field(default_factory=dict)
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    error_message: str | None = None
    id: str = field(default_factory=lambda: str(uuid4()))


class BotRepository(Protocol):
    async def get_restore_candidates(self) -> list[BotRecord]:
        """Return bots whose desired state is not stopped."""

    async def get(self, bot_id: str) -> BotRecord | None:
        """Return one bot, if it exists."""

    async def persist_lifecycle(self, bot_id: str, state: LifecycleUpdate) -> BotRecord | None:
        """Persist lifecycle state and return the resulting bot."""

    async def persist_error_if_owned(
        self,
        bot_id: str,
        worker_id: str,
        state: LifecycleUpdate,
        now: datetime | None = None,
    ) -> BotRecord | None:
        """Persist an error only while this worker owns a current lease."""


class LeaseRepository(Protocol):
    async def claim(
        self,
        bot_id: str,
        worker_id: str,
        now: datetime | None = None,
    ) -> LeaseRecord | None:
        """Atomically claim an unowned or expired bot run."""

    async def renew(self, bot_id: str, worker_id: str, now: datetime | None = None) -> bool:
        """Renew a lease only when it is owned by ``worker_id``."""

    async def release(self, bot_id: str, worker_id: str, now: datetime | None = None) -> bool:
        """Release a lease only when it is owned by ``worker_id``."""


class ReconciliationRepository(Protocol):
    async def record(self, result: ReconciliationRecord) -> ReconciliationRecord:
        """Persist a reconciliation result."""

    async def get_reconciliation(self, reconciliation_id: str) -> ReconciliationRecord | None:
        """Return one reconciliation result, if it exists."""


class SupervisorRepositories(BotRepository, LeaseRepository, ReconciliationRepository, Protocol):
    """Combined dependency contract used by supervisor composition."""
