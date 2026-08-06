from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes.analytics import router as analytics_router
from backend.api.routes.backtests import router as backtests_router
from backend.api.routes.journal import router as journal_router
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
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.API_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "PATCH", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.include_router(backtests_router)
    app.include_router(journal_router)
    app.include_router(analytics_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
