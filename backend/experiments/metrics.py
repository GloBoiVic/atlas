"""Pure, deterministic metrics for completed historical Experiments."""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal

MetricState = Literal["VALUE", "INFINITE", "UNAVAILABLE"]


@dataclass(frozen=True, slots=True)
class MetricValue:
    state: MetricState
    value: Decimal | None
    unit: str
    reason: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "state": self.state,
            "value": None if self.value is None else str(self.value),
            "unit": self.unit,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class ExperimentMetrics:
    net_return: MetricValue
    max_drawdown_amount: MetricValue
    max_drawdown_percent: MetricValue
    sharpe_ratio: MetricValue
    profit_factor: MetricValue
    win_rate: MetricValue
    expectancy_net_pnl: MetricValue
    trade_count: int


def _value(value: Decimal, unit: str) -> MetricValue:
    return MetricValue("VALUE", value, unit)


def _unavailable(unit: str, reason: str) -> MetricValue:
    return MetricValue("UNAVAILABLE", None, unit, reason)


def _decimal(value: object) -> Decimal:
    result = value if isinstance(value, Decimal) else Decimal(str(value))
    if not result.is_finite():
        raise ValueError("metric input must be finite")
    return result


def _utc_date(value: datetime) -> date:
    if value.tzinfo is None:
        return value.date()
    return value.astimezone(UTC).date()


def _daily_returns(
    equity: tuple[object, ...], starting_equity: Decimal
) -> list[Decimal]:
    if starting_equity <= 0:
        return []
    last_by_date: dict[date, tuple[datetime, int, Decimal]] = {}
    for index, point in enumerate(equity):
        observed_at = point.observed_at
        key = _utc_date(observed_at)
        candidate = (observed_at, index, _decimal(point.equity))
        if key not in last_by_date or candidate[:2] > last_by_date[key][:2]:
            last_by_date[key] = candidate
    values = [
        item[2] for item in sorted(last_by_date.values(), key=lambda item: item[:2])
    ]
    returns: list[Decimal] = []
    previous = starting_equity
    for value in values:
        returns.append(value / previous - Decimal("1"))
        previous = value
    return returns


def calculate_metrics(
    trades: tuple[object, ...] | list[object],
    equity_points: tuple[object, ...] | list[object],
    *,
    starting_equity: Decimal,
) -> ExperimentMetrics:
    """Calculate metrics using only immutable Trade and equity facts.

    The input order does not affect results except for equal-timestamp equity
    points, where the supplied sequence order deterministically selects the
    last point.
    """
    starting = _decimal(starting_equity)
    points = tuple(equity_points)
    equities = [_decimal(point.equity) for point in points]
    if equities and starting > 0:
        net_return = _value(equities[-1] / starting - Decimal("1"), "ratio")
    else:
        net_return = _unavailable("ratio", "NO_EQUITY_HISTORY")

    peak = starting
    max_drawdown = Decimal("0")
    max_drawdown_percent = Decimal("0")
    for value in equities:
        peak = max(peak, value)
        if peak > 0:
            drawdown = peak - value
            drawdown_percent = drawdown / peak
            max_drawdown = max(max_drawdown, drawdown)
            max_drawdown_percent = max(max_drawdown_percent, drawdown_percent)

    completed = tuple(trade for trade in trades if trade.status == "COMPLETED")
    trade_count = len(completed)
    net_pnls = [_decimal(trade.net_pnl) for trade in completed]
    profits = sum((value for value in net_pnls if value > 0), Decimal("0"))
    losses = sum((value for value in net_pnls if value < 0), Decimal("0"))
    if not net_pnls:
        profit_factor = _unavailable("ratio", "ZERO_TRADES")
        win_rate = _unavailable("ratio", "ZERO_TRADES")
        expectancy = _unavailable("USD", "ZERO_TRADES")
    else:
        if profits > 0 and losses == 0:
            profit_factor = MetricValue("INFINITE", None, "ratio", "NO_LOSING_TRADES")
        elif profits == 0 and losses == 0:
            profit_factor = _unavailable("ratio", "NO_PROFIT_OR_LOSS")
        else:
            profit_factor = _value(profits / abs(losses), "ratio")
        win_rate = _value(
            Decimal(sum(value > 0 for value in net_pnls)) / trade_count, "ratio"
        )
        expectancy = _value(sum(net_pnls, Decimal("0")) / trade_count, "USD")

    returns = _daily_returns(points, starting)
    if len(returns) < 2:
        sharpe = _unavailable("ratio", "INSUFFICIENT_DAILY_RETURNS")
    else:
        mean = sum(returns, Decimal("0")) / len(returns)
        variance = sum((value - mean) ** 2 for value in returns) / (len(returns) - 1)
        if variance == 0:
            sharpe = _unavailable("ratio", "ZERO_VARIANCE")
        else:
            sharpe = _value(mean / variance.sqrt() * Decimal(252).sqrt(), "ratio")

    return ExperimentMetrics(
        net_return=net_return,
        max_drawdown_amount=_value(max_drawdown, "USD"),
        max_drawdown_percent=_value(max_drawdown_percent, "ratio"),
        sharpe_ratio=sharpe,
        profit_factor=profit_factor,
        win_rate=win_rate,
        expectancy_net_pnl=expectancy,
        trade_count=trade_count,
    )


__all__ = ["ExperimentMetrics", "MetricValue", "calculate_metrics"]
