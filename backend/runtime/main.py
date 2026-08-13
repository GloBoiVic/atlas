import argparse
import logging
import signal
import threading

from backend.config import Settings
from backend.logging import configure_logging
from backend.persistence.database import check_database, create_database_engine

logger = logging.getLogger(__name__)


def stop_signal(event: threading.Event, _signum: int, _frame: object) -> None:
    event.set()


def run(check_only: bool = False, stop_event: threading.Event | None = None) -> int:
    try:
        settings = Settings()  # type: ignore[call-arg]
    except Exception:
        print("invalid configuration: database_url or another setting is invalid")
        return 2
    configure_logging(settings)
    engine = create_database_engine(settings)
    try:
        check_database(engine)
    except Exception as error:
        logger.error("database startup check failed: %s", type(error).__name__)
        engine.dispose()
        return 1
    logger.info("atlas-runtime is ready")
    if check_only:
        engine.dispose()
        return 0
    event = stop_event or threading.Event()
    event.wait()
    logger.info("atlas-runtime shutting down")
    engine.dispose()
    return 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    stop_event = threading.Event()
    signal.signal(
        signal.SIGINT,
        lambda signum, frame: stop_signal(stop_event, signum, frame),
    )
    signal.signal(
        signal.SIGTERM,
        lambda signum, frame: stop_signal(stop_event, signum, frame),
    )
    raise SystemExit(run(args.check, stop_event))
