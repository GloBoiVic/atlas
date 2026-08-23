from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import Engine, create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker

from backend.config import Settings

_UTC_SESSION_STATEMENT = "SET SESSION TIME ZONE 'UTC'"
_UTC_POLICY_MARKER = "_atlas_utc_session_policy_configured"


def _set_utc_session(dbapi_connection: Any, *_event_args: Any) -> None:
    """Set the psycopg session timezone without inheriting an app transaction."""
    previous_autocommit = dbapi_connection.autocommit
    try:
        dbapi_connection.autocommit = True
        with dbapi_connection.cursor() as cursor:
            cursor.execute(_UTC_SESSION_STATEMENT)
    finally:
        dbapi_connection.autocommit = previous_autocommit


def configure_utc_session_timezone(engine: Engine) -> Engine:
    """Govern PostgreSQL connections with Atlas's canonical UTC session policy."""
    if engine.dialect.name != "postgresql" or engine.dialect.driver != "psycopg":
        return engine
    if getattr(engine, _UTC_POLICY_MARKER, False):
        return engine

    event.listen(engine, "connect", _set_utc_session)
    event.listen(engine, "checkout", _set_utc_session)
    setattr(engine, _UTC_POLICY_MARKER, True)
    return engine


def create_database_engine(settings: Settings) -> Engine:
    engine = create_engine(
        settings.database_url.get_secret_value(),
        pool_pre_ping=True,
        connect_args={"connect_timeout": settings.database_connect_timeout_seconds},
    )
    return configure_utc_session_timezone(engine)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    configure_utc_session_timezone(engine)
    # Phase 4's historical runner creates dependent facts and then reads them
    # again within the caller-owned transaction.  Keep the application session
    # factory's flush behavior aligned with the direct runner/lifecycle path;
    # disabling autoflush makes the API composition unable to observe pending
    # entry facts and fails only when the primary case creates a Trade.
    return sessionmaker(bind=engine, autoflush=True, expire_on_commit=False)


def check_database(engine: Engine) -> None:
    with engine.connect() as connection:
        connection.execute(select(1))


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Generator[Session]:
    session = factory()
    try:
        yield session
    finally:
        session.close()
