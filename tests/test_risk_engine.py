from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal, localcontext
from typing import Literal, cast
from uuid import UUID, uuid4

import pytest

from backend.config import RiskConfig
from backend.core.account_mode import AccountMode
from backend.core.events import EventBus, EventHandler, RiskApproved, RiskRejected, SignalGenerated
from backend.data.models import Instrument
from backend.risk.engine import PositionInfo, PositionStatus, RiskContext, RiskEngine
from backend.strategy.contracts import Signal, SignalDirection

StopSource = Literal["percentage_of_entry", "absolute_price_distance", "explicit_stop_price"]
ContextChange = Callable[[RiskContext, UUID, UUID, Instrument], RiskContext]


@pytest.fixture
def identity() -> tuple[UUID, UUID, UUID, UUID]:
    return uuid4(), uuid4(), uuid4(), uuid4()


def make_signal(instrument_id: UUID, direction: SignalDirection = SignalDirection.BUY) -> Signal:
    return Signal(
        instrument_id=instrument_id,
        direction=direction,
        strength=Decimal("1"),
        metadata={},
        candle_timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        strategy_version_id=uuid4(),
        strategy_name="test",
        strategy_commit_sha="abc",
    )


def make_context(
    account_id: UUID,
    bot_id: UUID,
    instrument: Instrument,
    *,
    equity: Decimal = Decimal("1000"),
    available_balance: Decimal = Decimal("1000"),
    entry: Decimal = Decimal("100"),
    positions: tuple[PositionInfo, ...] = (),
    timestamp: datetime = datetime(2026, 1, 1, tzinfo=UTC),
) -> RiskContext:
    return RiskContext(
        equity=equity,
        available_balance=available_balance,
        open_positions=positions,
        entry_price=entry,
        instrument=instrument,
        bot_id=bot_id,
        account_id=account_id,
        mode=AccountMode.PAPER,
        clock_timestamp=timestamp,
    )


def make_instrument(
    instrument_id: UUID,
    *,
    is_active: bool = True,
    constraint_values: Mapping[str, str] | None = None,
    **constraints: str,
) -> Instrument:
    all_constraints = dict(constraint_values or {})
    all_constraints.update(constraints)
    return Instrument(
        id=instrument_id,
        symbol="TEST",
        provider="test",
        asset_type="crypto",
        constraints=all_constraints,
        is_active=is_active,
    )


def make_engine(
    account_id: UUID,
    bot_id: UUID,
    instrument: Instrument,
    config: RiskConfig | None = None,
) -> RiskEngine:
    def provider(signal: Signal) -> RiskContext:
        return make_context(account_id, bot_id, instrument)

    return RiskEngine(
        EventBus(), bot_id, account_id, AccountMode.PAPER, config or RiskConfig(), provider
    )


def test_default_percentage_stop_sizes_from_conservatively_rounded_distance(
    identity: tuple[UUID, UUID, UUID, UUID],
) -> None:
    account_id, bot_id, instrument_id, _ = identity
    instrument = make_instrument(instrument_id, tick_size="1", step_size="0.1")
    engine = make_engine(account_id, bot_id, instrument)

    decision = engine.evaluate(
        make_signal(instrument_id), make_context(account_id, bot_id, instrument)
    )

    assert isinstance(decision, RiskApproved)
    assert decision.stop_loss == Decimal("98")
    assert decision.position_size == Decimal("5")
    assert decision.take_profit == Decimal("0")


@pytest.mark.parametrize(
    ("source", "value", "expected_stop"),
    [
        ("percentage_of_entry", Decimal("0.1"), Decimal("90")),
        ("absolute_price_distance", Decimal("10"), Decimal("90")),
        ("explicit_stop_price", Decimal("90"), Decimal("90")),
    ],
)
def test_each_stop_source_is_supported(
    identity: tuple[UUID, UUID, UUID, UUID],
    source: StopSource,
    value: Decimal,
    expected_stop: Decimal,
) -> None:
    account_id, bot_id, instrument_id, _ = identity
    instrument = make_instrument(instrument_id, tick_size="1", step_size="1")
    config = RiskConfig(
        stop_source=source,
        stop_percentage=value if source == "percentage_of_entry" else None,
        stop_distance=value if source == "absolute_price_distance" else None,
        stop_price=value if source == "explicit_stop_price" else None,
    )
    engine = make_engine(account_id, bot_id, instrument, config)

    decision = engine.evaluate(
        make_signal(instrument_id), make_context(account_id, bot_id, instrument)
    )

    assert isinstance(decision, RiskApproved)
    assert decision.stop_loss == expected_stop


