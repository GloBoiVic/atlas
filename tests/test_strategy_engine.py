from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from backend.core.account_mode import AccountMode
from backend.core.events import (
    CandleClosed,
    EventBus,
    InMemoryFailureRecorder,
    SignalGenerated,
    StrategyError,
)
from backend.core.logging import setup_logging
from backend.data.models import Candle
from backend.strategy import (
    DataRequirement,
    DataType,
    SignalDirection,
    Strategy,
    StrategyDecision,
    StrategyEngine,
)


class RecordingStrategy(Strategy):
    def __init__(self, decisions: list[StrategyDecision | None]) -> None:
        super().__init__({})
        self.candles: list[Candle] = []
        self.decisions = decisions

    def on_candle(self, candle: Candle) -> StrategyDecision | None:
        self.candles.append(candle)
        return self.decisions[len(self.candles) - 1] if self.decisions else None


class FailingStrategy(Strategy):
    def on_candle(self, candle: Candle) -> StrategyDecision | None:
        raise RuntimeError("strategy exploded")


def make_candle(
    instrument_id: UUID,
    *,
    open_time: datetime,
    provider: str = "binance",
    timeframe: str = "1m",
    price_basis: str = "trade",
    is_complete: bool = True,
) -> Candle:
    return Candle(
        instrument_id=instrument_id,
        provider=provider,
        timeframe=timeframe,
        open_time=open_time,
        price_basis=price_basis,
        open=Decimal("100"),
        high=Decimal("101"),
        low=Decimal("99"),
        close=Decimal("100"),
    ) if is_complete else Candle(
        instrument_id=instrument_id,
        provider=provider,
        timeframe=timeframe,
        open_time=open_time,
        price_basis=price_basis,
        open=Decimal("100"),
        high=Decimal("101"),
        low=Decimal("99"),
        close=Decimal("100"),
        is_complete=False,
    )


@pytest.fixture
def identity() -> tuple[UUID, UUID, UUID, UUID]:
    return uuid4(), uuid4(), uuid4(), uuid4()


def make_engine(
    bus: EventBus,
    strategy: Strategy,
    identity: tuple[UUID, UUID, UUID, UUID],
) -> StrategyEngine:
    account_id, bot_id, instrument_id, version_id = identity
    return StrategyEngine(
        event_bus=bus,
        bot_id=bot_id,
        account_id=account_id,
        instrument_id=instrument_id,
        strategy=strategy,
        strategy_version_id=version_id,
        strategy_name="test-strategy",
        commit_sha="abc123",
        data_requirement=DataRequirement(DataType.CANDLE, "1m"),
    )


@pytest.mark.asyncio
async def test_engine_subscribes_and_suppresses_warmup_signals(
    identity: tuple[UUID, UUID, UUID, UUID],
) -> None:
    bus = EventBus()
    decision = StrategyDecision(SignalDirection.BUY, Decimal("0.8"), {"source": "test"})
    strategy = RecordingStrategy([decision, decision])
    engine = make_engine(bus, strategy, identity)
    candle = make_candle(identity[2], open_time=datetime(2026, 1, 1, tzinfo=UTC))
    signals: list[SignalGenerated] = []

    async def collect_signal(event: SignalGenerated) -> None:
        signals.append(event)

    bus.subscribe(SignalGenerated, collect_signal)

    await engine.warm_up([candle])
    await bus.publish(CandleClosed(candle=candle, bot_id=identity[1]))

    assert len(strategy.candles) == 1
    assert signals == []


