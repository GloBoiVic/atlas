from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.experiments.comparison import (
    ComparisonReadError,
    ExperimentComparisonReadService,
)
from backend.experiments.metrics import calculate_metrics
from backend.persistence.models import (
    DatasetSnapshotModel,
    InstrumentModel,
    StrategyVersionModel,
    VenueInstrumentModel,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _fixture(status="COMPLETED", **changes):
    experiment = SimpleNamespace(
        id=uuid4(),
        status=status,
        strategy_version_id=uuid4(),
        venue_instrument_id=uuid4(),
        dataset_snapshot_id=uuid4(),
        trading_start=NOW,
        trading_end=NOW + timedelta(days=1),
        starting_capital=Decimal("100"),
        risk_per_trade=Decimal("0.01"),
        parameter_snapshot={"ema_period": 100, "stop_buffer": "0.5"},
        risk_config={"risk_per_trade": "0.01"},
        simulation_config={"execution": "M1"},
        model_version="MODEL_V1",
        created_at=NOW,
    )
    for key, value in changes.items():
        setattr(experiment, key, value)
    version = SimpleNamespace(
        id=experiment.strategy_version_id,
        version_number=2,
        implementation_key="ema_sweep_engulfing.v2",
        source_fingerprint="a" * 64,
        parameter_schema=[
            {"key": "ema_period", "type": "integer"},
            {"key": "stop_buffer", "type": "decimal"},
        ],
        strategy=SimpleNamespace(
            strategy_key="ema_sweep_engulfing", name="EMA Sweep Engulfing"
        ),
    )
    venue = SimpleNamespace(id=experiment.venue_instrument_id, instrument_id=uuid4())
    instrument = SimpleNamespace(id=venue.instrument_id, code="EUR/USD")
    snapshot = SimpleNamespace(id=experiment.dataset_snapshot_id, fingerprint="b" * 64)
    result = SimpleNamespace(
        result_schema_version="RESULT_V1", metric_schema_version="METRICS_V1"
    )
    metrics = calculate_metrics((), (), starting_equity=Decimal("100"))
    return (
        experiment,
        {
            StrategyVersionModel: version,
            VenueInstrumentModel: venue,
            InstrumentModel: instrument,
            DatasetSnapshotModel: snapshot,
        },
        result,
        metrics,
    )


class Repo:
    def __init__(self, fixtures):
        self.fixtures = {item[0].id: item for item in fixtures}

    def experiment(self, _session, experiment_id):
        return self.fixtures.get(experiment_id, (None,))[0]


class Session:
    def __init__(self, fixtures):
        self.rows = {item[0].id: item for item in fixtures}

    def get(self, model, identifier):
        for _experiment, rows, *_ in self.rows.values():
            if model in rows and getattr(rows[model], "id", None) == identifier:
                return rows[model]
            if (
                model is InstrumentModel
                and rows.get(VenueInstrumentModel)
                and identifier == rows[VenueInstrumentModel].instrument_id
            ):
                return rows[InstrumentModel]
        return None


class ResultService:
    def __init__(self, fixtures):
        self.fixtures = {item[0].id: item for item in fixtures}

    def detail(self, _session, identifier):
        _, _, result, metrics = self.fixtures[identifier]
        return {"result": result, "metrics": metrics}


class PersistedResultService(ResultService):
    def detail(self, _session, identifier):
        _, _, result, _metrics = self.fixtures[identifier]
        return {
            "result": result,
            "metrics": {
                "netReturn": {"state": "VALUE", "value": "0.25", "unit": "ratio", "reason": None},
                "maxDrawdownAmount": {"state": "VALUE", "value": "-5", "unit": "USD", "reason": None},
                "maxDrawdownPercent": {"state": "VALUE", "value": "0.05", "unit": "ratio", "reason": None},
                "sharpe": {"state": "UNAVAILABLE", "value": None, "unit": "ratio", "reason": "ZERO_VARIANCE"},
                "profitFactor": {"state": "INFINITE", "value": None, "unit": "ratio", "reason": "NO_LOSSES"},
                "winRate": {"state": "VALUE", "value": "1", "unit": "ratio", "reason": None},
                "expectancy": {"state": "VALUE", "value": "25", "unit": "USD", "reason": None},
                "tradeCount": {"state": "VALUE", "value": "1", "unit": "trades", "reason": None},
            },
        }


def service(fixtures):
    return ExperimentComparisonReadService(
        results=Repo(fixtures), result_service=ResultService(fixtures)
    )


def test_completed_comparison_preserves_persisted_metric_projection():
    first = _fixture()
    second = _fixture()
    for model in (StrategyVersionModel, VenueInstrumentModel, InstrumentModel, DatasetSnapshotModel):
        second[1][model] = first[1][model]
    second[0].strategy_version_id = first[0].strategy_version_id
    second[0].venue_instrument_id = first[0].venue_instrument_id
    second[0].dataset_snapshot_id = first[0].dataset_snapshot_id
    value = ExperimentComparisonReadService(
        results=Repo((first, second)),
        result_service=PersistedResultService((first, second)),
    ).compare(Session((first, second)), (first[0].id, second[0].id))
    assert value["experiments"][0]["metrics"]["netReturn"]["value"] == "0.25"
    assert value["experiments"][0]["metrics"]["sharpe"]["reason"] == "ZERO_VARIANCE"


def test_comparison_preserves_order_and_typed_decimal_equality():
    first = _fixture()
    second = _fixture(parameter_snapshot={"ema_period": 100, "stop_buffer": "0.50"})
    # The fixtures intentionally represent the same canonical Instrument and version.
    second[1][StrategyVersionModel] = first[1][StrategyVersionModel]
    second[1][VenueInstrumentModel] = first[1][VenueInstrumentModel]
    second[1][InstrumentModel] = first[1][InstrumentModel]
    second[1][DatasetSnapshotModel] = first[1][DatasetSnapshotModel]
    second[0].strategy_version_id = first[0].strategy_version_id
    second[0].venue_instrument_id = first[0].venue_instrument_id
    second[0].dataset_snapshot_id = first[0].dataset_snapshot_id
    value = service((first, second)).compare(
        Session((first, second)), (second[0].id, first[0].id)
    )
    assert [item["slot"] for item in value["experiments"]] == ["A", "B"]
    assert value["changedParameterKeys"] == ()
    assert value["warnings"] == ()


def test_comparison_warning_precedence_and_single_parameter_isolation():
    first = _fixture()
    second = _fixture(parameter_snapshot={"ema_period": 101, "stop_buffer": "0.5"})
    second[1][StrategyVersionModel] = first[1][StrategyVersionModel]
    second[1][VenueInstrumentModel] = first[1][VenueInstrumentModel]
    second[1][InstrumentModel] = first[1][InstrumentModel]
    second[1][DatasetSnapshotModel] = first[1][DatasetSnapshotModel]
    second[0].strategy_version_id = first[0].strategy_version_id
    second[0].venue_instrument_id = first[0].venue_instrument_id
    second[0].dataset_snapshot_id = first[0].dataset_snapshot_id
    value = service((first, second)).compare(
        Session((first, second)), (first[0].id, second[0].id)
    )
    assert value["strongParameterIsolation"] is True
    assert value["changedParameterKeys"] == ("ema_period",)


@pytest.mark.parametrize(
    "ids, code",
    [
        ((uuid4(),), "COMPARISON_SELECTION_INVALID"),
        (
            (uuid4(), uuid4(), uuid4(), uuid4(), uuid4()),
            "COMPARISON_SELECTION_INVALID",
        ),
    ],
)
def test_selection_is_bounded(ids, code):
    with pytest.raises(ComparisonReadError) as error:
        service(()).compare(Session(()), ids)
    assert error.value.code == code


def test_non_completed_and_missing_are_rejected_whole_request():
    pending = _fixture("PENDING")
    with pytest.raises(ComparisonReadError, match="COMPLETED") as error:
        service((pending,)).compare(Session((pending,)), (pending[0].id, uuid4()))
    assert error.value.code == "EXPERIMENT_NOT_COMPLETED"
