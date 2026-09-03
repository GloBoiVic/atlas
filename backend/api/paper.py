"""Local-authority HTTP routes for explicit PAPER runtime control."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException

from backend.runtime.activation import (
    PaperActivationRequest,
    PaperRuntimeConfigurationError,
    PaperRuntimeControlConflict,
    PaperRuntimeServiceError,
    PaperStopRequest,
)

from .schemas import (
    PaperActivationRequest as PaperActivationHttpRequest,
)
from .schemas import (
    PaperCapabilityResponse,
    PaperRuntimeActivationResponse,
    PaperRuntimeActivationResultResponse,
    PaperRuntimeReconcileResponse,
    PaperRuntimeStatusResponse,
)
from .schemas import (
    PaperStopRequest as PaperStopHttpRequest,
)

logger = logging.getLogger(__name__)

_NOT_FOUND_CODES = frozenset(
    {"ACTIVATION_NOT_FOUND", "RECONCILIATION_ATTEMPT_NOT_FOUND"}
)
_CONFLICT_CODES = frozenset(
    {
        "ACTIVATION_IDENTITY_CONFLICT",
        "PAPER_ACTIVATION_ALREADY_PRESENT",
        "PAPER_ATTEMPT_UNSAFE",
        "STOP_CONFLICT",
        "RUNTIME_RECONCILIATION_BUSY",
    }
)
_UNSAFE_MESSAGE_MARKERS = (
    "authorization",
    "credential",
    "password",
    "payload",
    "provider body",
    "raw body",
    "secret",
    "token",
)
_SAFE_FALLBACK_MESSAGE = "PAPER runtime operation could not be completed."


def _http_error(error: PaperRuntimeServiceError) -> HTTPException:
    if error.code in _NOT_FOUND_CODES:
        code_status = 404
    elif isinstance(error, PaperRuntimeConfigurationError) or error.code in {
        "ACTIVATION_REQUEST_INVALID",
        "STOP_REQUEST_INVALID",
    }:
        code_status = 422
    elif (
        isinstance(error, PaperRuntimeControlConflict) or error.code in _CONFLICT_CODES
    ):
        code_status = 409
    elif error.code == "RECONCILIATION_UNAVAILABLE":
        code_status = 503
    elif error.code == "RECONCILIATION_FAILED":
        code_status = 502
    else:
        code_status = 500

    message = str(error)
    lowered_message = message.lower()
    if (
        not message
        or len(message) > 500
        or any(ord(character) < 32 for character in message)
        or any(marker in lowered_message for marker in _UNSAFE_MESSAGE_MARKERS)
    ):
        message = _SAFE_FALLBACK_MESSAGE
    return HTTPException(
        status_code=code_status,
        detail={"error": {"code": error.code, "message": message, "details": {}}},
    )


def _invoke[Result](operation: Callable[[], Result]) -> Result:
    """Run a service call without leaking implementation/provider exceptions."""
    try:
        return operation()
    except PaperRuntimeServiceError as error:
        raise _http_error(error) from error
    except Exception as error:
        logger.error("PAPER runtime route failed: %s", type(error).__name__)
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "PAPER_RUNTIME_INTERNAL_ERROR",
                    "message": _SAFE_FALLBACK_MESSAGE,
                    "details": {},
                }
            },
        ) from error


def create_paper_router(*, service: Any) -> APIRouter:
    """Create the local PAPER control/status surface over one service."""
    router = APIRouter(prefix="/api/v1/paper", tags=["paper"])

    @router.get("/capability", response_model=PaperCapabilityResponse)
    def capability() -> dict[str, object]:
        return _invoke(lambda: service.capability().to_json())

    @router.post("/activations", response_model=PaperRuntimeActivationResultResponse)
    def activate(request: PaperActivationHttpRequest) -> dict[str, object]:
        typed_request = PaperActivationRequest(
            activation_request_id=request.activation_request_id,
            strategy_version_id=request.strategy_version_id,
            parameters=request.parameters,
            risk_per_trade=request.risk_per_trade,
            confirmation=request.confirmation,
        )
        result = _invoke(lambda: service.activate(typed_request))
        return result.to_json()

    @router.get("/activations/active", response_model=PaperRuntimeStatusResponse)
    def active() -> dict[str, object]:
        activation = _invoke(service.get_active)
        if activation is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": {
                        "code": "PAPER_ACTIVATION_NOT_ACTIVE",
                        "message": "No PAPER activation is active.",
                        "details": {},
                    }
                },
            )
        status = _invoke(lambda: service.status(activation.activation_id))
        return status.to_json()

    @router.get(
        "/activations/{activation_id}", response_model=PaperRuntimeStatusResponse
    )
    def detail(activation_id: UUID) -> dict[str, object]:
        return _invoke(lambda: service.status(activation_id)).to_json()

    @router.post(
        "/activations/{activation_id}/stop",
        response_model=PaperRuntimeActivationResponse,
    )
    def stop(request: PaperStopHttpRequest, activation_id: UUID) -> dict[str, object]:
        typed_request = PaperStopRequest(request.reason)
        return _invoke(lambda: service.stop(activation_id, typed_request)).to_json()

    @router.post(
        "/activations/{activation_id}/reconcile",
        response_model=PaperRuntimeReconcileResponse,
    )
    def reconcile(activation_id: UUID) -> dict[str, object]:
        return _invoke(lambda: service.reconcile(activation_id)).to_json()

    return router


__all__ = ["create_paper_router"]
