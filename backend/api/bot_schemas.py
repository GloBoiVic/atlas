"""Typed transport contracts for bot configuration and lifecycle facts."""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.core.account_mode import AccountMode
from backend.persistence.repositories.protocols import BotRecord


class BotLifecycleStatus(StrEnum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    PAUSING = "pausing"
    PAUSED = "paused"
    ERROR = "error"


class BotCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    strategy_version_id: UUID
    account_id: UUID
    broker: str = Field(min_length=1, max_length=50)
    mode: AccountMode
    instrument: str = Field(min_length=1, max_length=50)
    timeframe: str = Field(min_length=1, max_length=10)
    config: dict[str, Any] = Field(default_factory=dict)


class BotUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    strategy_version_id: UUID | None = None
    broker: str | None = Field(default=None, min_length=1, max_length=50)
    mode: AccountMode | None = None
    instrument: str | None = Field(default=None, min_length=1, max_length=50)
    timeframe: str | None = Field(default=None, min_length=1, max_length=10)
    config: dict[str, Any] | None = None


class BotCommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: UUID | None = None
    mode: AccountMode | None = None


class BotReadResponse(BaseModel):
    id: UUID
    name: str
    strategy_version_id: UUID | None
    account_id: UUID
    broker: str
    mode: AccountMode
    instrument: str
    timeframe: str
    config: dict[str, object]
    desired_status: BotLifecycleStatus
    status: BotLifecycleStatus
    pnl: str
    started_at: datetime | None
    stopped_at: datetime | None
    last_error: str | None
    created_at: datetime | None
    updated_at: datetime | None


def bot_response(bot: BotRecord) -> BotReadResponse:
    return BotReadResponse(
        id=bot.id,
        name=bot.name,
        strategy_version_id=bot.strategy_version_id,
        account_id=bot.account_id,
        broker=bot.broker,
        mode=AccountMode(bot.mode),
        instrument=bot.instrument,
        timeframe=bot.timeframe,
        config=dict(bot.config),
        desired_status=bot.desired_status,
        status=bot.status,
        pnl=str(bot.pnl),
        started_at=bot.started_at,
        stopped_at=bot.stopped_at,
        last_error=bot.last_error,
        created_at=bot.created_at,
        updated_at=bot.updated_at,
    )
