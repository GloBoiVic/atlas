"""Seed the isolated PostgreSQL database used by the Playwright workflow tests."""

from __future__ import annotations

import json
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, select, text, update
from sqlalchemy.orm import Session

from backend.domain.market_data import Instrument
from backend.experiments.runner import ExperimentRunner
from backend.integrations.oanda.capabilities import OANDA_CAPABILITY
from backend.persistence.database import configure_utc_session_timezone
from backend.persistence.experiment_repository import ExperimentRepository
from backend.persistence.models import ExperimentModel
from backend.strategies.production import create_production_strategy_registry
from backend.tests.integration.test_golden_flows import _seed

ROOT = Path(__file__).parents[2]


def main() -> None:
    database_url = os.environ.get("ATLAS_E2E_DATABASE_URL")
    fixture_file = os.environ.get("ATLAS_E2E_FIXTURE_FILE")
    if not database_url or not fixture_file:
        raise SystemExit(
            "ATLAS_E2E_DATABASE_URL and ATLAS_E2E_FIXTURE_FILE are required"
        )
    os.environ["ATLAS_DATABASE_URL"] = database_url
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", "backend/persistence/migrations")
    command.upgrade(config, "head")
    engine = configure_utc_session_timezone(create_engine(database_url))
    try:
        with Session(engine) as session, session.begin():
            session.execute(
                text(
                    """
                    DO $$ DECLARE r RECORD; BEGIN
                      FOR r IN SELECT tablename FROM pg_tables
                        WHERE schemaname = current_schema()
                          AND tablename <> 'alembic_version'
                      LOOP EXECUTE format('TRUNCATE TABLE %I CASCADE', r.tablename);
                      END LOOP;
                    END $$;
                    """
                )
            )
            valid_id, snapshot_id, version_id = _seed(
                session, "LONG", complete_execution=True, m15_count=106
            )
            valid_experiment = session.get(ExperimentModel, valid_id)
            assert valid_experiment is not None
            runner = ExperimentRunner(
                strategy_registry=create_production_strategy_registry(ROOT),
                market_specification=OANDA_CAPABILITY.market_specification(
                    Instrument.EUR_USD
                ),
            )
            assert runner.run(session, valid_id).status == "COMPLETED"
            comparison_experiment = ExperimentRepository().create(
                session,
                strategy_version_id=valid_experiment.strategy_version_id,
                dataset_snapshot_id=valid_experiment.dataset_snapshot_id,
                venue_instrument_id=valid_experiment.venue_instrument_id,
                trading_start=valid_experiment.trading_start,
                trading_end=valid_experiment.trading_end,
                starting_capital=valid_experiment.starting_capital,
                risk_per_trade=valid_experiment.risk_per_trade,
                parameter_snapshot=valid_experiment.parameter_snapshot,
                risk_config=valid_experiment.risk_config,
                simulation_config=valid_experiment.simulation_config,
                model_version=valid_experiment.model_version,
            )
            ExperimentRepository().create_account_and_position(
                session, comparison_experiment
            )
            assert (
                runner.run(session, comparison_experiment.id).status == "COMPLETED"
            )
            failed_experiment = ExperimentRepository().create(
                session,
                strategy_version_id=valid_experiment.strategy_version_id,
                dataset_snapshot_id=valid_experiment.dataset_snapshot_id,
                venue_instrument_id=valid_experiment.venue_instrument_id,
                trading_start=valid_experiment.trading_start,
                trading_end=valid_experiment.trading_end,
                starting_capital=valid_experiment.starting_capital,
                risk_per_trade=valid_experiment.risk_per_trade,
                parameter_snapshot={
                    **valid_experiment.parameter_snapshot,
                    "stop_buffer": "invalid",
                },
                risk_config=valid_experiment.risk_config,
                simulation_config=valid_experiment.simulation_config,
                model_version=valid_experiment.model_version,
            )
            ExperimentRepository().create_account_and_position(
                session, failed_experiment
            )
            failed_id = failed_experiment.id
            _, zero_snapshot_id, _ = _seed(
                session, "LONG", complete_execution=True, m15_count=103
            )
            # Keep the invalid snapshot's coverage facts distinct from the
            # valid zero-Trade fixture; its sparse execution remains invalid.
            invalid_id, invalid_snapshot_id, _ = _seed(session, "LONG", m15_count=104)
            # The test database may still contain the retired Phase 4 insert
            # trigger, which changes current-model inserts from PENDING to
            # RUNNING. Restore the intended command boundary for these E2E
            # fixtures without changing application or migration behavior.
            zero_experiment = session.scalar(
                select(ExperimentModel).where(
                    ExperimentModel.dataset_snapshot_id == zero_snapshot_id,
                    ExperimentModel.id != valid_id,
                    ExperimentModel.id != failed_id,
                )
            )
            assert zero_experiment is not None
            session.execute(
                update(ExperimentModel)
                .where(
                    ExperimentModel.id.in_(
                        (failed_id, zero_experiment.id, invalid_id)
                    )
                )
                .values(status="PENDING")
            )
            session.expire_all()
        Path(fixture_file).write_text(
            json.dumps(
                {
                    "failedExperimentId": str(failed_id),
                    "datasetSnapshotId": str(snapshot_id),
                    "primarySnapshotId": str(snapshot_id),
                    "invalidSnapshotId": str(invalid_snapshot_id),
                    "strategyVersionId": str(version_id),
                    "zeroSnapshotId": str(zero_snapshot_id),
                }
            )
        )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
