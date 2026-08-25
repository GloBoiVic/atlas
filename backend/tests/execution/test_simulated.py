from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest

from backend.execution.contract import (
    ExecutionObservation,
    Order,
)
from backend.execution.simulated import SimulatedExecutionAdapter

NOW = datetime(2026, 1, 1, tzinfo=UTC)
Q = Decimal("1000")


def obs(bid: str, ask: str, **kwargs: Any) -> ExecutionObservation:
    return ExecutionObservation(NOW, Decimal(bid), Decimal(ask), **kwargs)


def order(
    order_type: str, purpose: str, direction: str, price: str | None = None
) -> Order:
    return Order(
        uuid4(), order_type, purpose, direction, Q,
        Decimal(price) if price else None,
    )


def test_market_entries_use_long_ask_and_short_bid() -> None:
    adapter = SimulatedExecutionAdapter()
    assert adapter.execute(
        order("MARKET", "ENTRY", "LONG"), obs("1.1000", "1.1002")
    ).execution_price == Decimal("1.1002")
    assert adapter.execute(
        order("MARKET", "ENTRY", "SHORT"), obs("1.1000", "1.1002")
    ).execution_price == Decimal("1.1000")


@pytest.mark.parametrize(
    ("direction", "bid", "ask", "purpose", "expected"),
    [("LONG", "1.1050", "1.1052", "TAKE_PROFIT", "1.1050"),
     ("SHORT", "1.0950", "1.0952", "TAKE_PROFIT", "1.0952"),
     ("LONG", "1.1000", "1.1002", "STOP_LOSS", "1.1000"),
     ("SHORT", "1.1000", "1.1002", "STOP_LOSS", "1.1002")],
)
def test_exits_fill_at_requested_price_on_open(
    direction: str, bid: str, ask: str, purpose: str, expected: str
) -> None:
    if purpose == "TAKE_PROFIT":
        price = "1.1050" if direction == "LONG" else "1.0952"
        order_type = "LIMIT"
    else:
        price = "1.1000" if direction == "LONG" else "1.1002"
        order_type = "STOP"
    fill = SimulatedExecutionAdapter().execute(
        order(order_type, purpose, direction, price), obs(bid, ask)
    )
    assert fill.execution_price == Decimal(expected)


def test_stop_gap_and_intrabar_touch_are_simulated() -> None:
    adapter = SimulatedExecutionAdapter(slippage_ticks=2)
    gap = adapter.execute(
        order("STOP", "STOP_LOSS", "LONG", "1.1000"),
        obs("1.0990", "1.0992"),
    )
    assert gap.execution_price == Decimal("1.09898")
    target = adapter.execute(
        order("LIMIT", "TAKE_PROFIT", "LONG", "1.1050"),
        obs("1.1000", "1.1002", bid_high=Decimal("1.1051"), bid_low=Decimal("1.0999")),
    )
    assert target.execution_price == Decimal("1.1050")
    assert target.price_basis == "INTRABAR_TARGET"


def test_dual_touch_is_adverse_first_and_preserves_source_provenance() -> None:
    from uuid import uuid4

    stop = order("STOP", "STOP_LOSS", "LONG", "1.1000")
    target = order("LIMIT", "TAKE_PROFIT", "LONG", "1.1050")
    bid_id, ask_id = uuid4(), uuid4()
    decision = SimulatedExecutionAdapter().execute_protection(
        stop,
        target,
        obs("1.1002", "1.1004", bid_high=Decimal("1.1051"), bid_low=Decimal("1.0998"),
            bid_source_market_bar_id=bid_id, ask_source_market_bar_id=ask_id),
    )
    assert decision.ambiguous is True
    assert decision.ambiguity_policy == "STOP_LOSS_ADVERSE_FIRST_V1"
    assert decision.fill is not None
    assert decision.fill.source_market_bar_id == bid_id
    assert decision.fill.price_basis == "INTRABAR_STOP"


