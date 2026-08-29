"""HTTP contract regression for the durable RUNNING claim."""

import os
from datetime import UTC, timedelta
from threading import Thread

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session

from backend.api.app import create_app
from backend.api.schemas import ExperimentDatasetSnapshotOptionResponse
from backend.experiments.runner import ExperimentRunner
from backend.persistence.database import configure_utc_session_timezone
from backend.persistence.experiment_repository import ExperimentRepository
from backend.persistence.models import (
    ExperimentEquityPointModel,
    ExperimentModel,
    ExperimentResultModel,
    StrategyVersionModel,
)
from backend.persistence.strategy_repository import version_to_domain
from backend.tests.integration.test_experiment_lifecycle import (
    GatedRunner,
    _create,
)
from backend.tests.integration.test_golden_flows import (
    PARAMETERS,
    START,
    _registry,
    _seed,
)

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def database_url():
    return os.environ["ATLAS_TEST_DATABASE_URL"]


def _complete_experiment(database_url, *, direction):
    """Persist a golden-flow Experiment, run it COMPLETED, and return its id."""
    engine = configure_utc_session_timezone(create_engine(database_url))
    try:
        with Session(engine) as session, session.begin():
            session.execute(
                __import__("sqlalchemy").text(
                    "TRUNCATE experiments, dataset_snapshots, market_bars, "
                    "strategy_versions, strategies, venue_instruments, "
                    "instruments CASCADE"
                )
            )
            experiment_id, _, _ = _seed(session, direction)
        with Session(engine) as session, session.begin():
            result = ExperimentRunner(
                strategy_registry=_registry()
            ).run(session, experiment_id)
            assert result.status == "COMPLETED", result.failure
        return experiment_id
    finally:
        engine.dispose()


def test_dataset_snapshot_option_accepts_v1_and_v2_schema_aliases():
    base = {
        "id": "00000000-0000-0000-0000-000000000001",
        "fingerprint": "a" * 64,
        "coverageStart": "2026-01-01T00:00:00Z",
        "coverageEnd": "2026-01-02T00:00:00Z",
        "integrity": {},
    }
    for schema in ("ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2",):
        value = ExperimentDatasetSnapshotOptionResponse.model_validate(
            {**base, "snapshotSchema": schema}
        )
        assert value.snapshot_schema == schema
        assert value.model_dump(by_alias=True)["snapshotSchema"] == schema


def test_configuration_options_preserve_strategy_version_market_requirements(
    database_url,
):
    engine = configure_utc_session_timezone(create_engine(database_url))
    try:
        experiment_id = _complete_experiment(database_url, direction="LONG")
        with Session(engine) as session:
            experiment = session.get(ExperimentModel, experiment_id)
            assert experiment is not None
            version_id = experiment.strategy_version_id
        app = create_app(engine=engine, registry=_registry())
        with TestClient(app) as client:
            response = client.get("/api/v1/experiments/configuration-options")
            assert response.status_code == 200, response.text
            selected = next(
                item
                for item in response.json()["strategyVersions"]
                if item["id"] == str(version_id)
            )
            assert selected["marketRequirements"] == {
                "instrument": "EUR/USD",
                "resolution": "15m",
                "priceComponent": "MID",
                "requiredHistoricalContextBars": 100,
                "completedOnly": True,
            }
    finally:
        engine.dispose()


def test_http_status_poll_observes_running_while_run_is_gated(database_url):
    engine = configure_utc_session_timezone(create_engine(database_url))
    experiment_id = _create(engine)
    runner = GatedRunner()
    app = create_app(engine=engine, registry=_registry(), runner=runner)
    with TestClient(app) as client:
        responses = []
        thread = Thread(
            target=lambda: responses.append(
                client.post(f"/api/v1/experiments/{experiment_id}/run")
            )
        )
        thread.start()
        assert runner.entered.wait(timeout=10)
        observed = client.get(f"/api/v1/experiments/{experiment_id}")
        assert observed.status_code == 200
        assert observed.json()["status"] == "RUNNING"
        runner.release.set()
        thread.join(timeout=10)
        assert responses[0].status_code == 200
    engine.dispose()


