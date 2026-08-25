# fmt: off
# ruff: noqa: E501, B017

import os
from pathlib import Path
from urllib.parse import urlparse

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from backend.persistence.database import configure_utc_session_timezone

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def migration_url() -> str:
    value = os.environ.get("ATLAS_TEST_DATABASE_URL")
    if not value:
        pytest.skip("ATLAS_TEST_DATABASE_URL is not configured")
    if not urlparse(value).path.rsplit("/", 1)[-1].endswith("_test"):
        pytest.fail("migration reset requires a database name ending in _test")
    return value


def alembic_config(url: str) -> Config:
    config = Config(str(Path(__file__).parents[3] / "alembic.ini"))
    config.set_main_option("script_location", "backend/persistence/migrations")
    os.environ["ATLAS_DATABASE_URL"] = url
    return config


def test_migration_cycle(migration_url: str) -> None:
    engine = configure_utc_session_timezone(create_engine(migration_url))
    try:
        with engine.begin() as connection:
            connection.execute(text("DROP SCHEMA public CASCADE"))
            connection.execute(text("CREATE SCHEMA public"))
        config = alembic_config(migration_url)
        command.upgrade(config, "head")
        inspector = inspect(engine)
        assert sorted(inspector.get_table_names()) == [
            "alembic_version",
            "dataset_snapshot_analytical_bars",
            "dataset_snapshot_bars",
            "dataset_snapshot_execution_observations",
            "dataset_snapshot_gaps",
            "dataset_snapshots",
            "experiment_accounts",
            "experiment_equity_points",
            "experiment_gap_decisions",
            "experiment_results",
            "experiments",
            "fills",
            "historical_data_load_requests",
            "instruments",
            "market_bars",
            "order_events",
            "orders",
            "positions",
            "risk_decisions",
            "strategies",
            "strategy_versions",
            "trade_intents",
            "trades",
            "venue_instruments",
        ]
        assert {column["name"] for column in inspector.get_columns("experiments")} >= {
            "failure_category", "failure_code", "failure_detail"
        }
        assert {column["name"] for column in inspector.get_columns("dataset_snapshots")} >= {
            "snapshot_schema",
        }
        assert {column["name"] for column in inspector.get_columns("dataset_snapshot_analytical_bars")} >= {
            "dataset_snapshot_id", "sequence", "start_time", "end_time",
            "resolution", "price_component", "open_price", "high_price",
            "low_price", "close_price", "volume", "complete",
            "source_request_id", "content_fingerprint", "retrieved_at",
        }
        assert {column["name"] for column in inspector.get_columns("dataset_snapshot_execution_observations")} >= {
            "dataset_snapshot_id", "sequence", "market_bar_id",
            "price_component", "start_time", "end_time",
            "observation_fingerprint",
        }
        assert {column["name"] for column in inspector.get_columns("dataset_snapshot_gaps")} >= {
            "dataset_snapshot_id", "sequence", "start_time", "end_time",
            "price_component", "resolution", "source", "reason",
            "classification", "affected_state", "affected_event",
            "policy_version", "blocked",
        }
        assert {constraint["name"] for constraint in inspector.get_check_constraints("dataset_snapshot_analytical_bars")} >= {
            "ck_dataset_snapshot_analytical_bars_valid_analytical_member",
        }
        assert {constraint["name"] for constraint in inspector.get_check_constraints("dataset_snapshot_execution_observations")} >= {
            "ck_dataset_snapshot_execution_observations_valid_execut_5670",
        }
        assert {constraint["name"] for constraint in inspector.get_check_constraints("dataset_snapshot_gaps")} >= {
            "ck_dataset_snapshot_gaps_valid_snapshot_gap",
        }
        assert {
            constraint["name"]
            for constraint in inspector.get_unique_constraints("trade_intents")
        } >= {"uq_trade_intents_experiment_frontier"}
        assert {
            constraint["name"]
            for constraint in inspector.get_unique_constraints("risk_decisions")
        } >= {"uq_risk_decisions_intent_phase"}
        assert {
            constraint["name"]
            for constraint in inspector.get_unique_constraints("fills")
        } >= {"uq_fills_order_sequence"}
        assert {
            constraint["name"]
            for constraint in inspector.get_unique_constraints("positions")
        } >= {"uq_positions_experiment_instrument"}
        assert {column["name"] for column in inspector.get_columns("experiment_results")} >= {
            "sharpe_ratio", "profit_factor", "win_rate", "expectancy_net_pnl",
            "metric_states", "metric_schema_version", "result_quality",
        }
        assert {column["name"] for column in inspector.get_columns("experiment_gap_decisions")} >= {
            "experiment_id", "sequence", "start_time", "end_time", "resolution",
            "price_component", "classification", "rule_version", "policy_version",
            "affected_state", "affected_event", "blocked", "details",
        }
        assert "ix_experiments_created_at_id_desc" in {
            index["name"] for index in inspector.get_indexes("experiments")
        }
        command.check(config)
        command.downgrade(config, "0006_phase_4_persistence")
        legacy_columns = {
            column["name"] for column in inspect(engine).get_columns("experiment_results")
        }
        assert not {"sharpe_ratio", "metric_states", "metric_schema_version"} & legacy_columns
        command.upgrade(config, "head")
        assert {column["name"] for column in inspect(engine).get_columns("experiment_results")} >= {
            "sharpe_ratio", "profit_factor", "win_rate", "expectancy_net_pnl",
            "metric_states", "metric_schema_version", "result_quality",
        }
        command.downgrade(config, "base")
        assert inspect(engine).get_table_names() == ["alembic_version"]
        command.upgrade(config, "head")
    finally:
        engine.dispose()


