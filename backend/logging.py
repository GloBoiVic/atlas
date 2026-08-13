import logging

from backend.config import Settings


def configure_logging(settings: Settings) -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.value),
        format="%(levelname)s %(name)s: %(message)s",
    )
