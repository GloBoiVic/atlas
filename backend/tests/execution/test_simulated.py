from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest

from backend.execution.contract import (
    ExecutionObservation,
    ExecutionRejected,
    ExecutionRejection,
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


def test_stop_gap_and_intrabar_touch_fail_closed() -> None:
    adapter = SimulatedExecutionAdapter()
    with pytest.raises(ExecutionRejected) as gap:
        adapter.execute(
            order("STOP", "STOP_LOSS", "LONG", "1.1000"),
            obs("1.0990", "1.0992"),
        )
    assert gap.value.code is ExecutionRejection.UNSUPPORTED_PHASE3_STOP_GAP
    with pytest.raises(ExecutionRejected) as touch:
        adapter.execute(
            order("LIMIT", "TAKE_PROFIT", "LONG", "1.1050"),
            obs("1.1000", "1.1002", intrabar_trigger=True),
        )
    assert touch.value.code is ExecutionRejection.UNSUPPORTED_PHASE3_INTRABAR_TRIGGER


def test_order_creation_and_execution_do_not_mutate_exposure_or_inputs() -> None:
    entry = order("MARKET", "ENTRY", "LONG")
    observation = obs("1.1000", "1.1002")
    before = (entry, observation)
    fill = SimulatedExecutionAdapter().execute(entry, observation)
    assert (entry, observation) == before
    assert fill.quantity == Q
