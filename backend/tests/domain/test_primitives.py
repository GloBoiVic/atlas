from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from backend.domain.market_data import (
    ALIGNMENT_CONVENTION,
    FINGERPRINT_SCHEMA,
    SESSION_POLICY,
    Bar,
    DatasetSnapshot,
    InputError,
    Instrument,
    PriceComponent,
    Provider,
    Timeframe,
    VenueInstrument,
)
from backend.domain.strategy import (
    Action,
    Direction,
    ParameterError,
    ParameterSchema,
    Phase,
    Rationale,
    StateError,
    StopProposal,
    StrategyContext,
    StrategyDecision,
    StrategyParameters,
    StrategyState,
    StrategyVersion,
    TargetProposal,
    VersionError,
)


def bar(at: datetime, *, close: str = "1.1000") -> Bar:
    return Bar(
        Instrument.EUR_USD,
        Timeframe.M15,
        PriceComponent.MID,
        at,
        at + timedelta(minutes=15),
        Decimal("1.0900"),
        Decimal("1.1100"),
        Decimal("1.0800"),
        Decimal(close),
    )


def test_bar_is_completed_eurusd_mid_15m_and_serializes_decimals_as_strings() -> None:
    candle = bar(datetime(2026, 1, 1, 10, 0, tzinfo=UTC))
    assert candle.to_json()["open"] == "1.0900"
    assert candle.to_json()["start_time"].endswith("Z")


@pytest.mark.parametrize(
    "change",
    [
        {"complete": False},
        {"instrument": "EUR/USD"},
        {"start_time": datetime(2026, 1, 1, 10, 0)},
        {"high": Decimal("1.05")},
    ],
)
def test_bar_rejects_invalid_contract_input(change: dict[str, object]) -> None:
    values: dict[str, object] = {
        "instrument": Instrument.EUR_USD,
        "timeframe": Timeframe.M15,
        "price_component": PriceComponent.MID,
        "start_time": datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
        "end_time": datetime(2026, 1, 1, 10, 15, tzinfo=UTC),
        "open": Decimal("1.09"),
        "high": Decimal("1.11"),
        "low": Decimal("1.08"),
        "close": Decimal("1.10"),
        "complete": True,
    }
    values.update(change)
    with pytest.raises((InputError, TypeError)):
        Bar(**values)  # type: ignore[arg-type]


def test_bar_rejects_off_grid_15m_start() -> None:
    with pytest.raises(InputError):
        bar(datetime(2026, 1, 1, 10, 1, tzinfo=UTC))


def test_market_data_boundary_accepts_m1_bid_and_ask() -> None:
    for component in (PriceComponent.BID, PriceComponent.ASK):
        candle = Bar(
            Instrument.EUR_USD,
            Timeframe.M1,
            component,
            datetime(2026, 1, 1, 10, 1, tzinfo=UTC),
            datetime(2026, 1, 1, 10, 2, tzinfo=UTC),
            Decimal("1.09"),
            Decimal("1.11"),
            Decimal("1.08"),
            Decimal("1.10"),
            volume=Decimal("2"),
        )
        assert candle.provider is Provider.OANDA
        assert candle.to_json()["volume"] == "2"


@pytest.mark.parametrize(
    "values",
    [
        {"provider": "OANDA"},
        {
            "instrument": Instrument.EUR_USD,
            "provider": Provider.OANDA,
            "provider_symbol": "EURUSD",
        },
        {
            "instrument": Instrument.EUR_USD,
            "provider": Provider.OANDA,
            "provider_symbol": "EUR_USD",
            "extra": True,
        },
    ],
)
def test_venue_instrument_rejects_invalid_mapping(values: dict[str, object]) -> None:
    with pytest.raises((InputError, TypeError)):
        VenueInstrument(**values)  # type: ignore[arg-type]


def test_dataset_snapshot_validates_and_serializes_descriptor() -> None:
    snapshot = DatasetSnapshot(
        uuid4(),
        VenueInstrument(Instrument.EUR_USD, Provider.OANDA, "EUR_USD"),
        Timeframe.M1,
        (PriceComponent.ASK, PriceComponent.BID, PriceComponent.MID),
        datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
        datetime(2026, 1, 1, 11, 0, tzinfo=UTC),
        ALIGNMENT_CONVENTION,
        SESSION_POLICY,
        FINGERPRINT_SCHEMA,
        "a" * 64,
        {"status": "VALID", "bar_count": 180},
        datetime(2026, 1, 1, 12, tzinfo=UTC),
    )
    assert snapshot.to_json()["components"] == ["ASK", "BID", "MID"]
    with pytest.raises(InputError):
        DatasetSnapshot(
            uuid4(),
            snapshot.venue_instrument,
            Timeframe.M15,
            snapshot.components,
            snapshot.coverage_start,
            snapshot.coverage_end,
            ALIGNMENT_CONVENTION,
            SESSION_POLICY,
            FINGERPRINT_SCHEMA,
            "a" * 63,
            {"status": "VALID"},
            snapshot.created_at,
        )


