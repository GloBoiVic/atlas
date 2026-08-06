"""Pure canonical metrics for persisted closed execution trades."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from math import sqrt
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID


class _TradeStatus(Protocol):
    value: str


class ClosedTrade(Protocol):
    """Minimum immutable trade facts required by canonical calculations."""

    @property
    def id(self) -> UUID: ...

    @property
    def status(self) -> _TradeStatus: ...

    @property
    def exit_time(self) -> datetime | None: ...

    @property
    def net_pnl(self) -> Decimal | None: ...

ZERO = Decimal("0")
MIN_SHARPE_OBSERVATIONS = 30


@dataclass(frozen=True, slots=True)
class EquityPoint:
    """One point in the closed-trade equity curve, including its initial baseline."""

    timestamp: datetime
    equity: Decimal
    net_pnl: Decimal
    trade_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class PerformanceMetrics:
    """Canonical analytics result before API serialization."""

    total_return: Decimal
    total_pnl: Decimal
    starting_equity: Decimal
    ending_equity: Decimal
    win_rate: float
    closed_trade_daily_sharpe: float | None
    max_drawdown: Decimal
    profit_factor: float | None
    total_trades: int
    winning_trades: int
    losing_trades: int
    equity_curve: tuple[EquityPoint, ...]


def calculate_metrics(
    *,
    starting_equity: Decimal,
    trades: tuple[ClosedTrade, ...],
    period_start: datetime,
    period_end: datetime,
) -> PerformanceMetrics:
    """Calculate canonical metrics deterministically from closed trades.

    Date bounds are inclusive and must be UTC. Sharpe uses population standard deviation
    over every UTC calendar day in the selected period, including days without closes.

    Raises:
        ValueError: If inputs violate the explicit financial or UTC contracts.
    """
    _validate_period(period_start, period_end)
    if not isinstance(starting_equity, Decimal) or not starting_equity.is_finite():
        raise ValueError("starting_equity must be a finite Decimal")
    if starting_equity <= ZERO:
        raise ValueError("starting_equity must be positive")

    ordered = sorted(trades, key=lambda trade: (trade.exit_time or period_end, trade.id))
    _validate_closed_trades(ordered, period_start, period_end)
    pnls = tuple(trade.net_pnl for trade in ordered if trade.net_pnl is not None)
    total_pnl = sum(pnls, ZERO)
    ending_equity = starting_equity + total_pnl
    equity = starting_equity
    peak = starting_equity
    max_drawdown = ZERO
    curve = [EquityPoint(period_start, starting_equity, ZERO)]
    for trade, pnl in zip(ordered, pnls, strict=True):
        equity += pnl
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)
        if trade.exit_time is None:
            raise AssertionError("validated trade is missing exit_time")
        curve.append(EquityPoint(trade.exit_time, equity, pnl, trade.id))

    winners = tuple(pnl for pnl in pnls if pnl > ZERO)
    losers = tuple(pnl for pnl in pnls if pnl < ZERO)
    gross_loss = abs(sum(losers, ZERO))
    profit_factor = float(sum(winners, ZERO) / gross_loss) if gross_loss else None
    return PerformanceMetrics(
        total_return=total_pnl / starting_equity,
        total_pnl=total_pnl,
        starting_equity=starting_equity,
        ending_equity=ending_equity,
        win_rate=len(winners) / len(pnls) if pnls else 0.0,
        closed_trade_daily_sharpe=_daily_sharpe(
            starting_equity, ordered, period_start.date(), period_end.date()
        ),
        max_drawdown=max_drawdown,
        profit_factor=profit_factor,
        total_trades=len(pnls),
        winning_trades=len(winners),
        losing_trades=len(losers),
        equity_curve=tuple(curve),
    )


def _validate_period(period_start: datetime, period_end: datetime) -> None:
    if period_start.tzinfo is None or period_start.utcoffset() != UTC.utcoffset(period_start):
        raise ValueError("period_start must be UTC")
    if period_end.tzinfo is None or period_end.utcoffset() != UTC.utcoffset(period_end):
        raise ValueError("period_end must be UTC")
    if period_start > period_end:
        raise ValueError("period_start must not be after period_end")


def _validate_closed_trades(
    trades: list[ClosedTrade], period_start: datetime, period_end: datetime
) -> None:
    for trade in trades:
        if trade.status.value != "exited" or trade.exit_time is None or trade.net_pnl is None:
            raise ValueError("metrics require completed trades with net_pnl")
        if not period_start <= trade.exit_time <= period_end:
            raise ValueError("trades must be within the selected period")


def _daily_sharpe(
    starting_equity: Decimal,
    trades: list[ClosedTrade],
    first_day: date,
    last_day: date,
) -> float | None:
    observations = (last_day - first_day).days + 1
    if observations < MIN_SHARPE_OBSERVATIONS:
        return None
    pnl_by_day: dict[date, Decimal] = {}
    for trade in trades:
        assert trade.exit_time is not None and trade.net_pnl is not None
        day = trade.exit_time.astimezone(UTC).date()
        pnl_by_day[day] = pnl_by_day.get(day, ZERO) + trade.net_pnl
    equity = starting_equity
    returns: list[Decimal] = []
    current_day = first_day
    while current_day <= last_day:
        day_pnl = pnl_by_day.get(current_day, ZERO)
        if equity == ZERO:
            return None
        next_equity = equity + day_pnl
        returns.append(next_equity / equity - Decimal("1"))
        equity = next_equity
        current_day += timedelta(days=1)
    mean = sum(returns, ZERO) / Decimal(len(returns))
    variance = sum((value - mean) ** 2 for value in returns) / Decimal(len(returns))
    if variance == ZERO:
        return None
    standard_deviation = Decimal(str(sqrt(float(variance))))
    annualization = Decimal(str(sqrt(365)))
    return float(mean / standard_deviation * annualization)
