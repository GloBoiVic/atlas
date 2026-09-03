import argparse
import logging
import signal
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, cast

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from backend.config import Settings
from backend.integrations.oanda import (
    OandaHistoricalBarSource,
    OandaPracticeAccountPropertiesReader,
    OandaPracticeEntryMutation,
    OandaPracticeEntryReadbackReader,
    OandaPracticeEurUsdPricingReader,
    OandaPracticeExecutionAccountReader,
    OandaPracticeExecutionInstrumentReader,
    OandaPracticeMutationRequester,
    OandaPracticeProtectionCompletion,
    OandaPracticeReconciliationReader,
    is_valid_oanda_practice_account_id,
)
from backend.logging import configure_logging
from backend.paper.durable_execution import PaperDurableExecutionApplication
from backend.paper.reconciliation import PaperReconciliationCoordinator
from backend.persistence.database import (
    check_database,
    create_database_engine,
    create_session_factory,
)
from backend.persistence.paper_execution_repository import PaperExecutionRepository
from backend.persistence.runtime_repository import PaperRuntimeRepository
from backend.runtime.orchestration import PaperRuntimeOrchestrator
from backend.runtime.ownership import PaperRuntimeOwner
from backend.strategies.production import create_production_strategy_registry
from backend.strategies.registry import StrategyRegistry

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], Session]


class StopEvent(Protocol):
    def is_set(self) -> object: ...

    def wait(self, timeout: float) -> object: ...


class OrchestratorFactory(Protocol):
    def __call__(
        self,
        *,
        settings: Settings,
        engine: Engine,
        session_factory: SessionFactory,
    ) -> PaperRuntimeOrchestrator: ...


def create_runtime_orchestrator(
    settings: Settings,
    engine: Engine,
    session_factory: SessionFactory,
    *,
    registry: StrategyRegistry | None = None,
) -> PaperRuntimeOrchestrator:
    """Compose the supported local OANDA Practice PAPER runtime explicitly."""
    strategy_registry = (
        registry
        if registry is not None
        else create_production_strategy_registry(Path(__file__).resolve().parents[2])
    )
    runtime_repository = PaperRuntimeRepository()
    paper_repository = PaperExecutionRepository()
    account_id = settings.oanda_account_id
    token = settings.oanda_api_token
    connect_timeout = settings.oanda_connect_timeout_seconds
    read_timeout = settings.oanda_read_timeout_seconds
    account_properties_reader = OandaPracticeAccountPropertiesReader(
        token,
        account_id,
        connect_timeout_seconds=connect_timeout,
        read_timeout_seconds=read_timeout,
    )

    analytical_source = OandaHistoricalBarSource(
        token,
        connect_timeout_seconds=connect_timeout,
        read_timeout_seconds=read_timeout,
    )
    account_reader = OandaPracticeExecutionAccountReader(
        token,
        account_id,
        connect_timeout_seconds=connect_timeout,
        read_timeout_seconds=read_timeout,
    )

    durable_execution: PaperDurableExecutionApplication | None = None
    reconciliation: PaperReconciliationCoordinator | None = None
    if is_valid_oanda_practice_account_id(account_id):
        configured_account_id = cast(str, account_id)
        entry_readback = OandaPracticeEntryReadbackReader(
            token,
            configured_account_id,
            connect_timeout_seconds=connect_timeout,
            read_timeout_seconds=read_timeout,
        )
        mutation_requester = OandaPracticeMutationRequester(
            token,
            connect_timeout_seconds=connect_timeout,
            read_timeout_seconds=read_timeout,
        )
        durable_execution = PaperDurableExecutionApplication(
            repository=paper_repository,
            session_factory=session_factory,
            account_properties_reader=account_properties_reader,
            execution_account_reader=OandaPracticeExecutionAccountReader(
                token,
                configured_account_id,
                connect_timeout_seconds=connect_timeout,
                read_timeout_seconds=read_timeout,
            ),
            execution_instrument_reader=OandaPracticeExecutionInstrumentReader(
                token,
                configured_account_id,
                connect_timeout_seconds=connect_timeout,
                read_timeout_seconds=read_timeout,
            ),
            pricing_reader_factory=lambda identity: OandaPracticeEurUsdPricingReader(
                token,
                identity,
                connect_timeout_seconds=connect_timeout,
                read_timeout_seconds=read_timeout,
            ),
            entry_mutation=OandaPracticeEntryMutation(
                mutation_requester, readback=entry_readback
            ),
            protection_completion=OandaPracticeProtectionCompletion(
                mutation_requester, entry_readback
            ),
        )
        reconciliation = PaperReconciliationCoordinator(
            repository=paper_repository,
            session_factory=session_factory,
            provider=OandaPracticeReconciliationReader(
                token,
                configured_account_id,
                connect_timeout_seconds=connect_timeout,
                read_timeout_seconds=read_timeout,
            ),
        )

    owner = PaperRuntimeOwner(
        engine,
        session_factory,
        repository=runtime_repository,
    )
    return PaperRuntimeOrchestrator(
        owner=owner,
        session_factory=session_factory,
        strategy_registry=strategy_registry,
        analytical_source=analytical_source,
        account_reader=account_reader,
        capability_reader=account_properties_reader,
        runtime_repository=runtime_repository,
        durable_execution=durable_execution,
        reconciliation=reconciliation,
    )


def stop_signal(event: threading.Event, _signum: int, _frame: object) -> None:
    event.set()


def run(
    check_only: bool = False,
    stop_event: StopEvent | None = None,
    orchestrator_factory: OrchestratorFactory | None = None,
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
    if event.is_set():
        logger.info("atlas-runtime shutting down")
        engine.dispose()
        return 0

    runtime: PaperRuntimeOrchestrator | None = None
    try:
        session_factory = create_session_factory(engine)
        factory = orchestrator_factory or create_runtime_orchestrator
        runtime = factory(
            settings=settings,
            engine=engine,
            session_factory=session_factory,
        )
        return runtime.run(event)
    except Exception as error:
        logger.error("atlas-runtime execution failed: %s", type(error).__name__)
        if runtime is not None:
            try:
                runtime.close()
            except Exception:
                logger.error("atlas-runtime cleanup failed")
        return 1
    finally:
        logger.info("atlas-runtime shutting down")
        engine.dispose()


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
