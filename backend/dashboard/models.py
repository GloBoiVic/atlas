"""Persistence-neutral contracts for the operational dashboard."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from backend.core.account_mode import AccountMode


@dataclass(frozen=True, slots=True)
class AccountRead:
    id: UUID
    name: str
    broker: str
    mode: AccountMode
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class PositionRead:
    id: UUID
    account_id: UUID
    bot_id: UUID | None
    strategy_version_id: UUID | None
    instrument_id: UUID
    symbol: str
    mode: AccountMode
    side: str
    quantity: Decimal
    entry_price: Decimal
    current_price: Decimal | None
    unrealized_pnl: Decimal
    realized_pnl: Decimal
    opened_at: datetime


@dataclass(frozen=True, slots=True)
class BotRead:
    id: UUID
    account_id: UUID
    strategy_id: UUID | None
    strategy_version_id: UUID | None
    name: str
    broker: str
    mode: AccountMode
    instrument: str
    timeframe: str
    desired_status: str
    status: str
    pnl: Decimal | None
    last_error: str | None
    started_at: datetime | None
    stopped_at: datetime | None
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class TradeRead:
    id: UUID
    account_id: UUID
    bot_id: UUID | None
    strategy_version_id: UUID | None
    instrument_id: UUID
    symbol: str
    mode: AccountMode
    direction: str
    entry_price: Decimal
    exit_price: Decimal | None
    quantity: Decimal
    gross_pnl: Decimal | None
    net_pnl: Decimal | None
    total_fees: Decimal
    status: str
    entry_time: datetime
    exit_time: datetime | None


@dataclass(frozen=True, slots=True)
class StrategyVersionRead:
    id: UUID
    strategy_id: UUID
    repository: str
    commit_sha: str
    parameters: dict[str, object]
    deployed_at: datetime


@dataclass(frozen=True, slots=True)
class StrategyRead:
    id: UUID
    name: str
    version: str
    commit_sha: str
    parameters: dict[str, object]
    description: str | None
    created_at: datetime
    versions: tuple[StrategyVersionRead, ...]


@dataclass(frozen=True, slots=True)
class AccountSummaryRead:
    account: AccountRead
    starting_equity: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    equity: Decimal
    as_of: datetime


@dataclass(frozen=True, slots=True)
class DashboardSummaryRead:
    account: AccountSummaryRead
    positions: tuple[PositionRead, ...]
    bots: tuple[BotRead, ...]
    recent_trades: tuple[TradeRead, ...]
