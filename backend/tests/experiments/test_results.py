from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

import backend.experiments.results as results_module
from backend.api.experiments import _metrics_payload
from backend.domain.market_data import Bar, Instrument, PriceComponent, Timeframe
from backend.experiments.metrics import calculate_metrics
from backend.experiments.results import ExperimentResultReadService, ResultReadError
from backend.persistence.models import DatasetSnapshotModel
from backend.strategies.indicators_v2 import ema

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _experiment(status: str = "COMPLETED") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        status=status,
        starting_capital=Decimal("100"),
        dataset_snapshot_id=uuid4(),
        trading_start=NOW,
        trading_end=NOW + timedelta(days=1),
        parameter_snapshot={"ema_period": 100},
        risk_config={"risk_per_trade": "0.01"},
        simulation_config={"financing_model": {"disclosure": "FINANCING EXCLUDED"}},
        model_version="PHASE4_HISTORICAL_EXECUTION_V1",
    )


class FakeRepo:
    def __init__(self, experiment: SimpleNamespace, *, equity=(), trades=()):
        self._experiment = experiment
        self._equity = tuple(equity)
        self._trades = tuple(trades)
        self.result_row = SimpleNamespace(output_fingerprint="a" * 64)
        self.mutations = 0

    def experiment(self, _session, _id):
        return self._experiment

    def result(self, _session, _id):
        return self.result_row

    def equity(self, _session, _id):
        return self._equity

    def trades(self, _session, _id, _limit, after_sequence=0):
        return tuple(
            item for item in self._trades if item.sequence_number > after_sequence
        )[:_limit]

    def trade(self, _session, _id, sequence):
        return next(
            (item for item in self._trades if item.sequence_number == sequence), None
        )

    def intent(self, _session, trade):
        return getattr(trade, "intent", None)

    def risks(self, _session, _id):
        return tuple(getattr(self._experiment, "risks", ()))

    def orders(self, _session, _experiment_id, _intent_id):
        return tuple(getattr(self._experiment, "orders", ()))

    def events(self, _session, order_id):
        return ((order_id, "ORDER_SUBMITTED"),)

    def fills(self, _session, _ids):
        return (SimpleNamespace(slippage_cost=Decimal("0.02"), fee=Decimal("0.03")),)


class FakeSession:
    def __init__(self, snapshot=None):
        self.snapshot = snapshot

    def get(self, model, _id):
        return self.snapshot


def _trade(sequence: int, *, intent=None) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        sequence_number=sequence,
        direction="LONG",
        status="COMPLETED",
        opened_at=NOW,
        closed_at=NOW + timedelta(minutes=15),
        entry_price=Decimal("1.1"),
        exit_price=Decimal("1.2"),
        exit_reason="TAKE_PROFIT",
        net_pnl=Decimal("10"),
        r_multiple=Decimal("1"),
        intrabar_ambiguous=True,
        ambiguity_policy="STOP_FIRST",
        intent=intent,
    )


@pytest.mark.parametrize("status", ["PENDING", "RUNNING", "FAILED"])
def test_result_subresources_fail_closed_before_completion(status: str) -> None:
    experiment = _experiment(status)
    service = ExperimentResultReadService(results=FakeRepo(experiment))
    expected = "EXPERIMENT_FAILED" if status == "FAILED" else "RESULT_NOT_READY"
    for read in (
        lambda: service.equity(None, experiment.id),
        lambda: service.trades(None, experiment.id),
        lambda: service.trade(None, experiment.id, 1),
    ):
        with pytest.raises(ResultReadError) as error:
            read()
        assert error.value.code == expected


def test_zero_trade_detail_derives_unavailable_states_without_mutation() -> None:
    experiment = _experiment()
    legacy = SimpleNamespace(metric_schema_version="LEGACY_UNCOMPUTED")
    repo = FakeRepo(experiment, equity=())
    repo.result_row = legacy
    service = ExperimentResultReadService(results=repo)

    detail = service.detail(None, experiment.id)
    metrics = detail["metrics"]
    assert metrics.trade_count == 0
    assert metrics.profit_factor.reason == "ZERO_TRADES"
    assert metrics.win_rate.reason == "ZERO_TRADES"
    assert metrics.expectancy_net_pnl.reason == "ZERO_TRADES"
    assert legacy.metric_schema_version == "LEGACY_UNCOMPUTED"
    assert repo.mutations == 0


