# ruff: noqa: B008

"""Loopback PAPER control boundary.

HTTP owns durable desired-state commands only.  The atlas-runtime process owns
locks, broker reads, reconciliation, and actual-state transitions.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from backend.persistence.database import session_scope
from backend.persistence.paper_repository import DeploymentRepository
from backend.runtime.coordinator import RuntimeCommand

from .schemas import PaperControlRequest, PaperControlResponse


def _error(code: str, message: str, http_status: int = 409) -> HTTPException:
    return HTTPException(
        http_status,
        {"error": {"code": code, "message": message, "details": {}}},
    )


def create_paper_router(
    *, session_factory: Any, repository: DeploymentRepository | None = None
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/paper", tags=["paper"])
    repository = repository or DeploymentRepository()

    def session() -> Any:
        with session_scope(session_factory) as db:
            yield db

    @router.post(
        "/deployments/{deployment_id}/control",
        response_model=PaperControlResponse,
        status_code=status.HTTP_202_ACCEPTED,
    )
    def control(
        deployment_id: UUID,
        request: PaperControlRequest,
        db: Any = Depends(session),
    ) -> dict[str, object]:
        try:
            command = RuntimeCommand(request.command.upper())
        except ValueError as error:
            raise _error(
                "INVALID_COMMAND", "Unsupported PAPER control command", 422
            ) from error
        if command is RuntimeCommand.RECONCILE:
            raise _error(
                "RUNTIME_COMMAND_REQUIRED",
                "Reconciliation is performed by the owning runtime",
                409,
            )
        desired = {
            RuntimeCommand.START: "RUNNING",
            RuntimeCommand.RESUME: "RUNNING",
            RuntimeCommand.PAUSE: "PAUSED",
            RuntimeCommand.STOP: "STOPPED",
            RuntimeCommand.ARCHIVE: "ARCHIVED",
        }[command]
        try:
            with db.begin():
                row = repository.request_state(db, deployment_id, desired)
        except ValueError as error:
            message = str(error)
            raise _error(
                "DEPLOYMENT_NOT_FOUND"
                if "does not exist" in message
                else "INVALID_STATE",
                message,
                404 if "does not exist" in message else 409,
            ) from error
        return {
            "deployment_id": row.id,
            "desired_state": row.desired_state,
            "actual_state": row.actual_state,
            "safety_reason": row.safety_reason,
        }

    return router


__all__ = ["create_paper_router"]
