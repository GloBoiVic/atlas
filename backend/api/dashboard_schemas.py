"""Pydantic v2 transport contracts for dashboard read models."""

from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

from backend.dashboard.models import (
    AccountSummaryRead,
    BotRead,
    DashboardSummaryRead,
    PositionRead,
    StrategyRead,
    StrategyVersionRead,
    TradeRead,
)


class _ReadModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_wire_values(self) -> Self:
        for name, value in self.__dict__.items():
            if isinstance(value, datetime) and (
                value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value)
            ):
                raise ValueError(f"{name} must be UTC")
            if name in _DECIMAL_FIELDS and (not isinstance(value, str) or not _is_decimal(value)):
                raise ValueError(f"{name} must be a finite Decimal string")
        return self


_DECIMAL_FIELDS = {
    "starting_equity",
    "realized_pnl",
    "unrealized_pnl",
    "equity",
    "quantity",
    "entry_price",
    "current_price",
    "gross_pnl",
    "net_pnl",
    "total_fees",
    "pnl",
    "exit_price",
}


def _is_decimal(value: str) -> bool:
    try:
        return Decimal(value).is_finite()
    except (InvalidOperation, ValueError):
        return False


class AccountResponse(_ReadModel):
    id: UUID
    name: str
    broker: str
    mode: str
    updated_at: datetime


class AccountSummaryResponse(_ReadModel):
    account: AccountResponse
    starting_equity: str
    realized_pnl: str
    unrealized_pnl: str
    equity: str
    as_of: datetime


class PositionResponse(_ReadModel):
    id: UUID
    account_id: UUID
    bot_id: UUID | None
    strategy_version_id: UUID | None
    instrument_id: UUID
    symbol: str
    mode: str
    side: str
    quantity: str
    entry_price: str
    current_price: str | None
    unrealized_pnl: str
    realized_pnl: str
    opened_at: datetime


class BotResponse(_ReadModel):
    id: UUID
    account_id: UUID
    strategy_id: UUID | None
    strategy_version_id: UUID | None
    name: str
    broker: str
    mode: str
    instrument: str
    timeframe: str
    desired_status: str
    status: str
    pnl: str | None
    last_error: str | None
    started_at: datetime | None
    stopped_at: datetime | None
    updated_at: datetime


class TradeResponse(_ReadModel):
    id: UUID
    account_id: UUID
    bot_id: UUID | None
    strategy_version_id: UUID | None
    instrument_id: UUID
    symbol: str
    mode: str
    direction: str
    entry_price: str
    exit_price: str | None
    quantity: str
    gross_pnl: str | None
    net_pnl: str | None
    total_fees: str
    status: str
    entry_time: datetime
    exit_time: datetime | None


class StrategyVersionResponse(_ReadModel):
    id: UUID
    strategy_id: UUID
    repository: str
    commit_sha: str
    parameters: dict[str, object]
    deployed_at: datetime


class StrategyResponse(_ReadModel):
    id: UUID
    name: str
    version: str
    commit_sha: str
    parameters: dict[str, object]
    description: str | None
    created_at: datetime
    versions: list[StrategyVersionResponse]


class DashboardSummaryResponse(_ReadModel):
    account: AccountSummaryResponse
    positions: list[PositionResponse]
    bots: list[BotResponse]
    recent_trades: list[TradeResponse]


def account_summary_response(value: AccountSummaryRead) -> AccountSummaryResponse:
    return AccountSummaryResponse(
        account=AccountResponse.model_validate(value.account, from_attributes=True),
        starting_equity=str(value.starting_equity),
        realized_pnl=str(value.realized_pnl),
        unrealized_pnl=str(value.unrealized_pnl),
        equity=str(value.equity),
        as_of=value.as_of,
    )


def position_response(value: PositionRead) -> PositionResponse:
    return PositionResponse(
        **{
            **asdict(value),
            "mode": value.mode.value,
            "quantity": str(value.quantity),
            "entry_price": str(value.entry_price),
            "current_price": _decimal(value.current_price),
            "unrealized_pnl": str(value.unrealized_pnl),
            "realized_pnl": str(value.realized_pnl),
        }
    )


def bot_response(value: BotRead) -> BotResponse:
    data = {**asdict(value), "mode": value.mode.value, "pnl": _decimal(value.pnl)}
    return BotResponse(**data)


def trade_response(value: TradeRead) -> TradeResponse:
    data = {
        **asdict(value),
        "mode": value.mode.value,
        "entry_price": str(value.entry_price),
        "exit_price": _decimal(value.exit_price),
        "quantity": str(value.quantity),
        "gross_pnl": _decimal(value.gross_pnl),
        "net_pnl": _decimal(value.net_pnl),
        "total_fees": str(value.total_fees),
    }
    return TradeResponse(**data)


def strategy_response(value: StrategyRead) -> StrategyResponse:
    return StrategyResponse(
        id=value.id,
        name=value.name,
        version=value.version,
        commit_sha=value.commit_sha,
        parameters=value.parameters,
        description=value.description,
        created_at=value.created_at,
        versions=[strategy_version_response(item) for item in value.versions],
    )


def strategy_version_response(value: StrategyVersionRead) -> StrategyVersionResponse:
    return StrategyVersionResponse.model_validate(value, from_attributes=True)


def dashboard_response(value: DashboardSummaryRead) -> DashboardSummaryResponse:
    return DashboardSummaryResponse(
        account=account_summary_response(value.account),
        positions=[position_response(item) for item in value.positions],
        bots=[bot_response(item) for item in value.bots],
        recent_trades=[trade_response(item) for item in value.recent_trades],
    )


def _decimal(value: Decimal | None) -> str | None:
    return None if value is None else str(value)