def test_market_data_constraints_and_immutability(migration_url: str) -> None:
    engine = configure_utc_session_timezone(create_engine(migration_url))
    try:
        config = alembic_config(migration_url)
        command.upgrade(config, "head")
        with engine.begin() as connection:
            def rejected(statement: str, params: dict[str, object] | None = None) -> None:
                with pytest.raises(Exception):
                    with connection.begin_nested():
                        connection.execute(text(statement), params or {})

            bar_insert = text("""
                INSERT INTO market_bars
                  (venue_instrument_id, resolution, price_component,
                   start_time, end_time, open_price, high_price, low_price,
                   close_price, volume, complete, content_fingerprint,
                   source_request_id, retrieved_at, is_current)
                VALUES (:venue, :resolution, :component, :start_time, :end_time,
                  :open_price, :high_price, :low_price, :close_price, :volume,
                  :complete, :fingerprint, :request_id, :retrieved_at, :is_current)
                RETURNING id
            """)

            def bar_values(**overrides: object) -> dict[str, object]:
                values: dict[str, object] = {
                    "venue": venue,
                    "resolution": "M1",
                    "component": "MID",
                    "start_time": "2026-01-01T00:00:00Z",
                    "end_time": "2026-01-01T00:01:00Z",
                    "open_price": 1.1,
                    "high_price": 1.2,
                    "low_price": 1.0,
                    "close_price": 1.15,
                    "volume": None,
                    "complete": True,
                    "fingerprint": "a" * 64,
                    "request_id": None,
                    "retrieved_at": "2026-01-01T00:02:00Z",
                    "is_current": True,
                }
                values.update(overrides)
                return values

            instrument = connection.execute(
                text("""
                    INSERT INTO instruments (code, base_currency, quote_currency)
                    VALUES ('EUR/USD', 'EUR', 'USD') RETURNING id
                """)
            ).scalar_one()
            venue = connection.execute(
                text("""
                    INSERT INTO venue_instruments
                        (instrument_id, provider, provider_symbol)
                    VALUES (:instrument, 'OANDA', 'EUR_USD') RETURNING id
                """),
                {"instrument": instrument},
            ).scalar_one()
            bar = connection.execute(bar_insert, bar_values()).scalar_one()
            rejected("UPDATE market_bars SET open_price = 2 WHERE id = :id", {"id": bar})
            rejected(bar_insert.text, bar_values(fingerprint="b" * 64))

            for invalid in (
                {"resolution": "M5", "fingerprint": "c" * 64},
                {"component": "LAST", "fingerprint": "d" * 64},
                {"start_time": "2026-01-01T00:00:30Z", "end_time": "2026-01-01T00:01:30Z", "fingerprint": "e" * 64},
                {"end_time": "2026-01-01T00:02:00Z", "fingerprint": "f" * 64},
                {"complete": False, "fingerprint": "0" * 64},
                {"open_price": 0, "fingerprint": "1" * 64},
                {"low_price": 1.2, "fingerprint": "2" * 64},
                {"volume": -1, "fingerprint": "3" * 64},
                {"fingerprint": "A" * 64},
                {"request_id": "provider\nrequest", "fingerprint": "4" * 64},
            ):
                rejected(bar_insert.text, bar_values(**invalid))

            connection.execute(text("UPDATE market_bars SET is_current = false WHERE id = :id"), {"id": bar})
            rejected("DELETE FROM market_bars WHERE id = :id", {"id": bar})
            rejected("INSERT INTO instruments (code, base_currency, quote_currency) VALUES ('GBP/USD', 'GBP', 'USD')")
            rejected("INSERT INTO venue_instruments (instrument_id, provider, provider_symbol) VALUES (:instrument, 'OANDA', 'EUR_USD')", {"instrument": instrument})
            historical_variant = connection.execute(
                bar_insert, bar_values(
                    open_price=1.0,
                    high_price=1.1,
                    low_price=0.9,
                    close_price=1.05,
                    fingerprint="b" * 64,
                    is_current=False,
                )
            ).scalar_one()
            assert historical_variant != bar
            snapshot_insert = text("""
                INSERT INTO dataset_snapshots
                  (venue_instrument_id, base_resolution, components,
                   coverage_start, coverage_end, alignment_convention,
                   session_policy, fingerprint_schema, fingerprint,
                   integrity_summary)
                VALUES (:venue, :base_resolution, CAST(:components AS jsonb),
                  :coverage_start, :coverage_end, :alignment, :session_policy,
                  :fingerprint_schema, repeat(:fingerprint_char, 64),
                  jsonb_build_object('status', CAST(:status AS text),
                    'expected_open_minutes', 1, 'expected_closure_minutes', 0,
                    'member_minutes', 1, 'bar_count', 1,
                    'unexpected_gap_count', 0,
                    'unexpected_observation_count', 0,
                    'session_policy', CAST(:integrity_session AS text)))
                RETURNING id
            """)

            def snapshot_values(**overrides: object) -> dict[str, object]:
                values: dict[str, object] = {
                    "venue": venue,
                    "base_resolution": "M1",
                    "components": '["ASK","BID","MID"]',
                    "coverage_start": "2026-01-01T00:00:00Z",
                    "coverage_end": "2026-01-01T00:01:00Z",
                    "alignment": "UTC_HALF_OPEN_V1",
                    "session_policy": "OANDA_FX_NY_V1",
                    "fingerprint_schema": "ATLAS_DATASET_SHA256_V1",
                    "fingerprint_char": "c",
                    "status": "VALID",
                    "integrity_session": "OANDA_FX_NY_V1",
                }
                values.update(overrides)
                return values

            for invalid in (
                {"base_resolution": "M15", "fingerprint_char": "d"},
                {"components": '["MID","BID","ASK"]', "fingerprint_char": "e"},
                {"alignment": "LOCAL_HALF_OPEN_V1", "fingerprint_char": "f"},
                {"session_policy": "UNKNOWN", "integrity_session": "UNKNOWN", "fingerprint_char": "0"},
                {"fingerprint_schema": "ATLAS_DATASET_SHA256_V2", "fingerprint_char": "1"},
                {"coverage_end": "2026-01-01T00:00:00Z", "fingerprint_char": "2"},
                {"coverage_start": "2026-01-01T00:00:30Z", "fingerprint_char": "3"},
                {"status": "INVALID", "fingerprint_char": "4"},
                {"fingerprint_char": "A"},
            ):
                rejected(snapshot_insert.text, snapshot_values(**invalid))

            snapshot = connection.execute(
                snapshot_insert, snapshot_values()
            ).scalar_one()
            rejected(snapshot_insert.text, snapshot_values())
            connection.execute(text("INSERT INTO dataset_snapshot_bars VALUES (:snapshot, :bar)"), {"snapshot": snapshot, "bar": bar})
            v2_snapshot = connection.execute(text("""
                INSERT INTO dataset_snapshots
                  (venue_instrument_id, base_resolution, components,
                   coverage_start, coverage_end, alignment_convention,
                   session_policy, fingerprint_schema, fingerprint,
                   integrity_summary, snapshot_schema)
                VALUES (:venue, 'M15', '["MID"]'::jsonb,
                  '2026-01-01T00:00:00Z', '2026-01-01T01:00:00Z',
                  'UTC_HALF_OPEN_V1', 'OANDA_FX_NY_V1',
                  'ATLAS_DATASET_SHA256_V2', repeat('e', 64),
                  '{"status":"VALID","policy_version":"ATLAS_HISTORICAL_GAP_POLICY_V1"}'::jsonb,
                  'ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2')
                RETURNING id
            """), {"venue": venue}).scalar_one()
            connection.execute(text("""
                INSERT INTO dataset_snapshot_analytical_bars
                  (dataset_snapshot_id, sequence, start_time, end_time,
                   resolution, price_component, open_price, high_price,
                   low_price, close_price, complete, content_fingerprint,
                   retrieved_at)
                VALUES (:snapshot, 1, '2026-01-01T00:00:00Z',
                  '2026-01-01T00:15:00Z', 'M15', 'MID', 1.1, 1.2, 1.0,
                  1.15, true, repeat('f', 64), '2026-01-01T00:16:00Z')
            """), {"snapshot": v2_snapshot})
            rejected("UPDATE dataset_snapshot_analytical_bars SET open_price = 2 WHERE dataset_snapshot_id = :snapshot AND sequence = 1", {"snapshot": v2_snapshot})
            rejected("INSERT INTO dataset_snapshot_bars VALUES (:snapshot, :bar)", {"snapshot": snapshot, "bar": bar})
            rejected("DELETE FROM dataset_snapshot_bars WHERE dataset_snapshot_id = :snapshot AND market_bar_id = :bar", {"snapshot": snapshot, "bar": bar})
            rejected("UPDATE dataset_snapshots SET fingerprint = repeat('d', 64) WHERE id = :snapshot", {"snapshot": snapshot})
            rejected("DELETE FROM dataset_snapshots WHERE id = :snapshot", {"snapshot": snapshot})
            rejected("DELETE FROM market_bars WHERE id = :id", {"id": bar})
            rejected("DELETE FROM venue_instruments WHERE id = :venue", {"venue": venue})
            rejected("DELETE FROM instruments WHERE id = :instrument", {"instrument": instrument})
    finally:
        engine.dispose()