def test_create_and_read_contract_timestamps_are_utc_z(database_url):
    engine = configure_utc_session_timezone(create_engine(database_url))
    # This API contract request spans a full hour.  Keep its V2 fixture honest:
    # execution membership must contain both native M1 quote components for
    # every minute in the requested range, rather than the sparse trading
    # fixture used by the execution-behavior tests.
    with Session(engine) as session:
        experiment_id, _, _ = _seed(session, "LONG", complete_execution=True)
        session.commit()
    with Session(engine) as session:
        source = session.get(ExperimentModel, experiment_id)
        assert source is not None
        version_id = source.strategy_version_id
        snapshot_id = source.dataset_snapshot_id
        strategy = session.get(StrategyVersionModel, source.strategy_version_id)
        assert strategy is not None
        _ = strategy.strategy.strategy_key
        naive_created_at = strategy.created_at.replace(tzinfo=None)
        strategy.created_at = naive_created_at
        with session.no_autoflush:
            assert version_to_domain(strategy).created_at.tzinfo == UTC
    app = create_app(engine=engine, registry=_registry(), runner=GatedRunner())
    body = {
        "strategyVersionId": str(version_id),
        "datasetSnapshotId": str(snapshot_id),
        "tradingStart": (START + timedelta(minutes=1500))
        .isoformat()
        .replace("+00:00", "Z"),
        "tradingEnd": (START + timedelta(minutes=1560))
        .isoformat()
        .replace("+00:00", "Z"),
        "startingCapital": "10000",
        "riskPerTrade": "0.01",
        "parameters": PARAMETERS,
        "slippageTicks": 0,
        "commissionPerUnit": "0",
    }
    with TestClient(app) as client:
        created = client.post("/api/v1/experiments", json=body)
        assert created.status_code == 201
        payload = created.json()
        assert payload["status"] == "PENDING"
        assert payload["createdAt"].endswith("Z")
        assert payload["tradingStart"].endswith("Z")
        assert payload["tradingEnd"].endswith("Z")
        detail = client.get(f"/api/v1/experiments/{payload['id']}")
        assert detail.status_code == 200
        assert detail.json()["provenance"]["requestedPeriod"]["start"].endswith("Z")
        listing = client.get("/api/v1/experiments?limit=100")
        assert listing.status_code == 200
        assert all(item["createdAt"].endswith("Z") for item in listing.json()["items"])
    engine.dispose()


def test_experiment_cursor_is_keyset_stable_and_bounded(database_url):
    engine = configure_utc_session_timezone(create_engine(database_url))
    ids = _create(engine, count=3)
    with Session(engine) as session:
        expected = [
            str(row.id)
            for row in session.scalars(
                select(ExperimentModel)
                .where(ExperimentModel.id.in_(ids))
                .order_by(ExperimentModel.created_at.desc(), ExperimentModel.id.desc())
            )
        ]
    app = create_app(engine=engine, registry=_registry(), runner=GatedRunner())
    with TestClient(app) as client:
        first = client.get("/api/v1/experiments?limit=2")
        assert first.status_code == 200
        first_ids = [item["id"] for item in first.json()["items"]]
        assert first_ids == expected[:2]
        assert all(item["metrics"] is None for item in first.json()["items"])
        cursor = first.json()["nextCursor"]
        assert cursor
        second = client.get(f"/api/v1/experiments?limit=2&cursor={cursor}")
        assert second.status_code == 200
        assert [item["id"] for item in second.json()["items"]] == expected[2:]
        assert second.json()["nextCursor"] is None
        assert client.get("/api/v1/experiments?cursor=!!!").status_code == 422
        assert client.get("/api/v1/experiments?limit=0").status_code == 422
        assert client.get("/api/v1/experiments?limit=101").status_code == 422
    engine.dispose()


