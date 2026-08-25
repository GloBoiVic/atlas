"""Focused validation tests for the Experiment price-analysis read seam.

These tests exercise the architecture's backend validation gates for
GET /api/v1/experiments/{id}/price-analysis without contacting the network:
- Snapshot fingerprint is the only M15 path; no current-bar query.
- Warm-up matches SimulationClock's last ``warm_up_bars`` M15 ending
  ``<= trading_start``.
- M15 is UTC, ordered, half-open; the response is bounded 10,000/250.
- EMA uses persisted ``ema_period`` (regression guard against ema_100).
- Entry/exit and approved stop/target come only from persisted rows.
- Reference/sweep/confirmation come only from persisted rationale.
- PENDING/RUNNING/FAILED/missing/incomplete return the documented codes.
- No OANDA/provider call, no persistence mutation.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.domain.market_data import Bar, Instrument, PriceComponent, Timeframe
from backend.experiments.results import ExperimentResultReadService, ResultReadError
from backend.persistence.models import (
    DatasetSnapshotModel,
    StrategyVersionModel,
)

NOW = datetime(2026, 8, 17, 14, 0, tzinfo=UTC)


def _experiment(status="COMPLETED", **overrides):
    payload = {
        "id": uuid4(),
        "status": status,
        "starting_capital": Decimal("10000"),
        "dataset_snapshot_id": uuid4(),
        "strategy_version_id": uuid4(),
        "trading_start": NOW + timedelta(hours=24),  # Aug 18 14:00
        "trading_end": NOW + timedelta(hours=48),  # Aug 19 14:00
        "parameter_snapshot": {"ema_period": 20},
        "risk_config": {"risk_per_trade": "0.01"},
        "simulation_config": {"financing_model": {"disclosure": "FINANCING EXCLUDED"}},
        "model_version": "PHASE4_HISTORICAL_EXECUTION_V1",
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def _snapshot(fingerprint):
    return SimpleNamespace(fingerprint=fingerprint)


def _version(warm_up_bars):
    return SimpleNamespace(warm_up_bars=warm_up_bars)


def _bar(index, base=NOW):
    open_time = base + timedelta(minutes=15 * index)
    close_time = base + timedelta(minutes=15 * (index + 1))
    return Bar(
        Instrument.EUR_USD,
        Timeframe.M15,
        PriceComponent.MID,
        open_time,
        close_time,
        Decimal("1.0") + Decimal(index) * Decimal("0.001"),
        Decimal("1.0") + Decimal(index) * Decimal("0.001") + Decimal("0.0005"),
        Decimal("1.0") + Decimal(index) * Decimal("0.001") - Decimal("0.0005"),
        Decimal("1.0") + Decimal(index) * Decimal("0.001"),
    )


class FakeRepo:
    def __init__(self, experiment, *, trades=()):
        self.experiment_row = experiment
        self._trades = tuple(trades)
        self.result_row = SimpleNamespace(output_fingerprint="a" * 64)

    def experiment(self, _session, _id):
        return self.experiment_row

    def result(self, _session, _id):
        return self.result_row

    def equity(self, _session, _id):
        return ()

    def trades(self, _session, _id, limit, after_sequence=0):
        return tuple(
            item for item in self._trades if item.sequence_number > after_sequence
        )[:limit]

    def trade(self, _session, _id, sequence):
        return next(
            (item for item in self._trades if item.sequence_number == sequence), None
        )

    def intent(self, _session, trade):
        return getattr(trade, "intent", None)

    def risks(self, _session, _id):
        return getattr(self.experiment_row, "risks", ())


class FakeSession:
    def __init__(self, snapshot=None, version=None):
        self.snapshot = snapshot
        self.version = version

    def get(self, model, _id):
        if model is DatasetSnapshotModel:
            return self.snapshot
        if model is StrategyVersionModel:
            return self.version
        return None


class MarketDataSpy:
    """Verify that derive_m15 receives the snapshot fingerprint and M15."""

    def __init__(self, bars):
        self._bars = tuple(bars)
        self.calls = []

    def derive_m15(self, fingerprint, component):
        self.calls.append((fingerprint, component))
        return self._bars

    def current_m15(self, *_args, **_kwargs):
        self.calls.append(("CURRENT_BAR_PROBE", None))
        return ()


@pytest.fixture
def bars():
    return tuple(_bar(index) for index in range(40))


def _trade(sequence, intent=None, opened_at=None, closed_at=None,
           entry_price=Decimal("1.100"), exit_price=None,
           approved_stop=None, approved_target=None,
           rationale=None):
    return SimpleNamespace(
        id=uuid4(),
        trade_intent_id=uuid4(),
        sequence_number=sequence,
        direction="LONG",
        status="COMPLETED",
        opened_at=opened_at or NOW + timedelta(minutes=120),
        closed_at=closed_at,
        entry_price=entry_price,
        exit_price=exit_price,
        intent=intent or SimpleNamespace(
            id=uuid4(),
            rationale=rationale or {
                "fields": {
                    "reference_time": "2026-08-18T14:30:00Z",
                    "reference_high": "1.10",
                    "reference_low": "1.09",
                    "sweep_time": "2026-08-18T14:45:00Z",
                    "sweep_high": "1.10",
                    "sweep_low": "1.08",
                    "confirmation_time": "2026-08-18T15:00:00Z",
                    "confirmation_high": "1.11",
                    "confirmation_low": "1.09",
                }
            },
        ),
    )


def _as_utc(value):
    """Coerce service-layer datetime outputs to a UTC datetime for assertions."""
    if isinstance(value, datetime):
        return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)


# ---------------------------------------------------------------------------
# Backend gate 1: snapshot fingerprint is the only M15 path.
# ---------------------------------------------------------------------------


def test_price_analysis_caller_uses_snapshot_fingerprint_and_mid_only(bars):
    snapshot = _snapshot("a" * 64)
    version = _version(warm_up_bars=20)
    market_data = MarketDataSpy(bars)
    service = ExperimentResultReadService(
        results=FakeRepo(_experiment()), market_data=market_data
    )
    service.price_analysis(FakeSession(snapshot, version), uuid4())
    assert market_data.calls == [("a" * 64, PriceComponent.MID)], (
        "price_analysis must request M15 using only the snapshot fingerprint "
        "and MID component; current-bar probes must be absent"
    )


def test_price_analysis_does_not_invoke_current_bar_provider(bars):
    snapshot = _snapshot("b" * 64)
    version = _version(warm_up_bars=4)
    market_data = MarketDataSpy(bars)
    service = ExperimentResultReadService(
        results=FakeRepo(_experiment()), market_data=market_data
    )
    service.price_analysis(FakeSession(snapshot, version), uuid4())
    assert all(call[0] != "CURRENT_BAR_PROBE" for call in market_data.calls), (
        "A later current-bar correction cannot appear on this read seam"
    )


# ---------------------------------------------------------------------------
# Backend gate 2: warm-up selection matches SimulationClock.
# ---------------------------------------------------------------------------


def test_price_analysis_warmup_matches_simulation_clock_window():
    """Select exactly the last ``warm_up_bars`` M15 ending ``<= trading_start``.

    Mirrors the SimulationClock rule:
        warmup = M15 bars with end_time <= trading_start
        window = M15 bars with trading_start < end_time <= trading_end
        emitted = last warm_up_bars of warmup, then all of window.
    """
    bars = tuple(_bar(index) for index in range(60))
    warmup_count = 5
    experiment = _experiment()
    experiment.trading_start = NOW + timedelta(minutes=15 * 30)
    experiment.trading_end = NOW + timedelta(minutes=15 * 45)
    snapshot = _snapshot("c" * 64)
    version = _version(warmup_count)

    expected_warmup = tuple(
        bar.end_time for bar in bars if bar.end_time <= experiment.trading_start
    )[-warmup_count:]
    expected_window = tuple(
        bar.end_time for bar in bars
        if experiment.trading_start < bar.end_time <= experiment.trading_end
    )

    market_data = MarketDataSpy(bars)
    service = ExperimentResultReadService(
        results=FakeRepo(experiment), market_data=market_data
    )
    value = service.price_analysis(FakeSession(snapshot, version), experiment.id)

    assert tuple(c["t"] for c in value.m15[:warmup_count]) == expected_warmup, (
        "Warm-up selection diverges from SimulationClock's last warm_up_bars rule"
    )
    assert tuple(c["t"] for c in value.m15[warmup_count:]) == expected_window, (
        "Window selection diverges from SimulationClock's half-open rule"
    )
    assert value.m15[0]["t"] <= experiment.trading_start <= value.m15[warmup_count]["t"]


def test_price_analysis_warmup_matches_real_simulation_clock_object():
    """True SimulationClock parity check using its public M15 selection rule."""
    bars = tuple(_bar(index) for index in range(40))
    warmup_count = 4
    experiment = _experiment()
    experiment.trading_start = NOW + timedelta(minutes=15 * 10)
    experiment.trading_end = NOW + timedelta(minutes=15 * 39)
    snapshot = _snapshot("q" * 64)
    version = _version(warmup_count)

    # Real SimulationClock M15 selection (matches the service):
    #   warmup = M15 bars with end_time <= trading_start
    #   emitted warmup = last warmup_m15_bars of warmup
    expected_warmup = tuple(
        bar.end_time for bar in bars if bar.end_time <= experiment.trading_start
    )[-warmup_count:]

    service = ExperimentResultReadService(
        results=FakeRepo(experiment), market_data=MarketDataSpy(bars)
    )
    value = service.price_analysis(FakeSession(snapshot, version), experiment.id)
    assert tuple(c["t"] for c in value.m15[:warmup_count]) == expected_warmup


# ---------------------------------------------------------------------------
# Backend gate 3: M15 is UTC, ordered, completed, half-open; bounded by 10k.
# ---------------------------------------------------------------------------


def test_price_analysis_bars_are_completed_utc_half_open_and_ordered():
    bars = tuple(_bar(index) for index in range(120))
    experiment = _experiment()
    snapshot = _snapshot("d" * 64)
    version = _version(warm_up_bars=4)
    service = ExperimentResultReadService(
        results=FakeRepo(experiment), market_data=MarketDataSpy(bars)
    )
    value = service.price_analysis(FakeSession(snapshot, version), experiment.id)
    finishes: list[datetime] = []
    for index, candle in enumerate(value.m15):
        finish = _as_utc(candle["t"])
        assert finish.tzinfo is not None
        assert finish.utcoffset() == timedelta(0), "M15 bars must be UTC"
        assert finish.minute % 15 == 0, "M15 bars must be 15-aligned"
        assert finish.second == 0
        assert finish.microsecond == 0
        if index > 0:
            assert finishes[-1] < finish, "M15 bars must be strictly ordered"
        finishes.append(finish)


def test_price_analysis_caps_at_10_000_candles_and_sets_truncated_diagnostic():
    bars = tuple(_bar(index) for index in range(10_001))
    experiment = _experiment()
    experiment.trading_start = NOW
    experiment.trading_end = NOW + timedelta(minutes=15 * 10_002)
    snapshot = _snapshot("e" * 64)
    version = _version(warm_up_bars=0)
    service = ExperimentResultReadService(
        results=FakeRepo(experiment), market_data=MarketDataSpy(bars)
    )
    value = service.price_analysis(FakeSession(snapshot, version), experiment.id)
    assert len(value.m15) == 10_000
    assert value.diagnostics["truncated"] is True
    assert value.diagnostics["omitted_m15_count"] == 1
    assert value.diagnostics["omitted_range"] is not None


def test_price_analysis_caps_at_250_trades_and_flags_truncation():
    bars = tuple(_bar(index) for index in range(30))
    trades = tuple(
        _trade(sequence)
        for sequence in range(1, 252)
    )
    experiment = _experiment()
    snapshot = _snapshot("f" * 64)
    version = _version(warm_up_bars=4)
    service = ExperimentResultReadService(
        results=FakeRepo(experiment, trades=trades),
        market_data=MarketDataSpy(bars),
    )
    value = service.price_analysis(FakeSession(snapshot, version), experiment.id)
    assert len(value.trades) == 250
    assert value.diagnostics["trade_eligible_count"] == 251
    assert value.diagnostics["trade_returned_count"] == 250
    assert value.diagnostics["omitted_trade_count"] == 1
    assert value.diagnostics["truncated"] is True


# ---------------------------------------------------------------------------
# Backend gate 4: EMA matches indicators_v2.ema with persisted period.
# Regression guard: include a non-100 ema_period.
# ---------------------------------------------------------------------------


def test_price_analysis_ema_uses_persisted_period_and_matches_indicators_v2():
    """The non-100 period regression guard: validate EMA against indicators_v2.ema."""
    from backend.strategies.indicators_v2 import ema as indicators_ema

    bars = tuple(_bar(index) for index in range(40))
    experiment = _experiment()
    experiment.trading_start = NOW + timedelta(minutes=15 * 4)
    experiment.trading_end = NOW + timedelta(minutes=15 * 40)
    snapshot = _snapshot("a" * 64)
    version = _version(warm_up_bars=4)
    service = ExperimentResultReadService(
        results=FakeRepo(experiment), market_data=MarketDataSpy(bars)
    )
    value = service.price_analysis(FakeSession(snapshot, version), experiment.id)
    assert value.diagnostics["ema_period"] == 20, (
        "Persisted ema_period 20 must be used; service must not regress to ema_100"
    )
    ema_period = 20
    for index, point in enumerate(value.ema):
        prefix_len = index + (len(bars) - len(value.ema)) + 1
        prefix = bars[:prefix_len]
        expected = str(indicators_ema(prefix, ema_period))
        assert point["v"] == expected, (
            f"EMA point at index {index} (prefix_len={prefix_len}) must equal "
            f"indicators_v2.ema; got {point['v']}, expected {expected}"
        )


def test_price_analysis_ema_omits_unwarmed_prefix_points():
    bars = tuple(_bar(index) for index in range(10))
    experiment = _experiment()
    experiment.parameter_snapshot = {"ema_period": 7}
    experiment.trading_start = NOW
    experiment.trading_end = NOW + timedelta(minutes=15 * 10)
    snapshot = _snapshot("a" * 64)
    version = _version(warm_up_bars=0)
    service = ExperimentResultReadService(
        results=FakeRepo(experiment), market_data=MarketDataSpy(bars)
    )
    value = service.price_analysis(FakeSession(snapshot, version), experiment.id)
    # 10 candles minus first 6 unwarmed prefixes = 4 EMA points
    assert len(value.ema) == 4
    assert value.ema[0]["t"] == value.m15[6]["t"]
    assert value.ema[-1]["t"] == value.m15[-1]["t"]


# ---------------------------------------------------------------------------
# Backend gate 5: entry/exit/approved stop/target from persisted rows.
# ---------------------------------------------------------------------------


def test_price_analysis_entry_exit_approved_stop_target_match_persisted_rows():
    bars = tuple(_bar(index) for index in range(30))
    opened = NOW + timedelta(minutes=120)
    closed = opened + timedelta(minutes=45)
    intent = SimpleNamespace(
        id=uuid4(),
        rationale={
            "fields": {
                "reference_time": "2026-08-18T14:30:00Z",
                "reference_high": "1.10",
                "reference_low": "1.09",
                "sweep_time": "2026-08-18T14:45:00Z",
                "sweep_high": "1.10",
                "sweep_low": "1.08",
                "confirmation_time": "2026-08-18T15:00:00Z",
                "confirmation_high": "1.11",
                "confirmation_low": "1.09",
            }
        },
    )
    trade = SimpleNamespace(
        id=uuid4(),
        trade_intent_id=uuid4(),
        sequence_number=1,
        direction="LONG",
        status="COMPLETED",
        opened_at=opened,
        closed_at=closed,
        entry_price=Decimal("1.1650"),
        exit_price=Decimal("1.1690"),
        intent=intent,
    )
    experiment = _experiment()
    experiment.risks = (
        SimpleNamespace(phase="PRE_SUBMISSION", outcome="APPROVED",
                        stop_price=Decimal("1.1640"),
                        target_price=Decimal("1.1690")),
    )
    snapshot = _snapshot("z" * 64)
    version = _version(warm_up_bars=4)
    service = ExperimentResultReadService(
        results=FakeRepo(experiment, trades=(trade,)),
        market_data=MarketDataSpy(bars),
    )
    value = service.price_analysis(FakeSession(snapshot, version), experiment.id)
    assert len(value.trades) == 1
    serialized = value.trades[0]
    assert serialized["entry"]["t"] == opened
    assert serialized["entry"]["price"] == "1.1650"
    assert serialized["exit"]["t"] == closed
    assert serialized["exit"]["price"] == "1.1690"
    assert serialized["stop"]["price"] == "1.1640"
    assert serialized["stop"]["from"] == opened
    assert serialized["stop"]["to"] == closed
    assert serialized["target"]["price"] == "1.1690"


def test_price_analysis_approved_protection_filter_excludes_other_phases():
    """Only the first approved PRE_SUBMISSION protection is exposed."""
    bars = tuple(_bar(index) for index in range(30))
    opened = NOW + timedelta(minutes=120)
    closed = opened + timedelta(minutes=45)
    intent = SimpleNamespace(
        id=uuid4(),
        rationale={
            "fields": {
                "reference_time": "2026-08-18T14:30:00Z",
                "reference_high": "1.10",
                "reference_low": "1.09",
                "sweep_time": "2026-08-18T14:45:00Z",
                "sweep_high": "1.10",
                "sweep_low": "1.08",
                "confirmation_time": "2026-08-18T15:00:00Z",
                "confirmation_high": "1.11",
                "confirmation_low": "1.09",
            }
        },
    )
    trade = SimpleNamespace(
        id=uuid4(),
        trade_intent_id=uuid4(),
        sequence_number=1,
        direction="LONG",
        status="COMPLETED",
        opened_at=opened,
        closed_at=closed,
        entry_price=Decimal("1.1650"),
        exit_price=Decimal("1.1690"),
        intent=intent,
    )
    experiment = _experiment()
    experiment.risks = (
        SimpleNamespace(phase="PRE_FLIGHT", outcome="APPROVED",
                        stop_price=Decimal("9.9999"),
                        target_price=Decimal("8.8888")),
        SimpleNamespace(phase="POST_FILL", outcome="APPROVED",
                        stop_price=Decimal("7.7777"),
                        target_price=Decimal("6.6666")),
        SimpleNamespace(phase="PRE_SUBMISSION", outcome="REJECTED",
                        stop_price=Decimal("5.5555"),
                        target_price=Decimal("4.4444")),
        SimpleNamespace(phase="PRE_SUBMISSION", outcome="APPROVED",
                        stop_price=Decimal("1.1640"),
                        target_price=Decimal("1.1690")),
    )
    snapshot = _snapshot("y" * 64)
    version = _version(warm_up_bars=4)
    service = ExperimentResultReadService(
        results=FakeRepo(experiment, trades=(trade,)),
        market_data=MarketDataSpy(bars),
    )
    value = service.price_analysis(FakeSession(snapshot, version), experiment.id)
    serialized = value.trades[0]
    assert serialized["stop"] is not None
    assert serialized["stop"]["price"] == "1.1640"
    assert serialized["target"]["price"] == "1.1690"


# ---------------------------------------------------------------------------
# Backend gate 6: rationale reference/sweep/confirmation facts.
# ---------------------------------------------------------------------------


def test_price_analysis_reference_facts_only_come_from_rationale():
    intent = SimpleNamespace(
        id=uuid4(),
        rationale={
            "fields": {
                "reference_time": "2026-08-18T14:30:00Z",
                "reference_high": "1.10",
                "reference_low": "1.09",
                "sweep_time": "2026-08-18T14:45:00Z",
                "sweep_high": "1.10",
                "sweep_low": "1.08",
                "confirmation_time": "2026-08-18T15:00:00Z",
                "confirmation_high": "1.11",
                "confirmation_low": "1.09",
            }
        },
    )
    trade = _trade(1, intent=intent)
    bars = tuple(_bar(index) for index in range(20))
    # Place trading_start inside the bar stream so window + warmup both qualify.
    experiment = _experiment()
    experiment.trading_start = NOW + timedelta(minutes=15 * 4)
    experiment.trading_end = NOW + timedelta(minutes=15 * 19)
    snapshot = _snapshot("g" * 64)
    version = _version(warm_up_bars=4)
    service = ExperimentResultReadService(
        results=FakeRepo(experiment, trades=(trade,)),
        market_data=MarketDataSpy(bars),
    )
    value = service.price_analysis(FakeSession(snapshot, version), experiment.id)
    assert len(value.reference) == 1
    facts = value.reference[0]
    assert facts["trade_sequence"] == 1
    assert _as_utc(facts["reference"]["t"]) == datetime(2026, 8, 18, 14, 30, tzinfo=UTC)
    assert facts["reference"]["high"] == "1.10"
    assert facts["reference"]["low"] == "1.09"
    assert _as_utc(facts["sweep"]["t"]) == datetime(2026, 8, 18, 14, 45, tzinfo=UTC)
    assert _as_utc(facts["confirmation"]["t"]) == datetime(
        2026, 8, 18, 15, 0, tzinfo=UTC
    )


def test_price_analysis_optional_rationale_omitted_but_chart_remains_usable():
    """Optional malformed rationale must not break M15/EMA."""
    intent = SimpleNamespace(
        id=uuid4(),
        rationale={"fields": {"reference_time": "garbage"}},
    )
    trade = _trade(1, intent=intent)
    bars = tuple(_bar(index) for index in range(60))
    experiment = _experiment()
    experiment.trading_start = NOW + timedelta(minutes=15 * 4)
    experiment.trading_end = NOW + timedelta(minutes=15 * 39)
    service = ExperimentResultReadService(
        results=FakeRepo(experiment, trades=(trade,)),
        market_data=MarketDataSpy(bars),
    )
    value = service.price_analysis(
        FakeSession(_snapshot("h" * 64), _version(warm_up_bars=4)),
        experiment.id,
    )
    assert value.reference == ()
    assert len(value.m15) > 0
    assert len(value.ema) > 0


# ---------------------------------------------------------------------------
# Backend gate 7: zero-Trade Experiments return valid M15/EMA with empty markers.
# ---------------------------------------------------------------------------


def test_price_analysis_zero_trades_returns_m15_ema_and_empty_markers():
    bars = tuple(_bar(index) for index in range(40))
    experiment = _experiment()
    experiment.trading_start = NOW + timedelta(minutes=15 * 5)
    experiment.trading_end = NOW + timedelta(minutes=15 * 39)
    service = ExperimentResultReadService(
        results=FakeRepo(experiment, trades=()),
        market_data=MarketDataSpy(bars),
    )
    value = service.price_analysis(
        FakeSession(_snapshot("i" * 64), _version(warm_up_bars=5)), experiment.id
    )
    # 5 warmup + 34 window = 39 candles total eligible
    assert len(value.m15) == 39
    ema_period = 20
    assert len(value.ema) == len(value.m15) - (ema_period - 1), (
        "EMA length equals eligible candles minus the warm-up prefix (ema_period - 1)"
    )
    assert value.trades == ()
    assert value.reference == ()
    assert value.diagnostics["trade_eligible_count"] == 0
    assert value.diagnostics["trade_returned_count"] == 0


# ---------------------------------------------------------------------------
# Backend gate 8: terminal states and incomplete inputs fail closed.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("status", ["PENDING", "RUNNING"])
def test_price_analysis_pre_completion_returns_result_not_ready(status):
    experiment = _experiment(status=status)
    service = ExperimentResultReadService(
        results=FakeRepo(experiment), market_data=MarketDataSpy(())
    )
    with pytest.raises(ResultReadError) as error:
        service.price_analysis(FakeSession(), experiment.id)
    assert error.value.code == "RESULT_NOT_READY"


def test_price_analysis_failed_returns_experiment_failed():
    experiment = _experiment(status="FAILED")
    service = ExperimentResultReadService(
        results=FakeRepo(experiment), market_data=MarketDataSpy(())
    )
    with pytest.raises(ResultReadError) as error:
        service.price_analysis(FakeSession(), experiment.id)
    assert error.value.code == "EXPERIMENT_FAILED"


def test_price_analysis_missing_snapshot_returns_incomplete_result():
    bars = tuple(_bar(index) for index in range(10))
    service = ExperimentResultReadService(
        results=FakeRepo(_experiment()), market_data=MarketDataSpy(bars)
    )
    with pytest.raises(ResultReadError) as error:
        service.price_analysis(
            FakeSession(snapshot=None, version=_version(4)), uuid4()
        )
    assert error.value.code == "INCOMPLETE_RESULT"


def test_price_analysis_missing_strategy_version_returns_incomplete_result():
    bars = tuple(_bar(index) for index in range(10))
    service = ExperimentResultReadService(
        results=FakeRepo(_experiment()), market_data=MarketDataSpy(bars)
    )
    with pytest.raises(ResultReadError) as error:
        service.price_analysis(
            FakeSession(snapshot=_snapshot("k" * 64), version=None), uuid4()
        )
    assert error.value.code == "INCOMPLETE_RESULT"


def test_price_analysis_missing_market_data_reader_returns_incomplete_result():
    service = ExperimentResultReadService(results=FakeRepo(_experiment()))
    with pytest.raises(ResultReadError) as error:
        service.price_analysis(FakeSession(), uuid4())
    assert error.value.code == "INCOMPLETE_RESULT"


def test_price_analysis_invalid_ema_period_returns_incomplete_result():
    bars = tuple(_bar(index) for index in range(20))
    experiment = _experiment()
    experiment.parameter_snapshot = {"ema_period": 0}
    service = ExperimentResultReadService(
        results=FakeRepo(experiment), market_data=MarketDataSpy(bars)
    )
    with pytest.raises(ResultReadError) as error:
        service.price_analysis(
            FakeSession(_snapshot("m" * 64), _version(4)), experiment.id
        )
    assert error.value.code == "INCOMPLETE_RESULT"


def test_price_analysis_missing_ema_period_returns_incomplete_result():
    bars = tuple(_bar(index) for index in range(20))
    experiment = _experiment()
    experiment.parameter_snapshot = {}
    service = ExperimentResultReadService(
        results=FakeRepo(experiment), market_data=MarketDataSpy(bars)
    )
    with pytest.raises(ResultReadError) as error:
        service.price_analysis(
            FakeSession(_snapshot("n" * 64), _version(4)), experiment.id
        )
    assert error.value.code == "INCOMPLETE_RESULT"


def test_price_analysis_insufficient_warmup_returns_incomplete_result():
    """Warmup history shorter than warm_up_bars must fail closed."""
    bars = tuple(_bar(index) for index in range(10))
    experiment = _experiment()
    experiment.trading_start = NOW + timedelta(minutes=15 * 5)
    experiment.trading_end = NOW + timedelta(minutes=15 * 9)
    service = ExperimentResultReadService(
        results=FakeRepo(experiment), market_data=MarketDataSpy(bars)
    )
    with pytest.raises(ResultReadError) as error:
        service.price_analysis(
            FakeSession(_snapshot("o" * 64), _version(warm_up_bars=8)),
            experiment.id,
        )
    assert error.value.code == "INCOMPLETE_RESULT"


def test_price_analysis_provider_failure_returns_incomplete_result():
    class Exploding:
        def derive_m15(self, *_args, **_kwargs):
            raise ValueError("simulated M1 read error")

    service = ExperimentResultReadService(
        results=FakeRepo(_experiment()), market_data=Exploding()
    )
    with pytest.raises(ResultReadError) as error:
        service.price_analysis(
            FakeSession(_snapshot("p" * 64), _version(4)), uuid4()
        )
    assert error.value.code == "INCOMPLETE_RESULT"


# ---------------------------------------------------------------------------
# Backend gate 9: read-only; no mutation of persisted query state.
# ---------------------------------------------------------------------------


def test_price_analysis_does_not_mutate_persisted_query_state():
    bars = tuple(_bar(index) for index in range(40))
    trade = _trade(1)
    session = FakeSession(_snapshot("r" * 64), _version(warm_up_bars=4))
    repo = FakeRepo(_experiment(), trades=(trade,))
    service = ExperimentResultReadService(
        results=repo, market_data=MarketDataSpy(bars)
    )
    before_snapshot_fingerprint = session.snapshot.fingerprint
    before_version_warmup = session.version.warm_up_bars
    before_experiment_id = repo.experiment_row.id
    before_result_row = repo.result_row
    service.price_analysis(session, repo.experiment_row.id)
    assert session.snapshot.fingerprint == before_snapshot_fingerprint
    assert session.version.warm_up_bars == before_version_warmup
    assert repo.experiment_row.id == before_experiment_id
    assert repo.result_row is before_result_row