@pytest.mark.asyncio
async def test_engine_emits_provenance_after_warmup(
    identity: tuple[UUID, UUID, UUID, UUID],
) -> None:
    bus = EventBus()
    decision = StrategyDecision(SignalDirection.SELL, Decimal("0.7"), {"x": 1})
    strategy = RecordingStrategy([None, decision])
    engine = make_engine(bus, strategy, identity)
    first = make_candle(identity[2], open_time=datetime(2026, 1, 1, tzinfo=UTC))
    live = make_candle(identity[2], open_time=datetime(2026, 1, 1, 0, 1, tzinfo=UTC))
    received: list[SignalGenerated] = []

    async def collect_signal(event: SignalGenerated) -> None:
        received.append(event)

    bus.subscribe(SignalGenerated, collect_signal)

    await engine.warm_up([first])
    source = CandleClosed(
        candle=live,
        account_id=identity[0],
        bot_id=identity[1],
        mode=AccountMode.PAPER,
    )
    await bus.publish(source)

    signal = received[0].signal
    assert signal.instrument_id == identity[2]
    assert signal.strategy_version_id == identity[3]
    assert signal.candle_timestamp == live.open_time
    assert signal.strategy_name == "test-strategy"
    assert received[0].correlation_id == source.correlation_id


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("instrument", "timeframe", "complete"),
    [(None, "1m", True), ("same", "5m", True), ("same", "1m", False)],
)
async def test_engine_rejects_invalid_candles(
    identity: tuple[UUID, UUID, UUID, UUID], instrument: str | None, timeframe: str, complete: bool
) -> None:
    bus = EventBus()
    strategy = RecordingStrategy([])
    engine = make_engine(bus, strategy, identity)
    await engine.warm_up([])
    candle = make_candle(
        identity[2] if instrument == "same" else uuid4(),
        open_time=datetime(2026, 1, 1, tzinfo=UTC),
        timeframe=timeframe,
        is_complete=complete,
    )

    await bus.publish(CandleClosed(candle=candle))

    assert strategy.candles == []


@pytest.mark.asyncio
async def test_engine_deduplicates_by_composite_candle_key(
    identity: tuple[UUID, UUID, UUID, UUID],
) -> None:
    bus = EventBus()
    strategy = RecordingStrategy([])
    engine = make_engine(bus, strategy, identity)
    open_time = datetime(2026, 1, 1, tzinfo=UTC)
    candle = make_candle(identity[2], open_time=open_time)
    equivalent = make_candle(identity[2], open_time=open_time)
    different_basis = make_candle(identity[2], open_time=open_time, price_basis="mid")
    await engine.warm_up([])

    await bus.publish(CandleClosed(candle=candle))
    await bus.publish(CandleClosed(candle=equivalent))
    await bus.publish(CandleClosed(candle=different_basis))

    assert strategy.candles == [candle, different_basis]


@pytest.mark.asyncio
async def test_strategy_failure_publishes_error_reraises_and_pauses_bot(
    identity: tuple[UUID, UUID, UUID, UUID],
) -> None:
    setup_logging()
    recorder = InMemoryFailureRecorder()
    paused: list[UUID] = []
    bus = EventBus(failure_recorder=recorder, pause_bot=paused.append)
    errors: list[StrategyError] = []

    async def collect_error(event: StrategyError) -> None:
        errors.append(event)

    bus.subscribe(StrategyError, collect_error)
    engine = make_engine(bus, FailingStrategy({}), identity)
    await engine.warm_up([])
    candle = make_candle(identity[2], open_time=datetime(2026, 1, 1, tzinfo=UTC))
    source = CandleClosed(candle=candle, bot_id=identity[1])

    await bus.publish(source)

    assert errors[0].error == "strategy exploded"
    assert len(recorder.failures) == 1
    assert paused == [identity[1]]


@pytest.mark.asyncio
async def test_engine_close_unsubscribes(identity: tuple[UUID, UUID, UUID, UUID]) -> None:
    bus = EventBus()
    strategy = RecordingStrategy([])
    engine = make_engine(bus, strategy, identity)
    engine.close()
    await engine.warm_up([])
    candle = make_candle(identity[2], open_time=datetime(2026, 1, 1, tzinfo=UTC))

    await bus.publish(CandleClosed(candle=candle))

    assert strategy.candles == []
    assert bus.stats == {"subscribed_events": 0}