def test_completed_experiment_list_reuses_detail_metrics_and_pagination(database_url):
    engine = configure_utc_session_timezone(create_engine(database_url))
    with Session(engine) as session, session.begin():
        experiment_id, _, _ = _seed(session, "LONG")
        row = session.get(ExperimentModel, experiment_id)
        assert row is not None
        ExperimentRepository().create_result(
            session,
            experiment_id=experiment_id,
            result_schema_version="TEST_RESULT_V1",
            trade_count=0,
            ambiguous_trade_count=0,
            gross_pnl="0",
            commission_cost="0",
            financing_cost="0",
            modeled_net_pnl="0",
            ending_balance="10050",
            ending_equity="10050",
            net_return="0.005",
            max_drawdown_amount="50",
            max_drawdown_percent="0.0049504950495",
            financing_disclosure="EXCLUDED",
            completed_market_time=START + timedelta(days=2),
            output_fingerprint="1" * 64,
            metric_states={
                "net_return": {"state": "VALUE", "reason": None},
                "max_drawdown_amount": {"state": "VALUE", "reason": None},
                "max_drawdown_percent": {"state": "VALUE", "reason": None},
                "sharpe_ratio": {"state": "VALUE", "reason": None},
                "profit_factor": {"state": "UNAVAILABLE", "reason": "ZERO_TRADES"},
                "win_rate": {"state": "UNAVAILABLE", "reason": "ZERO_TRADES"},
                "expectancy_net_pnl": {"state": "UNAVAILABLE", "reason": "ZERO_TRADES"},
            },
        )
        row.status = "COMPLETED"
        row.completed_at = START + timedelta(days=2)
        for sequence, equity in enumerate(("10000", "10100", "10050"), start=1):
            session.add(
                ExperimentEquityPointModel(
                    experiment_id=experiment_id,
                    sequence_number=sequence,
                    observed_at=START + timedelta(days=sequence - 1),
                    balance=equity,
                    realized_pnl="0",
                    unrealized_pnl="0",
                    equity=equity,
                    running_peak=max("10000", equity),
                    drawdown_amount="0" if sequence < 3 else "50",
                    drawdown_percent="0" if sequence < 3 else "0.0049504950495",
                )
            )
    app = create_app(engine=engine, registry=_registry())
    with TestClient(app) as client:
        detail = client.get(f"/api/v1/experiments/{experiment_id}")
        assert detail.status_code == 200
        detail_metrics = detail.json()["metrics"]
        assert detail_metrics["netReturn"]["state"] == "VALUE"
        assert detail_metrics["maxDrawdownAmount"]["state"] == "VALUE"
        assert detail_metrics["maxDrawdownPercent"]["state"] == "VALUE"
        assert detail_metrics["sharpe"]["state"] == "VALUE"
        assert detail_metrics["profitFactor"]["reason"] == "ZERO_TRADES"
        assert detail_metrics["tradeCount"]["state"] == "VALUE"
        assert detail_metrics["tradeCount"]["value"] == "0"

        statements: list[str] = []

        def record_select(
            _conn, _cursor, statement, _parameters, _context, _executemany
        ):
            if statement.lstrip().upper().startswith("SELECT"):
                statements.append(statement)

        event.listen(engine, "before_cursor_execute", record_select)
        try:
            listing = client.get("/api/v1/experiments?limit=1")
        finally:
            event.remove(engine, "before_cursor_execute", record_select)
        assert listing.status_code == 200
        item = next(
            row for row in listing.json()["items"] if row["id"] == str(experiment_id)
        )
        assert item["metrics"] == detail_metrics
        assert item["identity"] == detail.json()["identity"]
        assert len(statements) == 3
        assert listing.json()["nextCursor"]

        page = client.get(
            f"/api/v1/experiments?limit=1&cursor={listing.json()['nextCursor']}"
        )
        assert page.status_code == 200
        assert all(row["id"] != str(experiment_id) for row in page.json()["items"])
    engine.dispose()


def test_non_completed_experiment_list_hides_persisted_result(database_url):
    engine = configure_utc_session_timezone(create_engine(database_url))
    with Session(engine) as session, session.begin():
        experiment_id, _, _ = _seed(session, "LONG")
        ExperimentRepository().create_result(
            session,
            experiment_id=experiment_id,
            result_schema_version="TEST_RESULT_V1",
            trade_count=1,
            ambiguous_trade_count=0,
            gross_pnl="100",
            commission_cost="0",
            financing_cost="0",
            modeled_net_pnl="100",
            ending_balance="10100",
            ending_equity="10100",
            net_return="0.01",
            max_drawdown_amount="0",
            max_drawdown_percent="0",
            financing_disclosure="EXCLUDED",
            completed_market_time=START + timedelta(days=2),
            output_fingerprint="2" * 64,
            metric_states={
                "net_return": {"state": "VALUE", "reason": None},
                "max_drawdown_amount": {"state": "VALUE", "reason": None},
                "max_drawdown_percent": {"state": "VALUE", "reason": None},
                "sharpe_ratio": {"state": "VALUE", "reason": None},
                "profit_factor": {"state": "VALUE", "reason": None},
                "win_rate": {"state": "VALUE", "reason": None},
                "expectancy_net_pnl": {"state": "VALUE", "reason": None},
            },
        )

    app = create_app(engine=engine, registry=_registry(), runner=GatedRunner())
    with TestClient(app) as client:
        response = client.get("/api/v1/experiments?limit=1")
        assert response.status_code == 200, response.text
        item = next(
            row for row in response.json()["items"] if row["id"] == str(experiment_id)
        )
        assert item["status"] != "COMPLETED"
        assert item["metrics"] is None
        assert item["result"] is None
        assert item["resultQuality"] is None
        assert item["resultSchemaVersion"] is None
    engine.dispose()


