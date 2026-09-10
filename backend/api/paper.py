"""Local-authority HTTP routes for explicit PAPER runtime control."""

from __future__ import annotations

import logging
from collections.abc import Callable, Generator
from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.paper.trade_history import (
    PaperTradeHistoryReadError,
    PaperTradeHistoryReadService,
)
from backend.persistence.database import session_scope
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
    PaperBrokerStateResponse,
    PaperCapabilityResponse,
    PaperRuntimeActivationResponse,
    PaperRuntimeActivationResultResponse,
    PaperRuntimeReconcileResponse,
    PaperRuntimeStatusResponse,
    PaperTradeHistoryResponse,
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


def create_paper_router(
    *,
    service: Any,
    broker_state_reader: Callable[[], Any] | None = None,
    session_factory: Callable[[], Any] | None = None,
    trade_history_service: PaperTradeHistoryReadService | None = None,
) -> APIRouter:
    """Create the local PAPER control/status surface over one service."""
    router = APIRouter(prefix="/api/v1/paper", tags=["paper"])
    history = trade_history_service or PaperTradeHistoryReadService()

    def session() -> Generator[Session]:
        if session_factory is None:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": {
                        "code": "PAPER_TRADE_HISTORY_UNAVAILABLE",
                        "message": "Completed PAPER Trade history is unavailable.",
                        "details": {},
                    }
                },
            )
        with session_scope(cast(Any, session_factory)) as db:
            yield db

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

    @router.get("/broker-state", response_model=PaperBrokerStateResponse)
    def broker_state() -> dict[str, object]:
        if broker_state_reader is None:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": {
                        "code": "PAPER_BROKER_STATE_UNAVAILABLE",
                        "message": "Current broker state is unavailable.",
                        "details": {},
                    }
                },
            )
        try:
            inventory = broker_state_reader()
        except Exception as error:  # noqa: BLE001
            # Known OANDA observation failures map to unavailable.
            from backend.integrations.oanda.source import OandaError

            if isinstance(error, OandaError):
                logger.warning(
                    "PAPER broker state unavailable: %s", type(error).__name__
                )
                raise HTTPException(
                    status_code=503,
                    detail={
                        "error": {
                            "code": "PAPER_BROKER_STATE_UNAVAILABLE",
                            "message": "Current broker state is unavailable.",
                            "details": {},
                        }
                    },
                ) from error
            logger.error("PAPER broker state internal error: %s", type(error).__name__)
            raise HTTPException(
                status_code=500,
                detail={
                    "error": {
                        "code": "PAPER_BROKER_STATE_INTERNAL_ERROR",
                        "message": "Current broker state could not be read.",
                        "details": {},
                    }
                },
            ) from error
        open_trades: list[dict[str, object]] = []
        for trade in inventory.trades:
            open_time_value = trade.open_time.isoformat().replace("+00:00", "Z")
            open_trades.append(
                {
                    "trade_id": trade.provider_trade_id,
                    "instrument": trade.provider_instrument,
                    "open_time": open_time_value,
                    "open_price": str(trade.open_price),
                    "current_units": str(trade.current_units),
                    "state": trade.state,
                    "unrealized_pl": str(trade.unrealized_pl),
                }
            )
        provider_value = (
            inventory.identity.provider.value
            if hasattr(inventory.identity.provider, "value")
            else str(inventory.identity.provider)
        )
        return {
            "provider": provider_value,
            "environment": str(inventory.identity.environment),
            "account_currency": str(inventory.identity.base_currency),
            "open_trades": open_trades,
        }

    @router.get("/trades", response_model=PaperTradeHistoryResponse)
    def trades(
        db: Session = Depends(session),  # noqa: B008
        limit: Annotated[int, Query(ge=1, le=50)] = 10,
    ) -> dict[str, object]:
        try:
            items = history.list(db, limit)
        except PaperTradeHistoryReadError as error:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": error.code,
                        "message": str(error),
                        "details": {},
                    }
                },
            ) from error
        except Exception as error:  # noqa: BLE001
            logger.error("PAPER Trade history route failed: %s", type(error).__name__)
            raise HTTPException(
                status_code=500,
                detail={
                    "error": {
                        "code": "PAPER_TRADE_HISTORY_INTERNAL_ERROR",
                        "message": "Completed PAPER Trade history could not be read.",
                        "details": {},
                    }
                },
            ) from error
        return {"items": [item.to_json() for item in items]}

    return router


__all__ = ["create_paper_router"]
