"""Atlas worker entrypoint for background tasks."""
import asyncio
import signal

import structlog

from backend.config import settings
from backend.core.logging import setup_logging
from backend.worker.supervisor import BotSupervisor

logger = structlog.get_logger()
shutdown_event = asyncio.Event()


def handle_signal(signum: int, frame: object) -> None:
    logger.info("worker_shutdown_signal", signal=signum)
    shutdown_event.set()


async def run_worker(supervisor: BotSupervisor | None = None) -> None:
    """Run worker tasks and own the lifecycle of an injected supervisor.

    The worker does not construct a supervisor because its repositories, pipeline factory,
    reconciler, clock, and event bus are application-specific dependencies.
    """
    logger.info(
        "worker_started",
        environment=settings.ATLAS_ENVIRONMENT.value,
        supervisor_configured=supervisor is not None,
    )
    try:
        if supervisor is not None:
            await supervisor.restore_active()
        while not shutdown_event.is_set():
            await asyncio.sleep(1)
    finally:
        if supervisor is not None:
            try:
                await supervisor.shutdown()
            except BaseException:
                logger.exception("worker_supervisor_shutdown_failed")
                raise
        logger.info("worker_stopped")


def main() -> None:
    setup_logging()
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
