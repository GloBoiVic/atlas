"""Persistence and event helpers for supervisor-owned lifecycle transitions."""

from uuid import UUID

import structlog

from backend.core.account_mode import AccountMode
from backend.core.clock import Clock
from backend.core.events import BotStatusChanged, EventBus
from backend.persistence.repositories.protocols import (
    BotRecord,
    LifecycleUpdate,
    ReconciliationRecord,
    SupervisorRepositories,
)
from backend.worker.protocols import BotSnapshot, ReconciliationResult

logger = structlog.get_logger(__name__)


async def publish_persisted_transition(
    event_bus: EventBus,
    record: BotRecord,
) -> None:
    logger.info(
        "bot_status_changed",
        bot_id=str(record.id),
        status=record.status,
        desired_status=record.desired_status,
    )
    await event_bus.publish(
        BotStatusChanged(
            account_id=record.account_id,
            bot_id=record.id,
            mode=AccountMode(record.mode),
        ),
    )


async def persist_error(
    repositories: SupervisorRepositories,
    event_bus: EventBus,
    bot_id: UUID,
    error: str,
    clock: Clock,
) -> bool:
    bot = await repositories.get(bot_id)
    if bot is None:
        return False
    record = await repositories.persist_lifecycle(
        bot_id,
        LifecycleUpdate(
            desired_status=bot.desired_status,
            status="error",
            last_error=error,
            started_at=bot.started_at,
            stopped_at=bot.stopped_at,
        ),
    )
    if record is None:
        return False
    await publish_persisted_transition(event_bus, record)
    return True


async def record_reconciliation(
    repositories: SupervisorRepositories,
    bot: BotSnapshot,
    result: ReconciliationResult,
    clock: Clock,
) -> None:
    started_at = clock.now()
    await repositories.record(
        ReconciliationRecord(
            account_id=bot.account_id,
            bot_id=bot.id,
            status=result.status.value,
            broker_snapshot=result.broker_snapshot,
            differences=result.differences,
            started_at=started_at,
            completed_at=clock.now(),
            error_message=result.error,
        ),
    )