def test_sell_stop_and_take_profit_round_away_from_entry(
    identity: tuple[UUID, UUID, UUID, UUID],
) -> None:
    account_id, bot_id, instrument_id, _ = identity
    instrument = make_instrument(instrument_id, tick_size="0.1", step_size="1")
    config = RiskConfig(
        stop_source="explicit_stop_price",
        stop_percentage=None,
        stop_price=Decimal("101.01"),
        take_profit_risk_reward=Decimal("2"),
    )
    engine = make_engine(account_id, bot_id, instrument, config)

    decision = engine.evaluate(
        make_signal(instrument_id, SignalDirection.SELL),
        make_context(account_id, bot_id, instrument),
    )

    assert isinstance(decision, RiskApproved)
    assert decision.stop_loss == Decimal("101.1")
    assert decision.take_profit == Decimal("97.8")


def test_invalid_stop_and_constraints_reject_without_raising(
    identity: tuple[UUID, UUID, UUID, UUID],
) -> None:
    account_id, bot_id, instrument_id, _ = identity
    instrument = make_instrument(instrument_id, step_size="1")
    config = RiskConfig(
        stop_source="explicit_stop_price", stop_percentage=None, stop_price=Decimal("90")
    )
    engine = make_engine(account_id, bot_id, instrument, config)

    decision = engine.evaluate(
        make_signal(instrument_id), make_context(account_id, bot_id, instrument)
    )

    assert isinstance(decision, RiskRejected)
    assert decision.reason.startswith("invalid_instrument_constraint")


def test_existing_position_rejects_same_direction_and_reversal(
    identity: tuple[UUID, UUID, UUID, UUID],
) -> None:
    account_id, bot_id, instrument_id, _ = identity
    instrument = make_instrument(instrument_id, tick_size="1", step_size="1")
    position = PositionInfo(
        account_id=account_id,
        bot_id=bot_id,
        instrument_id=instrument_id,
        direction=SignalDirection.BUY,
        quantity=Decimal("1"),
        status=PositionStatus.OPEN,
    )
    engine = make_engine(account_id, bot_id, instrument)

    same = engine.evaluate(
        make_signal(instrument_id),
        make_context(account_id, bot_id, instrument, positions=(position,)),
    )
    opposite = engine.evaluate(
        make_signal(instrument_id, SignalDirection.SELL),
        make_context(account_id, bot_id, instrument, positions=(position,)),
    )

    assert isinstance(same, RiskRejected) and same.reason.startswith("direction_conflict")
    assert isinstance(opposite, RiskRejected) and opposite.reason.startswith("direction_conflict")


def test_close_is_zero_quantity_and_approved_when_flat(
    identity: tuple[UUID, UUID, UUID, UUID],
) -> None:
    account_id, bot_id, instrument_id, _ = identity
    instrument = make_instrument(instrument_id)
    engine = make_engine(account_id, bot_id, instrument)

    decision = engine.evaluate(
        make_signal(instrument_id, SignalDirection.CLOSE),
        make_context(account_id, bot_id, instrument, equity=Decimal("0"), entry=Decimal("0")),
    )

    assert isinstance(decision, RiskApproved)
    assert decision.position_size == decision.stop_loss == decision.take_profit == Decimal("0")


@pytest.mark.asyncio
async def test_event_adapter_filters_foreign_bots_and_preserves_correlation(
    identity: tuple[UUID, UUID, UUID, UUID],
) -> None:
    account_id, bot_id, instrument_id, foreign_bot_id = identity
    instrument = make_instrument(instrument_id, tick_size="1", step_size="1")
    calls: list[Signal] = []

    async def provider(signal: Signal) -> RiskContext:
        calls.append(signal)
        return make_context(account_id, bot_id, instrument)

    bus = EventBus()
    decisions: list[RiskApproved | RiskRejected] = []

    async def collect_approved(event: RiskApproved) -> None:
        decisions.append(event)

    async def collect_rejected(event: RiskRejected) -> None:
        decisions.append(event)

    bus.subscribe(RiskApproved, cast("EventHandler", collect_approved))
    bus.subscribe(RiskRejected, cast("EventHandler", collect_rejected))
    engine = RiskEngine(bus, bot_id, account_id, AccountMode.PAPER, RiskConfig(), provider)
    signal = make_signal(instrument_id)

    await bus.publish(
        SignalGenerated(
            signal=signal, bot_id=foreign_bot_id, account_id=account_id, mode=AccountMode.PAPER
        )
    )
    assert calls == []

    source = SignalGenerated(
        signal=signal, bot_id=bot_id, account_id=account_id, mode=AccountMode.PAPER
    )
    await bus.publish(source)
    assert len(decisions) == 1
    assert decisions[0].correlation_id == source.correlation_id
    engine.close()