def test_strategy_catalog_projection_uses_one_bounded_read(database_url):
    engine = configure_utc_session_timezone(create_engine(database_url))
    _create(engine)
    app = create_app(engine=engine, registry=_registry())
    with TestClient(app) as client:
        statements: list[str] = []

        def record_select(
            _conn, _cursor, statement, _parameters, _context, _executemany
        ):
            if statement.lstrip().upper().startswith("SELECT"):
                statements.append(statement)

        event.listen(engine, "before_cursor_execute", record_select)
        try:
            response = client.get("/api/v1/strategies")
        finally:
            event.remove(engine, "before_cursor_execute", record_select)
        assert response.status_code == 200
        assert response.json()["items"]
        assert len(statements) == 1
    engine.dispose()


def test_http_comparison_uses_public_repeated_ids_and_is_read_only(database_url):
    engine = configure_utc_session_timezone(create_engine(database_url))
    try:
        with Session(engine) as session, session.begin():
            first_id, snapshot_id, version_id = _seed(session, "LONG")
            first = session.get(ExperimentModel, first_id)
            assert first is not None
            repository = ExperimentRepository()
            second = repository.create(
                session,
                strategy_version_id=version_id,
                dataset_snapshot_id=snapshot_id,
                venue_instrument_id=first.venue_instrument_id,
                trading_start=first.trading_start,
                trading_end=first.trading_end,
                starting_capital=first.starting_capital,
                risk_per_trade=first.risk_per_trade,
                parameter_snapshot=first.parameter_snapshot,
                risk_config=first.risk_config,
                simulation_config=first.simulation_config,
                model_version=first.model_version,
            )
            repository.create_account_and_position(session, second)
            second_id = second.id

        for experiment_id in (first_id, second_id):
            with Session(engine) as session, session.begin():
                result = ExperimentRunner(strategy_registry=_registry()).run(
                    session, experiment_id
                )
                assert result.status == "COMPLETED", result.failure

        with Session(engine) as session:
            before_counts = {
                model.__tablename__: session.scalar(
                    select(func.count()).select_from(model)
                )
                for model in (
                    ExperimentModel,
                    ExperimentResultModel,
                    ExperimentEquityPointModel,
                )
            }

        app = create_app(engine=engine, registry=_registry())
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/experiments/comparison",
                params=[
                    ("experimentId", str(second_id)),
                    ("experimentId", str(first_id)),
                ],
            )
            assert response.status_code == 200, response.text
            payload = response.json()
            assert [item["id"] for item in payload["experiments"]] == [
                str(second_id),
                str(first_id),
            ]
            metric_names = {
                "netReturn",
                "maxDrawdownAmount",
                "maxDrawdownPercent",
                "sharpe",
                "profitFactor",
                "winRate",
                "expectancy",
                "tradeCount",
            }
            for experiment in payload["experiments"]:
                assert set(experiment["metrics"]) == metric_names
                assert all(
                    set(metric) == {"state", "value", "unit", "reason"}
                    for metric in experiment["metrics"].values()
                )
            assert (
                client.get(
                    "/api/v1/experiments/comparison",
                    params=[
                        ("experiment_id", str(first_id)),
                        ("experiment_id", str(second_id)),
                    ],
                ).status_code
                == 422
            )

        with Session(engine) as session:
            after_counts = {
                model.__tablename__: session.scalar(
                    select(func.count()).select_from(model)
                )
                for model in (
                    ExperimentModel,
                    ExperimentResultModel,
                    ExperimentEquityPointModel,
                )
            }
            assert after_counts == before_counts
    finally:
        engine.dispose()


