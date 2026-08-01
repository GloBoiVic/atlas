from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from backend.config import settings
from backend.core.logging import setup_logging

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    setup_logging()
    logger.info(
        "api_started",
        environment=settings.ATLAS_ENVIRONMENT.value,
        host=settings.API_HOST,
        port=settings.API_PORT,
    )
    yield
    logger.info("api_stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Atlas",
        description="Algorithmic trading platform",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
