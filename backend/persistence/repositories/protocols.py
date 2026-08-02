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


class ReconciliationRepository(Protocol):
    async def record(self, result: ReconciliationRecord) -> ReconciliationRecord:
        """Persist a reconciliation result."""

    async def get_reconciliation(self, reconciliation_id: str) -> ReconciliationRecord | None:
        """Return one reconciliation result, if it exists."""


class SupervisorRepositories(BotRepository, ReconciliationRepository, Protocol):
    """Combined dependency contract used by supervisor composition."""
