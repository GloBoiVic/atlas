import argparse
import logging
import os
import signal
import threading
from typing import Any

from backend.config import Settings
from backend.domain.market_data import Instrument
from backend.integrations.oanda.capabilities import OANDA_CAPABILITY
from backend.integrations.oanda.readonly import OandaPracticeReadOnlyClient
from backend.integrations.oanda.source import OandaHistoricalBarSource
from backend.logging import configure_logging
from backend.persistence.database import (
    check_database,
    create_database_engine,
    create_session_factory,
)
from backend.runtime.coordinator import ReadOnlyReconciler, RuntimeCoordinator
from backend.runtime.production import ProductionPaperComposition
from backend.runtime.reconciliation import OandaReadOnlyBrokerReader
from backend.runtime.store import SqlAlchemyRuntimeStore
from backend.strategies.production import create_production_strategy_registry

logger = logging.getLogger(__name__)


def stop_signal(event: threading.Event, _signum: int, _frame: object) -> None:
    event.set()


def _build_coordinator(settings: Any, engine: Any) -> RuntimeCoordinator | None:
    token = getattr(settings, "oanda_api_token", None)
    if token is None or not token.get_secret_value():
        # Without a server-side token there is no broker read authority.  The
        # process remains inert rather than guessing an account or activating.
        return None
    store = SqlAlchemyRuntimeStore(engine, create_session_factory(engine))
    registry = create_production_strategy_registry()
    reader = OandaReadOnlyBrokerReader(
        OandaPracticeReadOnlyClient(token),
        transaction_cursor=store.transaction_cursor,
    )
    reconciler = ReadOnlyReconciler(
        reader,
        local_facts=store.reconciliation_facts,
        repair=store.repair_reconciliation,
    )
    composition = ProductionPaperComposition(
        source=OandaHistoricalBarSource(
            token,
            connect_timeout_seconds=getattr(
                settings, "oanda_connect_timeout_seconds", 5
            ),
            read_timeout_seconds=getattr(settings, "oanda_read_timeout_seconds", 20),
        ),
        registry=registry,
        store=store,
        market=OANDA_CAPABILITY.market_specification(Instrument.EUR_USD),
        broker_reader=reader.read,
        # Capital-capable execution remains disabled until a separate explicit
        # activation approval supplies both a transport and this gate.
        capital_actions_enabled=False,
    )
    return RuntimeCoordinator(
        store,
        reconciler,
        owner_id=f"atlas-runtime-{os.getpid()}",
        acquire=store.acquire_lease,
        data_source=composition.data_source,
        restore_runtime=composition.restore_for_startup,
    )


def run(
    check_only: bool = False,
    stop_event: threading.Event | None = None,
    coordinator: RuntimeCoordinator | None = None,
) -> int:
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
    runtime = coordinator or _build_coordinator(settings, engine)
    try:
        if runtime is not None:
            runtime.startup()
        while not event.wait(getattr(settings, "runtime_poll_interval_seconds", 5)):
            if runtime is not None:
                runtime.cycle()
    except Exception as error:
        logger.error("atlas-runtime stopped safely: %s", type(error).__name__)
        return 1
    finally:
        if runtime is not None:
            runtime.shutdown()
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