def test_list_metric_payload_preserves_unavailable_infinite_and_zero_trade_states(
) -> None:
    point = SimpleNamespace(observed_at=NOW, equity=Decimal("100"))
    winning_trade = _trade(1)
    infinite = _metrics_payload(
        calculate_metrics((winning_trade,), (point,), starting_equity=Decimal("100"))
    )
    assert infinite is not None
    assert infinite["profitFactor"]["state"] == "INFINITE"
    assert infinite["profitFactor"]["value"] is None
    assert infinite["tradeCount"]["value"] == "1"

    zero_trade = _metrics_payload(
        calculate_metrics((), (), starting_equity=Decimal("100"))
    )
    assert zero_trade is not None
    assert zero_trade["netReturn"]["state"] == "UNAVAILABLE"
    assert zero_trade["sharpe"]["state"] == "UNAVAILABLE"
    assert zero_trade["profitFactor"]["reason"] == "ZERO_TRADES"
    assert zero_trade["tradeCount"]["value"] == "0"


def test_equity_envelope_is_bounded_and_preserves_source_and_edges() -> None:
    experiment = _experiment()
    rows = tuple(
        SimpleNamespace(
            sequence_number=index + 1,
            observed_at=NOW + timedelta(minutes=index),
            equity=Decimal(index),
            drawdown_amount=Decimal(index % 11),
            drawdown_percent=Decimal("0.1"),
            valuation_bid=None,
            valuation_ask=None,
        )
        for index in range(2001)
    )
    service = ExperimentResultReadService(results=FakeRepo(experiment, equity=rows))
    equity = service.equity(None, experiment.id)
    assert equity.sampling_policy == "EQUITY_ENVELOPE_V1"
    assert equity.source_count == 2001
    assert len(equity.points) <= 6000
    assert equity.points[0]["sequence"] == 1
    assert equity.points[-1]["sequence"] == 2001


def test_trade_pagination_and_detail_compose_lineage_and_approved_protection() -> None:
    experiment = _experiment()
    intent = SimpleNamespace(id=uuid4(), rationale={"reason_code": "SETUP"})
    trade = _trade(2, intent=intent)
    experiment.risks = (
        SimpleNamespace(phase="PRE_FLIGHT", outcome="APPROVED"),
        SimpleNamespace(
            phase="PRE_SUBMISSION",
            outcome="APPROVED",
            stop_price=Decimal("1.09"),
            target_price=Decimal("1.12"),
        ),
    )
    order = SimpleNamespace(id=uuid4(), purpose="ENTRY")
    experiment.orders = (order,)
    repo = FakeRepo(
        experiment, trades=(_trade(1, intent=intent), trade, _trade(3, intent=intent))
    )
    service = ExperimentResultReadService(results=repo)
    service._chart = lambda *_args: None
    page = service.trades(None, experiment.id, limit=1, after_sequence=1)
    assert [item["sequence_number"] for item in page] == [2]
    assert page[0]["label"] == "Trade 2"
    detail = service.trade(None, experiment.id, 2)
    assert detail["initial_stop"] == Decimal("1.09")
    assert detail["target"] == Decimal("1.12")
    assert detail["rationale"]["reason_code"] == "SETUP"
    assert detail["risks"] == experiment.risks
    assert detail["orders"][0][0] is order
    assert detail["fills"]
    assert detail["summary"]["ambiguous"] is True
    assert detail["financing_disclosure"] == "FINANCING EXCLUDED"


