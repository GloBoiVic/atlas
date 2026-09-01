from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.domain.market_data import (
    Bar,
    Instrument,
    PriceComponent,
    Timeframe,
)
from backend.domain.strategy import (
    Direction,
    EntryPolicy,
    MarketSpecification,
    PendingEntryHandoff,
)
from backend.market_data.live import CompletedM15Frontier, LiveDataError
from backend.runtime.coordinator import (
    ChronologicalDataProcessor,
    RuntimeCycle,
    RuntimeDeployment,
)
from backend.runtime.production import StrategyBarProcessor
from backend.strategies.production import (
    EmaSweepConfirmationBreakCompatibilityAdaptor,
)

NOW = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)
DEPLOYMENT = RuntimeDeployment(uuid4(), "101-1", "RUNNING", "RUNNING")


def _bar(start: datetime, value: str = "1.1000") -> Bar:
    price = Decimal(value)
    return Bar(
        Instrument.EUR_USD,
        Timeframe.M15,
        PriceComponent.MID,
        start,
        start + timedelta(minutes=15),
        price,
        price + Decimal("0.0010"),
        price - Decimal("0.0010"),
        price + Decimal("0.0005"),
    )


def _malformed(base: Bar, **changes: object) -> Bar:
    candidate = object.__new__(Bar)
    for name in Bar.__dataclass_fields__:
        object.__setattr__(candidate, name, changes.get(name, getattr(base, name)))
    return candidate


class RecordingProcessor:
    def __init__(self) -> None:
        self.calls: list[Bar] = []

    def process_completed_bar(self, deployment, bar, *, allow_entries):
        self.calls.append(bar)


@pytest.mark.parametrize(
    "changes,pattern",
    [
        ({"complete": False}, "native completed"),
        ({"provider": "OTHER"}, "native completed"),
        ({"instrument": "GBP/USD"}, "native completed"),
        ({"timeframe": Timeframe.M1}, "native completed"),
        ({"price_component": PriceComponent.BID}, "native completed"),
        (
            {
                "start_time": datetime(
                    2026, 8, 30, 13, 45, tzinfo=timezone(timedelta(hours=2))
                ),
                "end_time": datetime(
                    2026, 8, 30, 14, 0, tzinfo=timezone(timedelta(hours=2))
                ),
            },
            "timezone-aware UTC",
        ),
    ],
)
def test_invalid_live_m15_is_rejected_before_strategy(
    changes: dict[str, object], pattern: str
) -> None:
    processor = RecordingProcessor()
    invalid = _malformed(_bar(NOW - timedelta(minutes=15)), **changes)

    with pytest.raises(LiveDataError, match=pattern):
        ChronologicalDataProcessor(processor).process(
            DEPLOYMENT,
            RuntimeCycle(completed_m15=(invalid,), as_of=NOW),
            NOW,
        )

    assert processor.calls == []


def test_future_completed_m15_is_rejected_before_strategy() -> None:
    processor = RecordingProcessor()

    with pytest.raises(LiveDataError, match="not completed"):
        ChronologicalDataProcessor(processor).process(
            DEPLOYMENT,
            RuntimeCycle(completed_m15=(_bar(NOW),), as_of=NOW),
            NOW,
        )

    assert processor.calls == []


def test_durable_frontier_replay_and_next_bar_are_exactly_once() -> None:
    current = _bar(NOW - timedelta(minutes=30))
    frontier = CompletedM15Frontier().accept(current, NOW)
    processor = RecordingProcessor()
    data = ChronologicalDataProcessor(processor, frontier=frontier)
    older = _bar(NOW - timedelta(minutes=45))
    next_bar = _bar(NOW - timedelta(minutes=15))

    assert data.process(
        DEPLOYMENT,
        RuntimeCycle(completed_m15=(older, current), as_of=NOW),
        NOW,
    ) == 0
    assert data.process(
        DEPLOYMENT,
        RuntimeCycle(completed_m15=(next_bar,), as_of=NOW),
        NOW,
    ) == 1
    assert data.process(
        DEPLOYMENT,
        RuntimeCycle(completed_m15=(next_bar,), as_of=NOW),
        NOW,
    ) == 0
    assert processor.calls == [next_bar]

    conflicting = _bar(next_bar.start_time, "1.2000")
    with pytest.raises(LiveDataError, match="conflicting duplicate"):
        data.process(
            DEPLOYMENT,
            RuntimeCycle(completed_m15=(conflicting,), as_of=NOW),
            NOW,
        )
    assert processor.calls == [next_bar]


