"""HTTP contract regression for the durable RUNNING claim."""

import os
from datetime import UTC, timedelta
from threading import Thread

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.api.app import create_app
from backend.persistence.database import configure_utc_session_timezone
from backend.persistence.models import (
    ExperimentEquityPointModel,
    ExperimentModel,
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
    experiment_id = _create(engine)
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
        "tradingEnd": (START + timedelta(minutes=1590))
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
        experiment_id, _, _ = _seed(session, "LONG", phase4=True)
        row = session.get(ExperimentModel, experiment_id)
        assert row is not None
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

        listing = client.get("/api/v1/experiments?limit=1")
        assert listing.status_code == 200
        item = next(
            row for row in listing.json()["items"] if row["id"] == str(experiment_id)
        )
        assert item["metrics"] == detail_metrics
        assert listing.json()["nextCursor"]

        page = client.get(
            f"/api/v1/experiments?limit=1&cursor={listing.json()['nextCursor']}"
        )
        assert page.status_code == 200
        assert all(row["id"] != str(experiment_id) for row in page.json()["items"])
    engine.dispose()