@pytest.mark.parametrize(
    "change",
    [
        {"open": Decimal("0")},
        {"high": Decimal("1.05")},
        {"volume": Decimal("-1")},
        {"end_time": datetime(2026, 1, 1, 10, 16, tzinfo=UTC)},
    ],
)
def test_bar_rejects_invalid_values_timing_and_volume(
    change: dict[str, object],
) -> None:
    values: dict[str, object] = {
        "instrument": Instrument.EUR_USD,
        "provider": Provider.OANDA,
        "timeframe": Timeframe.M15,
        "price_component": PriceComponent.MID,
        "start_time": datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
        "end_time": datetime(2026, 1, 1, 10, 15, tzinfo=UTC),
        "open": Decimal("1.09"),
        "high": Decimal("1.11"),
        "low": Decimal("1.08"),
        "close": Decimal("1.10"),
    }
    values.update(change)
    with pytest.raises(InputError):
        Bar(**values)  # type: ignore[arg-type]


def test_context_rejects_wrong_market_data_dimensions() -> None:
    start = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
    invalid = (
        Bar(
            Instrument.EUR_USD,
            Timeframe.M1,
            PriceComponent.MID,
            start,
            start + timedelta(minutes=1),
            Decimal("1.09"),
            Decimal("1.11"),
            Decimal("1.08"),
            Decimal("1.10"),
        ),
        Bar(
            Instrument.EUR_USD,
            Timeframe.M15,
            PriceComponent.BID,
            start,
            start + timedelta(minutes=15),
            Decimal("1.09"),
            Decimal("1.11"),
            Decimal("1.08"),
            Decimal("1.10"),
        ),
    )
    for candle in invalid:
        with pytest.raises(InputError):
            StrategyContext(candle.end_time, Instrument.EUR_USD, (candle,))


def test_context_rejects_duplicate_or_future_bars() -> None:
    first = bar(datetime(2026, 1, 1, 10, 0, tzinfo=UTC))
    with pytest.raises(InputError):
        StrategyContext(first.end_time, Instrument.EUR_USD, (first, first))
    with pytest.raises(InputError):
        StrategyContext(first.start_time, Instrument.EUR_USD, (first,))


def test_context_requires_strict_enum_and_tuple_inputs() -> None:
    first = bar(datetime(2026, 1, 1, 10, 0, tzinfo=UTC))
    with pytest.raises(InputError):
        StrategyContext(first.end_time, "EUR/USD", (first,))  # type: ignore[arg-type]
    with pytest.raises(InputError):
        StrategyContext(first.end_time, Instrument.EUR_USD, [first])  # type: ignore[arg-type]
    with pytest.raises(InputError):
        StrategyContext(first.end_time, Instrument.EUR_USD, (first,), position="FLAT")  # type: ignore[arg-type]


def test_parameters_are_decimal_safe_and_immutable() -> None:
    parameters = StrategyParameters()
    assert parameters.to_json() == {
        "ema_period": 100,
        "atr_period": 14,
        "stop_buffer": "0.5",
        "target_r": "1.7",
        "expiry_window": 5,
    }
    with pytest.raises(ParameterError):
        StrategyParameters(ema_period=True)  # type: ignore[arg-type]
    with pytest.raises(ParameterError):
        StrategyParameters(stop_buffer=0.5)  # type: ignore[arg-type]
    with pytest.raises(ParameterError):
        StrategyParameters(expiry_window=6)


@pytest.mark.parametrize(
    "changes",
    [
        {"key": ""},
        {"label": ""},
        {"type": ""},
        {"description": ""},
        {"key": 1},
        {"nullable": 1},
        {"allowed_values": ["LONG"]},
        {"allowed_values": ("LONG", 1)},
        {"allowed_values": ("LONG", "LONG")},
        {"default": True},
        {"minimum": 0.5},
        {"maximum": False},
    ],
)
def test_parameter_schema_rejects_invalid_descriptor_fields(
    changes: dict[str, object],
) -> None:
    values: dict[str, object] = {
        "key": "direction",
        "label": "Direction",
        "type": "enum",
        "default": "LONG",
        "nullable": False,
        "minimum": None,
        "maximum": None,
        "description": "Direction",
        "allowed_values": ("LONG", "SHORT"),
    }
    values.update(changes)
    with pytest.raises(ParameterError):
        ParameterSchema(**values)  # type: ignore[arg-type]


