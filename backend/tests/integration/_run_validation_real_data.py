"""Run end-to-end validation of the price-analysis seam with real persisted data.

This script is invoked by VALIDATION test execution only. It creates two
completed Experiments on the integration database:
  1. A trade-producing Experiment (Phase4 with the golden LONG flow window).
  2. A zero-trade Experiment (a narrower no-setup window). It uses the same
     synthetic snapshot, but a trading window that does not contain the setup
     candle the Strategy expects.

It then records Experiment ids and the price-analysis JSON envelope so the
VALIDATION.md report can cite concrete real-data evidence. The script does not
mutate the snapshot (only creates new Experiments and queries the seam).
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from backend.api.app import create_app  # noqa: E402
from backend.experiments.runner import ExperimentRunner  # noqa: E402
from backend.persistence.database import configure_utc_session_timezone  # noqa: E402
from backend.persistence.experiment_repository import ExperimentRepository  # noqa: E402
from backend.tests.integration.test_golden_flows import (  # noqa: E402
    PARAMETERS,
    START,
    _registry,
    _seed,
)
from fastapi.testclient import TestClient  # noqa: E402


def _long_window():
    """Trade-producing: Phase4 LONG golden window that contains the setup."""
    return (
        START + timedelta(minutes=1500),
        START + timedelta(minutes=1545),
    )


def _zero_trade_window():
    """Zero-trade: window AFTER the setup/trade completed, no new setup."""
    return (
        START + timedelta(minutes=1560),
        START + timedelta(minutes=1590),
    )


_PHASE4_SIM_CONFIG = {
    "schema_version": "PHASE4_SIMULATION_CONFIG_V1",
    "execution_resolution": "M1",
    "analysis_component": "MID",
    "execution_components": ["BID", "ASK"],
    "spread_model": "DATASET_BID_ASK_EMBEDDED",
    "slippage_model": {"type": "ADVERSE_FIXED_TICKS", "ticks": 0, "tick_size": "0.00001"},
    "commission_model": {"type": "PER_FILL_PER_UNIT_USD", "amount": "0.10"},
    "financing_model": {"type": "EXCLUDED", "disclosure": "FINANCING EXCLUDED"},
    "intrabar_policy": "STOP_LOSS_ADVERSE_FIRST_V1",
    "target_fill_policy": "REQUESTED_PRICE_NO_IMPROVEMENT_V1",
    "end_policy": "FINAL_ELIGIBLE_M1_CLOSE_V1",
    "equity_sampling": "TRADING_START_AND_EACH_ELIGIBLE_M1_CLOSE_V1",
}


def _complete(engine: Session, *, snapshot_id, version_id, venue_instrument_id,
              trading_start, trading_end):
    repo = ExperimentRepository()
    experiment = repo.create(
        engine,
        strategy_version_id=version_id,
        dataset_snapshot_id=snapshot_id,
        venue_instrument_id=venue_instrument_id,
        trading_start=trading_start,
        trading_end=trading_end,
        starting_capital=Decimal("10000"),
        risk_per_trade=Decimal("0.01"),
        parameter_snapshot=PARAMETERS,
        risk_config={"schema_version": "PHASE4_RISK_CONFIG_V1", "risk_per_trade": "0.01"},
        simulation_config=_PHASE4_SIM_CONFIG,
        model_version="PHASE4_HISTORICAL_EXECUTION_V1",
    )
    repo.create_account_and_position(engine, experiment)
    engine.flush()
    return experiment.id


def main() -> None:
    url = os.environ.get("ATLAS_TEST_DATABASE_URL")
    if not url:
        print("ATLAS_TEST_DATABASE_URL not configured; aborting")
        sys.exit(2)
    engine = configure_utc_session_timezone(create_engine(url))
    results = {}


    with Session(engine) as session, session.begin():
        session.execute(text(
            "TRUNCATE experiments, dataset_snapshots, market_bars, strategy_versions, "
            "strategies, venue_instruments, instruments CASCADE"
        ))
        seeded_id, snapshot_id, version_id = _seed(
            session, "LONG", phase4=True
        )
        venue_id = session.scalar(text(
            "SELECT venue_instrument_id FROM dataset_snapshots WHERE id = :sid"
        ).bindparams(sid=snapshot_id))
        results["snapshot_id"] = str(snapshot_id)
        results["strategy_version_id"] = str(version_id)
        results["venue_instrument_id"] = str(venue_id)
    # Trade-producing experiment (same window as Phase4 LONG golden).
    ts, te = _long_window()
    with Session(engine) as session, session.begin():
        trade_id = _complete(
            session,
            snapshot_id=snapshot_id,
            version_id=version_id,
            venue_instrument_id=venue_id,
            trading_start=ts,
            trading_end=te,
        )
    with Session(engine) as session, session.begin():
        runner = ExperimentRunner(strategy_registry=_registry())
        result = runner.run(session, trade_id)
        assert result.status == "COMPLETED", result.failure
    results["trade_experiment_id"] = str(trade_id)

    # Zero-trade experiment (narrower window pre-empting setup).
    zts, zte = _zero_trade_window()
    with Session(engine) as session, session.begin():
        zero_id = _complete(
            session,
            snapshot_id=snapshot_id,
            version_id=version_id,
            venue_instrument_id=venue_id,
            trading_start=zts,
            trading_end=zte,
        )
    with Session(engine) as session, session.begin():
        result = ExperimentRunner(
            strategy_registry=_registry()
        ).run(session, zero_id)
        assert result.status == "COMPLETED", result.failure
        trade_count = session.scalar(text(
            "SELECT COUNT(*) FROM trades WHERE experiment_id = :eid"
        ).bindparams(eid=zero_id))
        results["zero_experiment_id"] = str(zero_id)
        results["zero_experiment_trade_count"] = int(trade_count or 0)

    # Capture price-analysis payloads.
    app = create_app(engine=engine, registry=_registry())
    with TestClient(app) as client:
        for label, experiment_id in (
            ("trade", trade_id),
            ("zero", zero_id),
        ):
            response = client.get(
                f"/api/v1/experiments/{experiment_id}/price-analysis"
            )
            assert response.status_code == 200, response.text
            payload = response.json()
            # Trim large arrays to keep the report readable.
            results[f"{label}_payload"] = {
                **{key: payload[key] for key in (
                    "tradingWindow", "diagnostics",
                )},
                "m15_count": len(payload["m15"]),
                "ema_count": len(payload["ema"]),
                "trades_count": len(payload["trades"]),
                "reference_count": len(payload["reference"]),
                "m15_first": payload["m15"][:2],
                "m15_last": payload["m15"][-2:],
                "ema_first": payload["ema"][:2],
                "ema_last": payload["ema"][-2:],
                "trades": payload["trades"],
                "reference_first": payload["reference"][:1],
            }

    out_path = Path(
        "/Users/vike/Desktop/atlas/dispatch/workstreams"
        "/experiment-results-chart/_validation_real_data.json"
    )
    out_path.write_text(json.dumps(results, indent=2, default=str))
    print(f"wrote {out_path}")
    engine.dispose()


if __name__ == "__main__":
    main()
