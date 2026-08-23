"""Shared PostgreSQL isolation for integration tests.

The integration test files all run against one shared ``*_test`` PostgreSQL
database and seed overlapping fixtures (for example the ``EUR/USD`` instrument
and the ``ema_sweep_engulfing`` strategy). Some intentionally commit rows that
cannot be removed through the guarded application DML path (terminal
Experiments and StrategyVersions are append-only), and some migration tests
drop and re-create the schema or downgrade to base on teardown. Left alone,
residue and schema state from one file leak into the next and across separate
``pytest`` invocations, which made ``pytest -q`` fail as a single command
(e.g. a ``UniqueViolation`` on ``instruments.code`` when an earlier file had
already seeded ``EUR/USD``, or ``relation does not exist`` when a prior run had
left the schema at base).

To make every integration test mutually isolated regardless of run order or
prior residue, this module provides two autouse fixtures:

1. ``_ensure_integration_schema`` (session) migrates the shared database to the
   migration head once, so a full run is self-sufficient no matter what schema
   state a previous invocation left behind.
2. ``_isolate_integration_database`` (function) truncates every data table
   before each integration test, so no test observes another test's rows.

``TRUNCATE ... CASCADE`` is used because it bypasses the row-level immutability
triggers (which only guard DML row transitions), so it can clear
append-only/terminal rows that a guarded DELETE could not. The same mechanism
is already used by the existing integration files for their own cleanup.
"""

import os
from pathlib import Path
from urllib.parse import urlparse

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from backend.persistence.database import configure_utc_session_timezone

# Truncate every table in the current (public) schema except alembic_version.
# Iterating pg_tables keeps the statement robust to the schema being absent
# (a no-op) and avoids hard-coding the table set here, which test_migrations.py
# already asserts as the migration's responsibility.
_TRUNCATE_ALL = text(
    """
    DO $$
    DECLARE
        r RECORD;
    BEGIN
        FOR r IN
            SELECT t.tablename
            FROM pg_tables AS t
            WHERE t.schemaname = current_schema()
              AND t.tablename <> 'alembic_version'
        LOOP
            EXECUTE format('TRUNCATE TABLE %I CASCADE', r.tablename);
        END LOOP;
    END $$;
    """
)

_ROOT = Path(__file__).parents[3]


def _test_database_url() -> str | None:
    """Return the configured integration URL, or None when not applicable."""
    url = os.environ.get("ATLAS_TEST_DATABASE_URL")
    if not url:
        return None
    database = urlparse(url).path.rsplit("/", 1)[-1]
    if not database.endswith("_test"):
        return None
    return url


@pytest.fixture(scope="session", autouse=True)
def _ensure_integration_schema() -> None:
    """Migrate the shared test database to head once per integration session.

    Integration files assume the schema is present (test_fill_application, for
    example, never runs migrations itself and runs before the files that do).
    A prior partial invocation can downgrade the schema to base, so this makes
    the full suite self-sufficient regardless of the starting schema state.
    """
    url = _test_database_url()
    if not url:
        return
    config = Config(str(_ROOT / "alembic.ini"))
    config.set_main_option("script_location", "backend/persistence/migrations")
    # env.py deliberately reads this explicit test-only URL for migrations.
    os.environ["ATLAS_DATABASE_URL"] = url
    command.upgrade(config, "head")


@pytest.fixture(autouse=True)
def _isolate_integration_database() -> None:
    """Truncate the shared test database before each integration test."""
    url = _test_database_url()
    if not url:
        return
    engine = configure_utc_session_timezone(create_engine(url))
    try:
        with engine.begin() as connection:
            connection.execute(_TRUNCATE_ALL)
    finally:
        engine.dispose()