@pytest.mark.parametrize(
    ("direction", "purpose", "price", "kwargs"),
    [
        ("LONG", "STOP_LOSS", "1.1000", {
            "bid_low": Decimal("1.0999"), "bid_high": Decimal("1.1040"),
            "ask_low": Decimal("1.1050"), "ask_high": Decimal("1.1100"),
        }),
        ("LONG", "TAKE_PROFIT", "1.1050", {
            "bid_low": Decimal("1.1010"), "bid_high": Decimal("1.1051"),
            "ask_low": Decimal("1.0990"), "ask_high": Decimal("1.1000"),
        }),
        ("SHORT", "STOP_LOSS", "1.1050", {
            "ask_low": Decimal("1.1010"), "ask_high": Decimal("1.1051"),
            "bid_low": Decimal("1.0990"), "bid_high": Decimal("1.1000"),
        }),
        ("SHORT", "TAKE_PROFIT", "1.1000", {
            "ask_low": Decimal("1.0999"), "ask_high": Decimal("1.1040"),
            "bid_low": Decimal("1.1050"), "bid_high": Decimal("1.1100"),
        }),
    ],
)
def test_protection_uses_directional_executable_side(
    direction: str, purpose: str, price: str, kwargs: dict[str, Decimal]
) -> None:
    stop = order(
        "STOP", "STOP_LOSS", direction,
        "1.1000" if direction == "LONG" else "1.1050",
    )
    target = order(
        "LIMIT", "TAKE_PROFIT", direction,
        "1.1050" if direction == "LONG" else "1.1000",
    )
    decision = SimulatedExecutionAdapter().execute_protection(
        stop, target, obs("1.1002", "1.1004", **kwargs)
    )
    assert decision.fill is not None
    assert decision.fill.order_id == (stop.id if purpose == "STOP_LOSS" else target.id)
    assert decision.ambiguous is False


def test_protection_marks_only_genuine_directional_dual_touch_ambiguous() -> None:
    stop = order("STOP", "STOP_LOSS", "SHORT", "1.1050")
    target = order("LIMIT", "TAKE_PROFIT", "SHORT", "1.1000")
    decision = SimulatedExecutionAdapter().execute_protection(
        stop,
        target,
        obs("1.1000", "1.1002", ask_high=Decimal("1.1051"), ask_low=Decimal("1.0999")),
    )
    assert decision.fill is not None and decision.fill.order_id == stop.id
    assert decision.ambiguous is True
    assert decision.ambiguity_policy == "STOP_LOSS_ADVERSE_FIRST_V1"


def test_opposite_side_extremes_do_not_create_false_ambiguity() -> None:
    stop = order("STOP", "STOP_LOSS", "LONG", "1.1000")
    target = order("LIMIT", "TAKE_PROFIT", "LONG", "1.1050")
    decision = SimulatedExecutionAdapter().execute_protection(
        stop,
        target,
        obs("1.1002", "1.1004", bid_high=Decimal("1.1051"), ask_low=Decimal("1.0998")),
    )
    assert decision.fill is not None and decision.fill.order_id == target.id
    assert decision.ambiguous is False


def test_end_close_is_executable_side_with_adverse_slippage() -> None:
    adapter = SimulatedExecutionAdapter(slippage_ticks=1)
    fill = adapter.execute(
        order("MARKET", "EXIT", "LONG"),
        obs(
            "1.1000",
            "1.1002",
            bid_close=Decimal("1.1010"),
            ask_close=Decimal("1.1012"),
        ),
    )
    assert fill.execution_price == Decimal("1.10099")
    assert fill.price_basis == "END_CLOSE"


def test_order_creation_and_execution_do_not_mutate_exposure_or_inputs() -> None:
    entry = order("MARKET", "ENTRY", "LONG")
    observation = obs("1.1000", "1.1002")
    before = (entry, observation)
    fill = SimulatedExecutionAdapter().execute(entry, observation)
    assert (entry, observation) == before
    assert fill.quantity == Q
