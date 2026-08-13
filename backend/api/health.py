import logging
from typing import TypedDict

from fastapi import APIRouter, Response, status
from sqlalchemy import Engine

from backend.persistence.database import check_database

logger = logging.getLogger(__name__)


class HealthResponse(TypedDict):
    status: str
    service: str
    checks: dict[str, str]


def create_health_router(engine: Engine) -> APIRouter:
    router = APIRouter(prefix="/health")

    @router.get("/live")
    def live() -> dict[str, str]:
        return {"status": "ok", "service": "atlas-api"}

    @router.get("/ready")
    def ready(response: Response) -> HealthResponse:
        try:
            check_database(engine)
        except Exception as error:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            logger.warning("database readiness check failed: %s", type(error).__name__)
            return {
                "status": "not_ready",
                "service": "atlas-api",
                "checks": {"database": "unavailable"},
            }
        return {"status": "ready", "service": "atlas-api", "checks": {"database": "ok"}}

    return router