def test_warmup_seed_is_analytical_only(monkeypatch: pytest.MonkeyPatch) -> None:
    initial = EmaSweepConfirmationBreakCompatibilityAdaptor.initial_state()
    persisted: list[object] = []
    processor = StrategyBarProcessor(
        SimpleNamespace(
            definition=SimpleNamespace(required_historical_context_bars=2)
        ),
        MarketSpecification(Instrument.EUR_USD, Decimal("0.0001")),
        initial,
        SimpleNamespace(),
        persist_state=lambda *values: persisted.append(values),
        persist_evaluation=lambda *values: persisted.append(values),
        on_evaluation=lambda value: persisted.append(value),
    )
    monkeypatch.setattr(
        "backend.runtime.production.evaluate_strategy",
        lambda *args, **kwargs: pytest.fail("warm-up must not evaluate Strategy"),
    )
    bars = (
        _bar(NOW - timedelta(minutes=30)),
        _bar(NOW - timedelta(minutes=15)),
    )

    processor.seed_historical_context(
        bars, as_of=NOW, durable_frontier=NOW
    )

    assert processor.bars == list(bars)
    assert processor.state is initial
    assert processor.pending_entry is None
    assert persisted == []


def test_restart_restores_pending_methodology_exactly_without_evaluation() -> None:
    pending = PendingEntryHandoff(
        EntryPolicy.PRICE_TRIGGERED,
        Direction.LONG,
        Decimal("1.1010"),
        PriceComponent.ASK,
        NOW - timedelta(minutes=15),
        NOW - timedelta(minutes=15),
        5,
        stop_price=Decimal("1.0950"),
        stop_methodology="confirmation_extreme ± (stop_buffer × ATR14)",
    )
    state = replace(
        EmaSweepConfirmationBreakCompatibilityAdaptor.initial_state(),
        last_evaluated_bar_end=NOW - timedelta(minutes=15),
        pending_entry=pending,
    )
    processor = StrategyBarProcessor(
        SimpleNamespace(
            definition=SimpleNamespace(required_historical_context_bars=2)
        ),
        SimpleNamespace(),
        state,
        SimpleNamespace(),
    )

    processor.seed_historical_context(
        (
            _bar(NOW - timedelta(minutes=45)),
            _bar(NOW - timedelta(minutes=30)),
        ),
        as_of=NOW,
        durable_frontier=NOW - timedelta(minutes=15),
    )

    assert processor.pending_entry == pending
    assert processor.state.pending_entry == pending


def test_seeded_100_bar_restart_evaluates_the_next_bar_immediately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    required = 100
    frontier = NOW - timedelta(minutes=15)
    bars = tuple(
        _bar(frontier - timedelta(minutes=15 * (required - index)))
        for index in range(required)
    )
    initial = replace(
        EmaSweepConfirmationBreakCompatibilityAdaptor.initial_state(),
        last_evaluated_bar_end=frontier,
    )
    persisted: list[object] = []
    processor = StrategyBarProcessor(
        SimpleNamespace(
            definition=SimpleNamespace(required_historical_context_bars=required)
        ),
        SimpleNamespace(),
        initial,
        MarketSpecification(Instrument.EUR_USD, Decimal("0.0001")),
        persist_state=lambda *values: persisted.append(values),
    )
    next_bar = _bar(NOW)
    next_state = replace(initial, last_evaluated_bar_end=next_bar.end_time)
    monkeypatch.setattr(
        "backend.runtime.production.evaluate_strategy",
        lambda *args, **kwargs: SimpleNamespace(next_state=next_state),
    )

    processor.seed_historical_context(
        bars,
        as_of=next_bar.end_time,
        durable_frontier=frontier,
    )
    processor.process_completed_bar(DEPLOYMENT, next_bar, allow_entries=True)

    assert len(processor.bars) == required
    assert processor.state == next_state
    assert len(persisted) == 1
