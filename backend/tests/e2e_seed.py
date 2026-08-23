"""Seed the isolated PostgreSQL database used by the Playwright workflow tests."""

from __future__ import annotations

import json
import os
from datetime import timedelta
from hashlib import sha256
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from backend.persistence.database import configure_utc_session_timezone
from backend.persistence.models import (
    DatasetSnapshotBarModel,
    DatasetSnapshotModel,
    MarketBarModel,
)
from backend.tests.integration.test_golden_flows import START, _seed

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
            failed_id, snapshot_id, version_id = _seed(
                session, "LONG", phase4=True, invalid_config=True
            )
            source_snapshot = session.get(DatasetSnapshotModel, snapshot_id)
            assert source_snapshot is not None
            zero_end = START + timedelta(minutes=1515)
            zero_snapshot = DatasetSnapshotModel(
                venue_instrument_id=source_snapshot.venue_instrument_id,
                base_resolution=source_snapshot.base_resolution,
                components=source_snapshot.components,
                coverage_start=source_snapshot.coverage_start,
                coverage_end=zero_end,
                alignment_convention=source_snapshot.alignment_convention,
                session_policy=source_snapshot.session_policy,
                fingerprint_schema=source_snapshot.fingerprint_schema,
                fingerprint=sha256(b"atlas-phase5-e2e-zero-snapshot").hexdigest(),
                integrity_summary={
                    "status": "VALID",
                    "expected_open_minutes": 1509,
                    "expected_closure_minutes": 6,
                    "member_minutes": 1509,
                    "bar_count": 4527,
                    "unexpected_gap_count": 0,
                    "unexpected_observation_count": 0,
                    "session_policy": source_snapshot.session_policy,
                },
            )
            session.add(zero_snapshot)
            session.flush()
            zero_snapshot_id = zero_snapshot.id
            zero_bars = session.scalars(
                select(MarketBarModel).where(
                    MarketBarModel.venue_instrument_id
                    == source_snapshot.venue_instrument_id,
                    MarketBarModel.start_time < zero_end,
                )
            )
            session.add_all(
                DatasetSnapshotBarModel(
                    dataset_snapshot_id=zero_snapshot.id, market_bar_id=bar.id
                )
                for bar in zero_bars
            )
        Path(fixture_file).write_text(
            json.dumps(
                {
                    "failedExperimentId": str(failed_id),
                    "datasetSnapshotId": str(snapshot_id),
                    "primarySnapshotId": str(snapshot_id),
                    "strategyVersionId": str(version_id),
                    "zeroSnapshotId": str(zero_snapshot_id),
                }
            )
        )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
