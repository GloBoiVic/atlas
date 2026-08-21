"""Controlled PostgreSQL evidence for the runner's durable failure boundary."""

# ruff: noqa: E501, B017

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.experiments.runner import ExperimentRunner
from backend.strategies.registry import StrategyRegistry

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def runner_database_url() -> str:
    value = os.environ.get("ATLAS_TEST_DATABASE_URL")
    if not value:
        pytest.skip("ATLAS_TEST_DATABASE_URL is not configured")
    return value


def test_runner_persists_sanitized_terminal_failure(runner_database_url: str) -> None:
    engine = create_engine(runner_database_url)
    try:
        config = Config(str(Path(__file__).parents[3] / "alembic.ini"))
        config.set_main_option("script_location", "backend/persistence/migrations")
        os.environ["ATLAS_DATABASE_URL"] = runner_database_url
        command.upgrade(config, "head")

        now = datetime(2026, 1, 1, tzinfo=UTC)
        with Session(engine) as session, session.begin():
            instrument = session.execute(text("""
                INSERT INTO instruments (code, base_currency, quote_currency)
                VALUES ('EUR/USD', 'EUR', 'USD')
                ON CONFLICT (code) DO UPDATE SET code = EXCLUDED.code RETURNING id
            """)).scalar_one()
            venue = session.execute(text("""
                INSERT INTO venue_instruments (instrument_id, provider, provider_symbol)
                VALUES (:instrument, 'OANDA', 'EUR_USD')
                ON CONFLICT (provider, provider_symbol) DO UPDATE
                SET instrument_id = EXCLUDED.instrument_id RETURNING id
            """), {"instrument": instrument}).scalar_one()
            strategy = session.execute(text("""
                INSERT INTO strategies (strategy_key, name, description)
                VALUES ('controlled.failure', 'Controlled failure', 'integration') RETURNING id
            """)).scalar_one()
            version = session.execute(text("""
                INSERT INTO strategy_versions
                    (strategy_id, version_number, source_fingerprint, implementation_key,
                     parameter_schema, context_timeframes, capabilities, source_manifest,
                     exact_source_snapshot, primary_timeframe, warm_up_bars, state_schema_version)
                VALUES (:strategy, 1, repeat('a', 64), 'controlled.failure', '[]', '[]', '[]', '[]', '{}', 'M15', 0, 1)
                RETURNING id
            """), {"strategy": strategy}).scalar_one()
            snapshot = session.execute(text("""
                INSERT INTO dataset_snapshots
                    (venue_instrument_id, base_resolution, components, coverage_start, coverage_end,
                     alignment_convention, session_policy, fingerprint_schema, fingerprint, integrity_summary)
                VALUES (:venue, 'M1', '["ASK","BID","MID"]', :start, :end, 'UTC_HALF_OPEN_V1',
                        'OANDA_FX_NY_V1', 'ATLAS_DATASET_SHA256_V1', repeat('b', 64),
                        jsonb_build_object('status','VALID','expected_open_minutes',0,
                          'expected_closure_minutes',0,'member_minutes',0,'bar_count',0,
                          'unexpected_gap_count',0,'unexpected_observation_count',0,
                          'session_policy','OANDA_FX_NY_V1')) RETURNING id
            """), {"venue": venue, "start": now, "end": now.replace(hour=1)}).scalar_one()
            experiment = session.execute(text("""
                INSERT INTO experiments
                    (strategy_version_id, dataset_snapshot_id, venue_instrument_id, trading_start,
                     trading_end, starting_capital, risk_per_trade, parameter_snapshot, risk_config,
                     simulation_config, model_version)
                VALUES (:version, :snapshot, :venue, :start, :end, 10000, .01, '{}', '{}', '{}',
                        'PHASE3_OPEN_CHECKPOINT_V1') RETURNING id
            """), {"version": version, "snapshot": snapshot, "venue": venue,
                    "start": now, "end": now.replace(hour=1)}).scalar_one()

        with Session(engine) as session, session.begin():
            result = ExperimentRunner(strategy_registry=StrategyRegistry()).run(session, experiment)
            assert result.status == "FAILED"
            assert result.failure is not None
            row = session.execute(text("""
                SELECT status, failure_category, failure_code, failure_detail
                FROM experiments WHERE id = :id
            """), {"id": experiment}).one()
            assert row == (
                "FAILED", "MARKET_DATA", "INVALID_INPUT", "Experiment could not be run"
            )
            assert "\n" not in row.failure_detail
            with pytest.raises(Exception):
                with session.begin_nested():
                    session.execute(text("UPDATE experiments SET failure_detail = 'changed' WHERE id = :id"), {"id": experiment})
            # TRUNCATE is intentional: terminal Experiment rows cannot be deleted
            # through the guarded application DML path, even by test cleanup.
            session.execute(text("TRUNCATE experiments, dataset_snapshots, strategy_versions, strategies, venue_instruments, instruments CASCADE"))
    finally:
        engine.dispose()
