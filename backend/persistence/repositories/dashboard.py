"""SQLAlchemy read repository for operational dashboard projections."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.core.account_mode import AccountMode
from backend.dashboard.models import (
    AccountRead,
    BotRead,
    PositionRead,
    StrategyRead,
    StrategyVersionRead,
    TradeRead,
)
from backend.persistence.models import (
    Account,
    Bot,
    ExecutionPosition,
    ExecutionTrade,
    Instrument,
    Strategy,
    StrategyVersion,
)


class SqlAlchemyDashboardReadRepository:
    """Read-only repository with explicit account and mode predicates."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_account(self, account_id: UUID) -> AccountRead | None:
        async with self._session_factory() as session:
            row = await session.get(Account, account_id)
            if row is None:
                return None
            return AccountRead(
                row.id, row.name, row.broker, AccountMode(row.mode), _utc(row.updated_at)
            )

    async def list_positions(self, *, account_id: UUID, mode: AccountMode) -> list[PositionRead]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(ExecutionPosition, Instrument.symbol)
                .join(Instrument, Instrument.id == ExecutionPosition.instrument_id)
                .where(
                    ExecutionPosition.account_id == account_id,
                    ExecutionPosition.mode == mode.value,
                    ExecutionPosition.status.in_(("open", "reducing")),
                )
                .order_by(ExecutionPosition.opened_at, ExecutionPosition.id)
            )
            return [_position(row, symbol) for row, symbol in result.all()]

    async def list_bots(self, *, account_id: UUID, mode: AccountMode) -> list[BotRead]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(Bot)
                .where(
                    Bot.account_id == account_id,
                    Bot.mode == mode.value,
                    or_(Bot.desired_status != "stopped", Bot.status != "stopped"),
                )
                .order_by(Bot.updated_at.desc(), Bot.id)
            )
            return [_bot(row) for row in result.scalars().all()]

    async def list_trades(
        self, *, account_id: UUID, mode: AccountMode, limit: int | None
    ) -> list[TradeRead]:
        async with self._session_factory() as session:
            account = await session.get(Account, account_id)
            if account is None or AccountMode(account.mode) != mode:
                return []
            statement = (
                select(ExecutionTrade, Instrument.symbol)
                .join(Instrument, Instrument.id == ExecutionTrade.instrument_id)
                .where(ExecutionTrade.account_id == account_id)
                .order_by(ExecutionTrade.entry_time.desc(), ExecutionTrade.id)
            )
            if limit is not None:
                statement = statement.limit(limit)
            result = await session.execute(statement)
            return [_trade(row, symbol, mode) for row, symbol in result.all()]

    async def list_strategies(self) -> list[StrategyRead]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(Strategy).where(Strategy.is_active.is_(True)).order_by(Strategy.name)
            )
            strategies = list(result.scalars().all())
            versions_result = await session.execute(
                select(StrategyVersion)
                .where(
                    StrategyVersion.strategy_id.in_([row.id for row in strategies])
                    if strategies
                    else StrategyVersion.id.is_(None)
                )
                .order_by(StrategyVersion.deployed_at.desc(), StrategyVersion.id)
            )
            versions: dict[UUID, list[StrategyVersionRead]] = {}
            for row in versions_result.scalars().all():
                versions.setdefault(row.strategy_id, []).append(_strategy_version(row))
            return [
                StrategyRead(
                    row.id,
                    row.name,
                    row.version,
                    row.commit_sha,
                    dict(row.parameters),
                    row.description,
                    _required_utc(row.created_at),
                    tuple(versions.get(row.id, [])),
                )
                for row in strategies
            ]

    async def list_strategy_versions(self, strategy_id: UUID) -> list[StrategyVersionRead]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(StrategyVersion)
                .where(StrategyVersion.strategy_id == strategy_id)
                .order_by(StrategyVersion.deployed_at.desc(), StrategyVersion.id)
            )
            return [_strategy_version(row) for row in result.scalars().all()]


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _required_utc(value: datetime | None) -> datetime:
    if value is None:
        raise LookupError("strategy created_at is missing")
    return _utc(value)


def _position(row: ExecutionPosition, symbol: str) -> PositionRead:
    return PositionRead(
        row.id,
        row.account_id,
        row.bot_id,
        row.strategy_version_id,
        row.instrument_id,
        symbol,
        AccountMode(row.mode),
        row.side,
        row.quantity,
        row.entry_price,
        row.current_price,
        row.unrealized_pnl,
        row.realized_pnl,
        _utc(row.opened_at),
    )


def _bot(row: Bot) -> BotRead:
    return BotRead(
        row.id,
        row.account_id,
        row.strategy_id,
        row.strategy_version_id,
        row.name,
        row.broker,
        AccountMode(row.mode),
        row.instrument,
        row.timeframe,
        row.desired_status,
        row.status,
        row.pnl,
        row.last_error,
        _optional_utc(row.started_at),
        _optional_utc(row.stopped_at),
        _utc(row.updated_at),
    )


def _trade(row: ExecutionTrade, symbol: str, mode: AccountMode) -> TradeRead:
    return TradeRead(
        row.id,
        row.account_id,
        row.bot_id,
        row.strategy_version_id,
        row.instrument_id,
        symbol,
        mode,
        row.direction,
        row.entry_price,
        row.exit_price,
        row.quantity,
        row.gross_pnl,
        row.net_pnl,
        row.total_fees,
        row.status,
        _utc(row.entry_time),
        _optional_utc(row.exit_time),
    )


def _strategy_version(row: StrategyVersion) -> StrategyVersionRead:
    return StrategyVersionRead(
        row.id,
        row.strategy_id,
        row.repository,
        row.commit_sha,
        dict(row.parameters),
        _utc(row.deployed_at),
    )


def _optional_utc(value: datetime | None) -> datetime | None:
    return None if value is None else _utc(value)
