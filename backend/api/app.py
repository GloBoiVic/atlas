from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.dashboard_schemas import DashboardSummaryResponse, dashboard_response
from backend.api.deps import AnalyticsScope, get_analytics_scope, get_dashboard_read_service
from backend.api.operational_ws import (
    DenyByDefaultAuthenticator,
    OperationalConnectionManager,
    OperationalProjector,
)
from backend.api.routes.analytics import router as analytics_router
from backend.api.routes.backtests import router as backtests_router
from backend.api.routes.bots import router as bots_router
from backend.api.routes.dashboard import router as dashboard_router
from backend.api.routes.journal import router as journal_router
from backend.api.routes.operational_ws import router as operational_ws_router
from backend.config import settings
from backend.core.events import EventBus
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
    projector = getattr(app.state, "operational_projector", None)
    if projector is not None:
        await projector.close()
    logger.info("api_stopped")


def create_app(event_bus: EventBus | None = None) -> FastAPI:
    """Create the API, optionally attaching the host process's existing EventBus."""
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
    app.include_router(bots_router)
    app.include_router(journal_router)
    app.include_router(analytics_router)
    app.include_router(dashboard_router)
    if settings.ENABLE_DEFERRED_OPERATIONAL_WEBSOCKET:
        # This is an explicit escape hatch for deferred protocol testing only.  It is
        # deliberately not enabled by Docker/default settings and is not an MVP path:
        # API/worker EventBus instances are separate, and Cloudflare Access auth/proxy
        # wiring, unique state-envelope IDs, and send timeouts are still required.
        app.include_router(operational_ws_router)
        app.state.operational_event_bus = event_bus or EventBus()
        app.state.operational_connection_manager = OperationalConnectionManager()
        app.state.operational_projector = OperationalProjector(
            app.state.operational_event_bus,
            app.state.operational_connection_manager,
        )
        # Cloudflare Access authentication must be supplied by the deployment.  The API
        # remains fail-closed until a verifier is wired here.
        app.state.operational_authenticator = DenyByDefaultAuthenticator()
        app.state.operational_scope_provider = get_analytics_scope
    else:
        logger.info(
            "operational_websocket_disabled",
            reason="deferred until cross_process_bridge_and_deployment_auth_are_approved",
        )

    async def snapshot_provider(scope: AnalyticsScope) -> DashboardSummaryResponse:
        service = get_dashboard_read_service()
        return dashboard_response(await service.get_dashboard_summary(scope, trade_limit=10))

    if settings.ENABLE_DEFERRED_OPERATIONAL_WEBSOCKET:
        app.state.operational_snapshot_provider = snapshot_provider

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