@pytest.mark.asyncio
async def test_pending_reservation_is_released_by_terminal_hook(
    identity: tuple[UUID, UUID, UUID, UUID],
) -> None:
    account_id, bot_id, instrument_id, _ = identity
    instrument = make_instrument(instrument_id, tick_size="1", step_size="1")
    bus = EventBus()
    decisions: list[RiskApproved | RiskRejected] = []

    async def collect_approved(event: RiskApproved) -> None:
        decisions.append(event)

    async def collect_rejected(event: RiskRejected) -> None:
        decisions.append(event)

    bus.subscribe(RiskApproved, cast("EventHandler", collect_approved))
    bus.subscribe(RiskRejected, cast("EventHandler", collect_rejected))
    engine = RiskEngine(
        bus,
        bot_id,
        account_id,
        AccountMode.PAPER,
        RiskConfig(),
        lambda signal: make_context(account_id, bot_id, instrument),
    )
    signal = make_signal(instrument_id)
    source = SignalGenerated(
        signal=signal, account_id=account_id, bot_id=bot_id, mode=AccountMode.PAPER
    )
    await bus.publish(source)
    await bus.publish(source)
    assert isinstance(decisions[-1], RiskRejected)
    engine.release_reservation(instrument_id)
    await bus.publish(source)
    assert isinstance(decisions[-1], RiskApproved)


def assert_rejected(decision: RiskApproved | RiskRejected, code: str) -> None:
    assert isinstance(decision, RiskRejected)
    assert decision.reason.startswith(code)


def test_runtime_risk_limit_is_enforced(identity: tuple[UUID, UUID, UUID, UUID]) -> None:
    account_id, bot_id, instrument_id, _ = identity
    instrument = make_instrument(instrument_id, tick_size="1", step_size="1")
    config = RiskConfig()
    config.per_trade_risk = Decimal("0.03")
    decision = make_engine(account_id, bot_id, instrument, config).evaluate(
        make_signal(instrument_id), make_context(account_id, bot_id, instrument)
    )
    assert_rejected(decision, "risk_limit_exceeded")


def test_max_open_positions_rejects_exact_boundary_with_pending_reservations(
    identity: tuple[UUID, UUID, UUID, UUID],
) -> None:
    account_id, bot_id, instrument_id, other_instrument_id = identity
    first = make_instrument(instrument_id, tick_size="1", step_size="1")
    third_instrument_id = uuid4()
    third = make_instrument(third_instrument_id, tick_size="1", step_size="1")
    config = RiskConfig(max_open_positions=2)
    engine = make_engine(account_id, bot_id, first, config)
    engine._reservations.add((account_id, other_instrument_id, AccountMode.PAPER))
    position = PositionInfo(
        account_id=account_id,
        bot_id=bot_id,
        instrument_id=instrument_id,
        direction=SignalDirection.BUY,
        quantity=Decimal("1"),
        status=PositionStatus.OPEN,
    )
    decision = engine.evaluate(
        make_signal(third_instrument_id),
        make_context(account_id, bot_id, third, positions=(position,)),
    )
    assert_rejected(decision, "max_open_positions")


def test_quantity_constraints_reject_limits_and_min_notional(
    identity: tuple[UUID, UUID, UUID, UUID],
) -> None:
    account_id, bot_id, instrument_id, _ = identity
    limited = make_instrument(
        instrument_id, tick_size="1", step_size="1", min_qty="6", max_qty="10"
    )
    decision = make_engine(account_id, bot_id, limited).evaluate(
        make_signal(instrument_id), make_context(account_id, bot_id, limited)
    )
    assert_rejected(decision, "invalid_quantity")

    notional = make_instrument(instrument_id, tick_size="1", step_size="1", min_notional="501")
    decision = make_engine(account_id, bot_id, notional).evaluate(
        make_signal(instrument_id), make_context(account_id, bot_id, notional)
    )
    assert_rejected(decision, "quantity_below_min_notional")