def test_target_is_methodology_until_actual_entry_is_supplied() -> None:
    target = TargetProposal()
    assert target.to_json() == {"methodology": "R_MULTIPLE", "multiple": "1.7"}
    assert target.resolve(
        Decimal("1.105"), Decimal("1.095"), Direction.LONG
    ) == Decimal("1.1220")
    assert target.resolve(
        Decimal("1.095"), Decimal("1.105"), Direction.SHORT
    ) == Decimal("1.0780")
    with pytest.raises(InputError):
        target.resolve(Decimal("1.100"), Decimal("1.100"), Direction.LONG)


def test_state_and_decision_serialization_are_explicit() -> None:
    state = StrategyState(
        phase=Phase.REFERENCE_IDENTIFIED,
        direction=Direction.LONG,
        reference_high=Decimal("1.11"),
        reference_low=Decimal("1.08"),
        reference_time=datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
    )
    decision = StrategyDecision(Action.NO_ACTION, rationale=Rationale("WARMING_UP"))
    assert state.to_json()["reference_high"] == "1.11"
    assert decision.to_json()["action"] == "NO_ACTION"


def test_decision_open_requires_matching_utc_geometry_and_time() -> None:
    rationale = Rationale("CONFIRMED", (("trend", "above EMA"),))
    stop = StopProposal(Decimal("1.090"), Direction.LONG)
    target = TargetProposal()
    with pytest.raises(InputError):
        StrategyDecision(
            Action.OPEN_LONG, rationale, Direction.LONG, None, stop, target
        )
    with pytest.raises(InputError):
        StrategyDecision(
            Action.OPEN_LONG,
            rationale,
            Direction.SHORT,
            datetime(2026, 1, 1, 10, 15, tzinfo=UTC),
            stop,
            target,
        )
    with pytest.raises(InputError):
        StrategyDecision(
            Action.OPEN_LONG,
            rationale,
            Direction.LONG,
            datetime(2026, 1, 1, 10, 15),
            stop,
            target,
        )


def test_non_opening_decisions_reject_geometry_and_rationale_keys_are_unique() -> None:
    with pytest.raises(InputError):
        StrategyDecision(
            Action.NO_ACTION, Rationale("NO_SETUP"), direction=Direction.LONG
        )
    with pytest.raises(InputError):
        Rationale("DUPLICATE", (("bar", "one"), ("bar", "two")))


def test_state_round_trips_and_rejects_malformed_envelopes() -> None:
    state = StrategyState(
        phase=Phase.REFERENCE_IDENTIFIED,
        direction=Direction.LONG,
        reference_high=Decimal("1.11"),
        reference_low=Decimal("1.08"),
        reference_time=datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
    )
    assert StrategyState.from_json(state.to_json()) == state
    malformed = state.to_json()
    malformed.pop("phase")
    with pytest.raises(StateError):
        StrategyState.from_json(malformed)
    with pytest.raises(StateError):
        StrategyState.from_json(
            {**state.to_json(), "reference_time": "2026-01-01T10:00:00"}
        )


def test_state_rejects_bool_integers_and_zero_window_confirmation() -> None:
    with pytest.raises(StateError):
        StrategyState(schema_version=True)  # type: ignore[arg-type]
    with pytest.raises(StateError):
        StrategyState(
            phase=Phase.AWAITING_CONFIRMATION,
            direction=Direction.LONG,
            reference_high=Decimal("1.11"),
            reference_low=Decimal("1.08"),
            reference_time=datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
            sweep_time=datetime(2026, 1, 1, 10, 15, tzinfo=UTC),
            window_bars=0,
        )


def test_decision_requires_strict_boundary_types() -> None:
    with pytest.raises(InputError):
        StrategyDecision("NO_ACTION", Rationale("X"))  # type: ignore[arg-type]


def test_strategy_version_requires_lowercase_sha256_and_serializes() -> None:
    version = StrategyVersion(
        uuid4(),
        "ema-sweep-engulfing",
        1,
        "a" * 64,
        "ema-sweep-engulfing",
        (
            ParameterSchema(
                "ema_period", "EMA period", "integer", 100, False, 1, None, "EMA"
            ),
        ),
    )
    assert version.to_json()["source_fingerprint"] == "a" * 64
    descriptor = version.to_json()["parameter_schema"][0]
    assert descriptor["allowed_values"] == []
    with pytest.raises(VersionError):
        StrategyVersion(uuid4(), "x", 1, "A" * 64, "x", ())
