from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, runtime_checkable
from uuid import UUID


@dataclass(frozen=True, slots=True)
class BotSnapshot:
    """Persistence-neutral bot configuration and lifecycle state for runtime injection."""

    id: UUID
    name: str
    account_id: UUID
    broker: str
    mode: str
    instrument: str
    timeframe: str
    desired_status: str
    status: str
    last_error: str | None = None


class ReconciliationStatus(StrEnum):
    """Outcome of comparing durable Atlas state with the broker state."""

    MATCHED = "matched"
    MISMATCHED = "mismatched"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    """Broker reconciliation output used to gate execution for one bot."""

    status: ReconciliationStatus
    broker_snapshot: Mapping[str, object] = field(default_factory=dict)
    differences: Mapping[str, object] = field(default_factory=dict)
    error: str | None = None

    @property
    def is_safe_to_execute(self) -> bool:
        """Return whether reconciliation permits new execution for the bot."""
        return self.status is ReconciliationStatus.MATCHED


@runtime_checkable
class BotPipeline(Protocol):
    """Isolated runtime pipeline owned by one bot supervisor."""

    async def start(self) -> None:
        """Start feed and strategy processing for the pipeline."""

    async def stop(self) -> None:
        """Stop all pipeline processing and release its runtime resources."""

    def set_execution_enabled(self, enabled: bool) -> None:
        """Enable or disable order execution without stopping the pipeline."""

    @property
    def execution_enabled(self) -> bool:
        """Whether this pipeline may submit new orders."""


@runtime_checkable
class PipelineFactory(Protocol):
    """Injected constructor for one isolated pipeline per owned bot."""

    def create_pipeline(self, bot: BotSnapshot) -> BotPipeline:
        """Create a pipeline for ``bot`` without starting it."""


@runtime_checkable
class Reconciler(Protocol):
    """Injected broker-state reconciliation boundary for the supervisor."""

    async def reconcile(self, bot: BotSnapshot) -> ReconciliationResult:
        """Compare broker state with the state represented by ``bot``."""