def test_invalid_quantity_step_path_is_rejected(
    identity: tuple[UUID, UUID, UUID, UUID], monkeypatch: pytest.MonkeyPatch
) -> None:
    account_id, bot_id, instrument_id, _ = identity
    instrument = make_instrument(instrument_id, tick_size="1", step_size="1")
    engine = make_engine(account_id, bot_id, instrument)

    def invalid_quantity(equity: Decimal, distance: Decimal, asset: Instrument) -> Decimal:
        return Decimal("1.5")

    monkeypatch.setattr(engine, "_calculate_quantity", invalid_quantity)
    decision = engine.evaluate(
        make_signal(instrument_id), make_context(account_id, bot_id, instrument)
    )
    assert_rejected(decision, "invalid_quantity")


@pytest.mark.parametrize(
    ("context_change", "code"),
    [
        (
            lambda context, account, bot, instrument: replace(context, bot_id=uuid4()),
            "identity_mismatch",
        ),
        (
            lambda context, account, bot, instrument: replace(context, account_id=uuid4()),
            "identity_mismatch",
        ),
        (
            lambda context, account, bot, instrument: replace(context, mode=AccountMode.TESTNET),
            "identity_mismatch",
        ),
        (
            lambda context, account, bot, instrument: replace(
                context, instrument=make_instrument(uuid4())
            ),
            "identity_mismatch",
        ),
        (
            lambda context, account, bot, instrument: replace(
                context, clock_timestamp=datetime(2026, 1, 1)
            ),
            "invalid_timestamp",
        ),
        (
            lambda context, account, bot, instrument: replace(context, equity=Decimal("-1")),
            "invalid_equity",
        ),
        (
            lambda context, account, bot, instrument: replace(
                context, available_balance=Decimal("-1")
            ),
            "invalid_balance",
        ),
        (
            lambda context, account, bot, instrument: replace(context, entry_price=Decimal("0")),
            "invalid_entry_price",
        ),
    ],
)
def test_identity_timestamp_and_entry_context_rejections(
    identity: tuple[UUID, UUID, UUID, UUID], context_change: ContextChange, code: str
) -> None:
    account_id, bot_id, instrument_id, _ = identity
    instrument = make_instrument(instrument_id, tick_size="1", step_size="1")
    context = make_context(account_id, bot_id, instrument)
    changed = context_change(context, account_id, bot_id, instrument)
    decision = make_engine(account_id, bot_id, instrument).evaluate(
        make_signal(instrument_id), changed
    )
    assert_rejected(decision, code)


def test_inactive_instrument_and_missing_stop_reject(
    identity: tuple[UUID, UUID, UUID, UUID],
) -> None:
    account_id, bot_id, instrument_id, _ = identity
    inactive = make_instrument(instrument_id, is_active=False, tick_size="1", step_size="1")
    decision = make_engine(account_id, bot_id, inactive).evaluate(
        make_signal(instrument_id), make_context(account_id, bot_id, inactive)
    )
    assert_rejected(decision, "invalid_instrument_constraint")

    config = RiskConfig()
    config.stop_percentage = None
    active = make_instrument(instrument_id, tick_size="1", step_size="1")
    decision = make_engine(account_id, bot_id, active, config).evaluate(
        make_signal(instrument_id), make_context(account_id, bot_id, active)
    )
    assert_rejected(decision, "missing_stop")


@pytest.mark.parametrize("direction", [SignalDirection.BUY, SignalDirection.SELL])
def test_wrong_side_stop_rejects_for_both_directions(
    identity: tuple[UUID, UUID, UUID, UUID], direction: SignalDirection
) -> None:
    account_id, bot_id, instrument_id, _ = identity
    config = RiskConfig(
        stop_source="explicit_stop_price",
        stop_percentage=None,
        stop_price=Decimal("101") if direction is SignalDirection.BUY else Decimal("99"),
    )
    instrument = make_instrument(instrument_id, tick_size="1", step_size="1")
    decision = make_engine(account_id, bot_id, instrument, config).evaluate(
        make_signal(instrument_id, direction), make_context(account_id, bot_id, instrument)
    )
    assert_rejected(decision, "invalid_stop")


