from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

from backend.experiments.metrics import calculate_metrics


def trade(net_pnl: str, status: str = "COMPLETED") -> SimpleNamespace:
    return SimpleNamespace(status=status, net_pnl=Decimal(net_pnl))


def equity(
    *values: str, start: datetime = datetime(2026, 1, 1, tzinfo=UTC)
) -> tuple[SimpleNamespace, ...]:
    return tuple(
        SimpleNamespace(
            observed_at=start + timedelta(days=index), equity=Decimal(value)
        )
        for index, value in enumerate(values)
    )


def test_net_return_and_max_drawdown_use_full_equity_series() -> None:
    metrics = calculate_metrics(
        [trade("10")],
        equity("100", "120", "90", "110"),
        starting_equity=Decimal("100"),
    )

    assert metrics.net_return.value == Decimal("0.1")
    assert metrics.max_drawdown_amount.value == Decimal("30")
    assert metrics.max_drawdown_percent.value == Decimal("0.25")


def test_max_drawdown_percent_uses_peak_before_the_trough() -> None:
    metrics = calculate_metrics(
        [], equity("100", "110", "90", "120"), starting_equity=Decimal("100")
    )

    assert metrics.max_drawdown_amount.value == Decimal("20")
    assert metrics.max_drawdown_percent.value == Decimal(20) / Decimal(110)


def test_drawdown_amount_and_percent_share_the_maximum_peak_to_trough_event() -> None:
    metrics = calculate_metrics(
        [trade("5"), trade("-3")],
        equity("100", "200", "150", "210", "180"),
        starting_equity=Decimal("100"),
    )

    assert metrics.trade_count == 2
    assert metrics.max_drawdown_amount.value == Decimal("50")
    assert metrics.max_drawdown_percent.value == Decimal("0.25")


def test_sharpe_uses_final_equity_point_per_utc_day() -> None:
    points = (
        SimpleNamespace(
            observed_at=datetime(2026, 1, 1, tzinfo=UTC), equity=Decimal("110")
        ),
        SimpleNamespace(
            observed_at=datetime(2026, 1, 2, 12, tzinfo=UTC), equity=Decimal("120")
        ),
        SimpleNamespace(
            observed_at=datetime(2026, 1, 3, tzinfo=UTC), equity=Decimal("132")
        ),
    )
    metrics = calculate_metrics([], points, starting_equity=Decimal("100"))

    assert metrics.sharpe_ratio.state == "VALUE"
    first_return = Decimal("110") / Decimal("100") - 1
    second_return = Decimal("120") / Decimal("110") - 1
    third_return = Decimal("132") / Decimal("120") - 1
    mean = (first_return + second_return + third_return) / 3
    sample_deviation = (
        (first_return - mean) ** 2
        + (second_return - mean) ** 2
        + (third_return - mean) ** 2
    ).sqrt() / Decimal(2).sqrt()
    expected = mean / sample_deviation * Decimal(252).sqrt()
    assert abs(metrics.sharpe_ratio.value - expected) < Decimal("1e-24")


def test_metrics_replay_is_deterministic_when_equity_rows_arrive_out_of_order() -> None:
    points = equity("100", "110", "90", "120")
    ordered = calculate_metrics([], points, starting_equity=Decimal("100"))
    replayed = calculate_metrics(
        [], tuple(reversed(points)), starting_equity=Decimal("100")
    )

    assert replayed == ordered


def test_sharpe_reports_insufficient_and_zero_variance_states() -> None:
    insufficient = calculate_metrics(
        [], equity("100"), starting_equity=Decimal("100")
    )
    zero_variance = calculate_metrics(
        [], equity("110", "121", "133.1"), starting_equity=Decimal("100")
    )

    assert insufficient.sharpe_ratio.reason == "INSUFFICIENT_DAILY_RETURNS"
    assert zero_variance.sharpe_ratio.reason == "ZERO_VARIANCE"


def test_profit_factor_finite_infinite_and_empty() -> None:
    finite = calculate_metrics(
        [trade("3"), trade("-1")], [], starting_equity=Decimal("100")
    )
    infinite = calculate_metrics(
        [trade("3"), trade("0")], [], starting_equity=Decimal("100")
    )
    empty = calculate_metrics([], [], starting_equity=Decimal("100"))

    assert finite.profit_factor.value == Decimal("3")
    assert infinite.profit_factor.state == "INFINITE"
    assert infinite.profit_factor.value is None
    assert empty.profit_factor.reason == "ZERO_TRADES"


def test_win_rate_keeps_break_even_trades_in_denominator_and_expectancy_is_net(
) -> None:
    metrics = calculate_metrics(
        [trade("2"), trade("0"), trade("-1")],
        [],
        starting_equity=Decimal("100"),
    )

    assert metrics.win_rate.value == Decimal(1) / Decimal(3)
    assert metrics.expectancy_net_pnl.value == Decimal(1) / Decimal(3)
    assert metrics.trade_count == 3


def test_zero_trade_states_are_explicit_and_metric_output_is_deterministic() -> None:
    points = equity("100", "99", "98")
    first = calculate_metrics([], points, starting_equity=Decimal("100"))
    second = calculate_metrics([], points, starting_equity=Decimal("100"))

    assert first == second
    assert first.trade_count == 0
    assert first.win_rate.state == "UNAVAILABLE"
    assert first.expectancy_net_pnl.state == "UNAVAILABLE"
    assert first.profit_factor.state == "UNAVAILABLE"
    assert first.net_return.as_dict() == {
        "state": "VALUE",
        "value": "-0.02",
        "unit": "ratio",
        "reason": None,
    }