def test_chart_uses_snapshot_membership_ema_annotations_and_omitted_range(
    monkeypatch,
) -> None:
    experiment = _experiment()
    intent = SimpleNamespace(
        id=uuid4(),
        rationale={
            "fields": {
                f"marker_{index}_time": (
                    NOW + timedelta(minutes=15 * index * 20)
                ).isoformat()
                for index in range(30)
            },
        },
    )
    trade = _trade(1, intent=intent)
    experiment.risks = ()
    snapshot = SimpleNamespace(
        coverage_start=NOW, coverage_end=NOW + timedelta(days=20)
    )
    m15 = tuple(
        Bar(
            Instrument.EUR_USD,
            Timeframe.M15,
            PriceComponent.MID,
            NOW + timedelta(minutes=15 * index),
            NOW + timedelta(minutes=15 * (index + 1)),
            Decimal("1.1"),
            Decimal("1.11"),
            Decimal("1.09"),
            Decimal("1.1"),
        )
        for index in range(700)
    )
    calls = []

    class Snapshots:
        def ordered_members_with_sources(self, *_args):
            calls.append("snapshot")
            return (SimpleNamespace(bar=m15[0]),)

    monkeypatch.setattr(results_module, "aggregate_m1_to_m15", lambda *_args: m15)
    monkeypatch.setattr(
        results_module,
        "ema_100",
        lambda bars: Decimal("1.1000") if len(bars) >= 100 else None,
    )
    service = ExperimentResultReadService(
        results=FakeRepo(experiment, trades=(trade,)), snapshots=Snapshots()
    )
    chart = service._chart(FakeSession(snapshot), experiment, trade, intent)
    assert calls == ["snapshot"]
    assert len(chart.candles) <= 500
    assert any(candle["ema"] == "1.1000" for candle in chart.candles)
    assert chart.omitted_range is not None
    assert [item["kind"] for item in chart.annotations].count("strategy_marker") == 30
    assert {item["kind"] for item in chart.annotations} >= {"entry", "exit"}


def test_trade_detail_missing_intent_fails_closed() -> None:
    experiment = _experiment()
    service = ExperimentResultReadService(
        results=FakeRepo(experiment, trades=(_trade(1),))
    )
    with pytest.raises(ResultReadError) as error:
        service.trade(None, experiment.id, 1)
    assert error.value.code == "INCOMPLETE_RESULT"


def test_price_analysis_uses_persisted_period_and_keeps_zero_trade_context() -> None:
    experiment = _experiment()
    experiment.parameter_snapshot = {"ema_period": 3}
    experiment.strategy_version_id = uuid4()
    snapshot = SimpleNamespace(fingerprint="f" * 64)
    version = SimpleNamespace(required_historical_context_bars=2)
    bars = tuple(
        Bar(
            Instrument.EUR_USD,
            Timeframe.M15,
            PriceComponent.MID,
            NOW + timedelta(minutes=15 * index),
            NOW + timedelta(minutes=15 * (index + 1)),
            Decimal("1.0") + index,
            Decimal("1.1") + index,
            Decimal("0.9") + index,
            Decimal("1.0") + index,
        )
        for index in range(4)
    )

    class Session:
        def get(self, model, _id):
            return snapshot if model is DatasetSnapshotModel else version

    class MarketData:
        def derive_m15(self, fingerprint, component):
            assert fingerprint == snapshot.fingerprint
            assert component is PriceComponent.MID
            return bars

    experiment.trading_start = NOW + timedelta(minutes=30)
    experiment.trading_end = NOW + timedelta(minutes=60)
    service = ExperimentResultReadService(
        results=FakeRepo(experiment), market_data=MarketData()
    )
    value = service.price_analysis(Session(), experiment.id)
    assert len(value.m15) == 4
    assert len(value.ema) == 2
    expected = ema(bars[:3], 3)
    assert value.ema[0]["v"] == str(expected)
    assert value.trades == ()
    assert value.reference == ()


def test_price_analysis_reports_candle_truncation_without_sampling() -> None:
    experiment = _experiment()
    experiment.parameter_snapshot = {"ema_period": 2}
    experiment.strategy_version_id = uuid4()
    experiment.trading_start = NOW
    experiment.trading_end = NOW + timedelta(minutes=15 * 10001)
    snapshot = SimpleNamespace(fingerprint="f" * 64)
    version = SimpleNamespace(required_historical_context_bars=0)
    bars = tuple(
        Bar(
            Instrument.EUR_USD,
            Timeframe.M15,
            PriceComponent.MID,
            NOW + timedelta(minutes=15 * index),
            NOW + timedelta(minutes=15 * (index + 1)),
            Decimal("1.0"), Decimal("1.1"), Decimal("0.9"), Decimal("1.0"),
        )
        for index in range(10001)
    )

    class Session:
        def get(self, model, _id):
            return snapshot if model is DatasetSnapshotModel else version

    class MarketData:
        def derive_m15(self, _fingerprint, _component):
            return bars

    value = ExperimentResultReadService(
        results=FakeRepo(experiment), market_data=MarketData()
    ).price_analysis(Session(), experiment.id)
    assert len(value.m15) == 10000
    assert value.diagnostics["truncated"] is True
    assert value.diagnostics["omitted_m15_count"] == 1