@pytest.mark.price_analysis
def test_price_analysis_completed_returns_m15_ema_and_markers(database_url):
    """LONG golden flow completed Experiment exposes M15/EMA + trade markers."""
    engine = configure_utc_session_timezone(create_engine(database_url))
    try:
        experiment_id = _complete_experiment(database_url, direction="LONG")
        # Snapshot counts BEFORE the API call so we can verify read-only behavior.
        with Session(engine) as before_session:
            before_counts = {
                model.__tablename__: before_session.scalar(
                    select(func.count()).select_from(model)
                )
                for model in (
                    ExperimentModel,
                    ExperimentResultModel,
                    ExperimentEquityPointModel,
                )
            }
        app = create_app(engine=engine, registry=_registry())
        with TestClient(app) as client:
            response = client.get(
                f"/api/v1/experiments/{experiment_id}/price-analysis"
            )
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload["tradingWindow"]["start"].endswith("Z")
            assert payload["tradingWindow"]["end"].endswith("Z")
            assert len(payload["m15"]) > 0
            assert len(payload["ema"]) > 0
            assert len(payload["trades"]) >= 1, (
                "Completed Experiment must expose at least one trade marker"
            )
            diagnostics = payload["diagnostics"]
            assert diagnostics["emaPeriod"] == PARAMETERS["ema_period"]
            assert diagnostics["requiredHistoricalContextBars"] == 100
            assert diagnostics["truncated"] is False
            assert diagnostics["snapshotFingerprint"]
            assert diagnostics["m15EligibleCount"] == diagnostics["m15ReturnedCount"]
            # Trade markers come from persisted rows; verify shape per-trade
            for trade in payload["trades"]:
                assert trade["direction"] == "LONG"
                assert trade["entry"]["t"].endswith("Z")
                assert trade["exit"] is not None
                assert trade["entry"]["price"]
                assert trade["stop"] is not None
                assert trade["stop"]["price"]
                assert trade["stop"]["from"].endswith("Z")
                assert trade["stop"]["to"].endswith("Z")
                assert trade["target"] is not None
                assert isinstance(trade["target"]["price"], str)
            # Reference facts come from rationale.
            assert len(payload["reference"]) == len(payload["trades"])
            for fact in payload["reference"]:
                assert fact["reference"]["t"].endswith("Z")
                assert fact["sweep"]["t"].endswith("Z")
                assert fact["confirmation"]["t"].endswith("Z")
        # Read-only guarantee: counts unchanged after the API call
        with Session(engine) as after_session:
            after_counts = {
                model.__tablename__: after_session.scalar(
                    select(func.count()).select_from(model)
                )
                for model in (
                    ExperimentModel,
                    ExperimentResultModel,
                    ExperimentEquityPointModel,
                )
            }
            assert after_counts == before_counts, (
                "GET /price-analysis must not mutate Experiment or result tables"
            )
    finally:
        engine.dispose()


@pytest.mark.price_analysis
def test_price_analysis_returns_404_for_missing_experiment(database_url):
    engine = configure_utc_session_timezone(create_engine(database_url))
    try:
        app = create_app(engine=engine, registry=_registry())
        with TestClient(app) as client:
            bogus = "00000000-0000-0000-0000-000000000000"
            response = client.get(f"/api/v1/experiments/{bogus}/price-analysis")
            assert response.status_code == 404, response.text
            body = response.json()
            error = body.get("error") or body.get("detail", {}).get("error", {})
            assert error["code"] == "NOT_FOUND"
    finally:
        engine.dispose()


@pytest.mark.price_analysis
def test_price_analysis_returns_409_for_pending_experiment(database_url):
    """Pending Experiments must return RESULT_NOT_READY before completion."""
    engine = configure_utc_session_timezone(create_engine(database_url))
    try:
        experiment_id = _create(engine)
        app = create_app(engine=engine, registry=_registry(), runner=GatedRunner())
        with TestClient(app) as client:
            response = client.get(
                f"/api/v1/experiments/{experiment_id}/price-analysis"
            )
            assert response.status_code == 409, response.text
            body = response.json()
            error = body.get("error") or body.get("detail", {}).get("error", {})
            assert error["code"] == "RESULT_NOT_READY"
    finally:
        engine.dispose()
