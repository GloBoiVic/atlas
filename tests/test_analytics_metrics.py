from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

import pytest

from backend.analytics.metrics import calculate_metrics
from backend.analytics.service import AnalyticsService

if TYPE_CHECKING:
    from backend.persistence.repositories.protocols import ExecutionRepository


class ClosedStatus:
    value = "exited"


class OpenStatus:
    value = "entered"


class FakeTrade:
    def __init__(self, pnl: Decimal | None, days: int, closed: bool) -> None:
        self.id: UUID = uuid4()
        self.status: ClosedStatus | OpenStatus = ClosedStatus() if closed else OpenStatus()
        self.exit_time: datetime | None = (
            START + timedelta(days=days, hours=1) if closed else None
        )
        self.net_pnl: Decimal | None = pnl if closed else None


START = datetime(2026, 1, 1, tzinfo=UTC)
ACCOUNT_ID = uuid4()


def make_trade(pnl: str, days: int = 0, *, closed: bool = True) -> FakeTrade:
    return FakeTrade(Decimal(pnl), days, closed)


def test_no_trades_has_zero_metrics_and_baseline_curve() -> None:
    result = calculate_metrics(
        starting_equity=Decimal("1000"),
        trades=(),
        period_start=START,
        period_end=START + timedelta(days=29),
    )

    assert result.total_pnl == Decimal("0")
    assert result.total_return == Decimal("0")
    assert result.ending_equity == Decimal("1000")
    assert result.win_rate == 0.0
    assert result.profit_factor is None
    assert result.closed_trade_daily_sharpe is None
    assert result.equity_curve[0].equity == Decimal("1000")


def test_all_wins_have_no_loss_profit_factor() -> None:
    result = calculate_metrics(
        starting_equity=Decimal("1000"),
        trades=(make_trade("10"), make_trade("20", 1)),
        period_start=START,
        period_end=START + timedelta(days=1, hours=2),
    )

    assert result.total_pnl == Decimal("30")
    assert result.total_return == Decimal("0.03")
    assert result.win_rate == 1.0
    assert result.profit_factor is None
    assert result.losing_trades == 0


def test_all_losses_have_zero_win_rate_and_profit_factor_one() -> None:
    result = calculate_metrics(
        starting_equity=Decimal("1000"),
        trades=(make_trade("-10"), make_trade("-20", 1)),
        period_start=START,
        period_end=START + timedelta(days=1, hours=2),
    )

    assert result.total_pnl == Decimal("-30")
    assert result.win_rate == 0.0
    assert result.profit_factor == 0.0
    assert result.ending_equity == Decimal("970")


def test_mixed_trades_and_equity_curve_are_exact() -> None:
    trades = (make_trade("50"), make_trade("-20", 1), make_trade("10", 2))
    result = calculate_metrics(
        starting_equity=Decimal("1000"),
        trades=trades,
        period_start=START,
        period_end=START + timedelta(days=2, hours=2),
    )

    assert result.total_pnl == Decimal("40")
    assert result.total_return == Decimal("0.04")
    assert result.win_rate == pytest.approx(2 / 3)
    assert result.profit_factor == pytest.approx(3.0)
    assert [point.equity for point in result.equity_curve] == [
        Decimal("1000"),
        Decimal("1050"),
        Decimal("1030"),
        Decimal("1040"),
    ]


def test_max_drawdown_is_peak_to_trough() -> None:
    result = calculate_metrics(
        starting_equity=Decimal("1000"),
        trades=(make_trade("100"), make_trade("-250", 1), make_trade("10", 2)),
        period_start=START,
        period_end=START + timedelta(days=2, hours=2),
    )

    assert result.max_drawdown == Decimal("250")


@pytest.mark.asyncio
async def test_service_filters_closed_trades_by_inclusive_utc_exit_date() -> None:
    class Repository:
        def __init__(self, trades: list[FakeTrade]) -> None:
            self.trades = trades

        async def get_closed_trades(
            self, *, account_id: object, start: datetime, end: datetime
        ) -> list[FakeTrade]:
            return [
                trade
                for trade in self.trades
                if trade.status.value == "exited"
                and trade.exit_time is not None
                and start <= trade.exit_time <= end
            ]

    included = make_trade("10", 1)
    excluded_open = make_trade("20", 1, closed=False)
    excluded_date = make_trade("100", 3)

    result = await AnalyticsService(
        cast("ExecutionRepository", Repository([included, excluded_open, excluded_date]))
    ).get_metrics(
        account_id=ACCOUNT_ID,
        starting_equity=Decimal("1000"),
        period_start=START,
        period_end=START + timedelta(days=1, hours=2),
    )

    assert result.total_trades == 1
    assert result.total_pnl == Decimal("10")


def test_sharpe_includes_zero_return_calendar_gap_days() -> None:
    result = calculate_metrics(
        starting_equity=Decimal("1000"),
        trades=(make_trade("100", 0), make_trade("-100", 29)),
        period_start=START,
        period_end=START + timedelta(days=29, hours=2),
    )

    assert result.closed_trade_daily_sharpe == pytest.approx(0.23465100721669863)


def test_sharpe_is_undefined_for_insufficient_observations_and_zero_variance() -> None:
    short = calculate_metrics(
        starting_equity=Decimal("1000"),
        trades=(make_trade("10"),),
        period_start=START,
        period_end=START + timedelta(days=28),
    )
    flat = calculate_metrics(
        starting_equity=Decimal("1000"),
        trades=(),
        period_start=START,
        period_end=START + timedelta(days=29),
    )

    assert short.closed_trade_daily_sharpe is None
    assert flat.closed_trade_daily_sharpe is None


def test_starting_equity_must_be_positive() -> None:
    with pytest.raises(ValueError, match="starting_equity must be positive"):
        calculate_metrics(
            starting_equity=Decimal("0"),
            trades=(),
            period_start=START,
            period_end=START,
        )