@pytest.mark.parametrize("rounded_stop", [Decimal("0"), Decimal("100")])
def test_post_rounding_zero_or_wrong_side_stop_rejects(
    identity: tuple[UUID, UUID, UUID, UUID],
    rounded_stop: Decimal,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    account_id, bot_id, instrument_id, _ = identity
    instrument = make_instrument(instrument_id, tick_size="1", step_size="1")
    engine = make_engine(account_id, bot_id, instrument)
    monkeypatch.setattr(engine, "_round_stop", lambda direction, stop, asset: rounded_stop)
    decision = engine.evaluate(
        make_signal(instrument_id), make_context(account_id, bot_id, instrument)
    )
    assert_rejected(decision, "invalid_stop")


def test_invalid_take_profit_ratio_rejects_at_runtime(
    identity: tuple[UUID, UUID, UUID, UUID],
) -> None:
    account_id, bot_id, instrument_id, _ = identity
    config = RiskConfig(take_profit_risk_reward=Decimal("1"))
    config.take_profit_risk_reward = Decimal("0")
    instrument = make_instrument(instrument_id, tick_size="1", step_size="1")
    decision = make_engine(account_id, bot_id, instrument, config).evaluate(
        make_signal(instrument_id), make_context(account_id, bot_id, instrument)
    )
    assert_rejected(decision, "invalid_take_profit")


def test_take_profit_rounding_geometry_rejects_when_precision_collapses_distance(
    identity: tuple[UUID, UUID, UUID, UUID],
) -> None:
    account_id, bot_id, instrument_id, _ = identity
    config = RiskConfig(take_profit_risk_reward=Decimal("0.0001"))
    instrument = make_instrument(instrument_id, tick_size="1", step_size="1")
    with localcontext() as context:
        context.prec = 2
        decision = make_engine(account_id, bot_id, instrument, config).evaluate(
            make_signal(instrument_id), make_context(account_id, bot_id, instrument)
        )
    assert_rejected(decision, "invalid_take_profit")


@pytest.mark.parametrize(
    "constraints",
    [
        {"step_size": "1"},
        {"tick_size": "1", "step_size": "0"},
        {"tick_size": "1", "step_size": "not-a-number"},
        {"tick_size": "1", "step_size": "1", "min_qty": "bad"},
        {"tick_size": "1", "step_size": "1", "min_qty": "-1"},
        {"tick_size": "1", "step_size": "1", "max_qty": "bad"},
        {"tick_size": "1", "step_size": "1", "min_notional": "-1"},
    ],
)
def test_constraint_validation_variants_reject_safely(
    identity: tuple[UUID, UUID, UUID, UUID], constraints: dict[str, str]
) -> None:
    account_id, bot_id, instrument_id, _ = identity
    instrument = make_instrument(instrument_id, constraint_values=constraints)
    decision = make_engine(account_id, bot_id, instrument).evaluate(
        make_signal(instrument_id), make_context(account_id, bot_id, instrument)
    )
    assert_rejected(decision, "invalid_instrument_constraint")


@pytest.mark.asyncio
async def test_protocol_context_provider_path_and_identity_event_rejection(
    identity: tuple[UUID, UUID, UUID, UUID],
) -> None:
    account_id, bot_id, instrument_id, _ = identity
    instrument = make_instrument(instrument_id, tick_size="1", step_size="1")

    class Provider:
        def get_context(self, signal: Signal) -> RiskContext:
            return make_context(account_id, bot_id, instrument)

    bus = EventBus()
    decisions: list[RiskRejected] = []
    approved: list[RiskApproved] = []

    async def collect(event: RiskRejected) -> None:
        decisions.append(event)

    async def collect_approved(event: RiskApproved) -> None:
        approved.append(event)

    bus.subscribe(RiskRejected, cast("EventHandler", collect))
    bus.subscribe(RiskApproved, cast("EventHandler", collect_approved))
    engine = RiskEngine(bus, bot_id, account_id, AccountMode.PAPER, RiskConfig(), Provider())
    await_publish = SignalGenerated(
        signal=make_signal(instrument_id),
        account_id=uuid4(),
        bot_id=bot_id,
        mode=AccountMode.PAPER,
    )

    await bus.publish(await_publish)
    assert len(decisions) == 1
    assert decisions[0].reason.startswith("identity_mismatch")
    await bus.publish(replace(await_publish, account_id=account_id, correlation_id=uuid4()))
    assert len(approved) == 1
    engine.close()


@pytest.mark.asyncio
async def test_reset_reservations_and_terminal_outcome_release(
    identity: tuple[UUID, UUID, UUID, UUID],
) -> None:
    account_id, bot_id, instrument_id, _ = identity
    instrument = make_instrument(instrument_id, tick_size="1", step_size="1")
    engine = make_engine(account_id, bot_id, instrument)
    signal = make_signal(instrument_id)
    context = make_context(account_id, bot_id, instrument)
    assert isinstance(engine.evaluate(signal, context), RiskApproved)
    engine._reservations.add((account_id, instrument_id, AccountMode.PAPER))
    engine.reset_reservations()
    engine._reservations.add((account_id, instrument_id, AccountMode.PAPER))
    engine.on_terminal_outcome(instrument_id)
    assert (account_id, instrument_id, AccountMode.PAPER) not in engine._reservations
