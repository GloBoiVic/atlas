from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from backend.api.local_authority import LocalAuthorityMiddleware
from backend.api.paper import create_paper_router
from backend.api.schemas import PaperRuntimeActivationResponse
from backend.domain import FinancialPositionState, ValidatedParameterPayload
from backend.runtime import (
    PaperRuntimeActivation,
    PaperRuntimeActivationResult,
    PaperRuntimeLifecycleState,
    PaperRuntimeOperationalPhase,
    PaperRuntimeStatus,
    runtime_parameter_fingerprint,
)
from backend.runtime.activation import PaperRuntimeServiceError

ACTIVATION_ID = UUID("11111111-1111-1111-1111-111111111111")
VERSION_ID = UUID("22222222-2222-2222-2222-222222222222")
ATTEMPT_ID = UUID("33333333-3333-3333-3333-333333333333")
REQUESTED_AT = datetime(2026, 9, 3, 8, tzinfo=timezone(timedelta(hours=-4)))
EXPECTED_REQUESTED_AT = "2026-09-03T12:00:00Z"


def _activation(
    lifecycle_state: PaperRuntimeLifecycleState = PaperRuntimeLifecycleState.RUNNING,
) -> PaperRuntimeActivation:
    parameters = ValidatedParameterPayload.from_mapping((), {})
    return PaperRuntimeActivation(
        activation_id=ACTIVATION_ID,
        strategy_version_id=VERSION_ID,
        strategy_key="runtime_fixture",
        strategy_version_number=1,
        source_fingerprint="a" * 64,
        implementation_key="runtime_fixture.v1",
        validated_parameter_snapshot=parameters,
        parameter_fingerprint=runtime_parameter_fingerprint(parameters),
        risk_per_trade=Decimal("0.0100"),
        provider_account_id="001-002-003-004",
        requested_at=REQUESTED_AT,
        lifecycle_state=lifecycle_state,
        operational_phase=PaperRuntimeOperationalPhase.WAITING_FRONTIER,
    )


class _PaperService:
    def __init__(self) -> None:
        self.activation_requests: list[object] = []
        self.stop_requests: list[tuple[UUID, object]] = []
        self.reconcile_ids: list[UUID] = []
        self.activation = _activation()

    def capability(self):
        return SimpleNamespace(
            to_json=lambda: {
                "provider": "OANDA",
                "environment": "PRACTICE",
                "base_currency": "USD",
                "instrument": "EUR_USD",
                "analytical_resolution": "M15",
                "analytical_price_component": "MID",
                "poll_interval_seconds": 15,
                "token_configured": True,
                "account_configured": True,
                "configured_account_id": "001-002-003-004",
                "available": True,
                "reason_code": None,
                "activation_required": True,
            }
        )

    def activate(self, request: object):
        self.activation_requests.append(request)
        return PaperRuntimeActivationResult(
            activation=self.activation,
            replayed=False,
        )

    def get_active(self) -> PaperRuntimeActivation | None:
        return self.activation

    def status(self, activation_id: UUID):
        return PaperRuntimeStatus(
            activation=replace(self.activation, activation_id=activation_id),
            current_financial_position_state=FinancialPositionState.LONG,
            execution_outcome="FILLED_PROTECTED",
            reconciliation_status="LIFECYCLE_ADVANCED",
        )

    def stop(self, activation_id: UUID, request: object):
        self.stop_requests.append((activation_id, request))
        return replace(
            self.activation,
            activation_id=activation_id,
            lifecycle_state=PaperRuntimeLifecycleState.STOP_REQUESTED,
        )

    def reconcile(self, activation_id: UUID):
        self.reconcile_ids.append(activation_id)
        return SimpleNamespace(
            to_json=lambda: {
                "activation_id": str(activation_id),
                "attempt_id": str(ATTEMPT_ID),
                "performed": True,
                "reconciliation_status": "UNRESOLVED",
                "execution_outcome": "UNKNOWN",
                "stale": True,
            }
        )


def _app(service: object, *, peer: str = "127.0.0.1") -> FastAPI:
    app = FastAPI()
    app.add_middleware(LocalAuthorityMiddleware, peer_address_resolver=lambda _: peer)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                    "details": {
                        "fields": [
                            {
                                "loc": [str(item) for item in error["loc"]],
                                "type": error["type"],
                                "msg": error["msg"],
                            }
                            for error in exc.errors()
                        ]
                    },
                }
            },
        )

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, exc: HTTPException):
        detail = exc.detail
        content = (
            detail
            if isinstance(detail, dict) and "error" in detail
            else {
                "error": {
                    "code": f"HTTP_{exc.status_code}",
                    "message": str(detail),
                    "details": {},
                }
            }
        )
        return JSONResponse(
            status_code=exc.status_code, content=jsonable_encoder(content)
        )

    app.include_router(create_paper_router(service=service))
    return app


def test_paper_routes_project_all_control_and_status_seams() -> None:
    service = _PaperService()
    with TestClient(_app(service), base_url="http://localhost") as client:
        capability = client.get("/api/v1/paper/capability")
        activation = client.post(
            "/api/v1/paper/activations",
            json={
                "activationRequestId": str(ACTIVATION_ID),
                "strategyVersionId": str(VERSION_ID),
                "parameters": {},
                "riskPerTrade": "0.0100",
                "confirmation": "ACTIVATE_PAPER",
            },
        )
        active = client.get("/api/v1/paper/activations/active")
        detail = client.get(f"/api/v1/paper/activations/{ACTIVATION_ID}")
        stopped = client.post(
            f"/api/v1/paper/activations/{ACTIVATION_ID}/stop",
            json={"reason": "operator requested stop"},
        )
        reconciled = client.post(f"/api/v1/paper/activations/{ACTIVATION_ID}/reconcile")

    assert capability.status_code == 200
    assert capability.json()["activationRequired"] is True
    assert activation.status_code == 200
    assert activation.json()["activation"]["requestedAt"] == EXPECTED_REQUESTED_AT
    assert isinstance(activation.json()["activation"]["riskPerTrade"], str)
    assert activation.json()["activation"]["riskPerTrade"] == "0.01"
    assert active.status_code == detail.status_code == 200
    assert active.json()["activation"]["requestedAt"] == EXPECTED_REQUESTED_AT
    assert detail.json()["activation"]["requestedAt"] == EXPECTED_REQUESTED_AT
    assert isinstance(active.json()["activation"]["riskPerTrade"], str)
    assert active.json()["activation"]["riskPerTrade"] == "0.01"
    assert isinstance(detail.json()["activation"]["riskPerTrade"], str)
    assert detail.json()["activation"]["riskPerTrade"] == "0.01"
    assert active.json()["currentFinancialPositionState"] == "LONG"
    assert active.json()["terminalRuntimeStateDoesNotProveFlat"] is True
    assert stopped.status_code == 200
    assert stopped.json()["requestedAt"] == EXPECTED_REQUESTED_AT
    assert isinstance(stopped.json()["riskPerTrade"], str)
    assert stopped.json()["riskPerTrade"] == "0.01"
    assert stopped.json()["lifecycleState"] == "STOP_REQUESTED"
    assert reconciled.status_code == 200
    assert reconciled.json()["executionOutcome"] == "UNKNOWN"
    assert len(service.activation_requests) == 1
    assert service.stop_requests[0][0] == ACTIVATION_ID
    assert service.reconcile_ids == [ACTIVATION_ID]


def test_real_activation_projection_restores_requested_at_and_decimal_contract() -> (
    None
):
    activation = _activation()

    projection = activation.to_json()
    assert projection["requested_at"] == EXPECTED_REQUESTED_AT
    assert projection["risk_per_trade"] == "0.01"

    response = PaperRuntimeActivationResponse.model_validate(projection)
    serialized = response.model_dump(by_alias=True, mode="json")
    assert serialized["requestedAt"] == EXPECTED_REQUESTED_AT
    assert isinstance(serialized["riskPerTrade"], str)
    assert serialized["riskPerTrade"] == "0.01"
    assert "requested_at" not in activation.immutable_json()


def test_paper_activation_contract_rejects_numbers_and_unknown_fields() -> None:
    service = _PaperService()
    with TestClient(_app(service), base_url="http://localhost") as client:
        base = {
            "activationRequestId": str(ACTIVATION_ID),
            "strategyVersionId": str(VERSION_ID),
            "parameters": {},
            "riskPerTrade": "0.01",
            "confirmation": "ACTIVATE_PAPER",
        }
        number = client.post(
            "/api/v1/paper/activations", json={**base, "riskPerTrade": 0.01}
        )
        secret = "top-secret-token"
        unknown = client.post(
            "/api/v1/paper/activations", json={**base, "token": secret}
        )

    assert number.status_code == 422
    assert unknown.status_code == 422
    assert secret not in unknown.text
    assert service.activation_requests == []


def test_paper_routes_require_actual_local_peer_and_redact_unexpected_errors() -> None:
    service = _PaperService()
    with TestClient(
        _app(service, peer="10.0.0.1"), base_url="http://localhost"
    ) as client:
        denied = client.get("/api/v1/paper/capability")
    assert denied.status_code == 403
    assert "LOCAL_PEER_REQUIRED" in denied.text

    class FailingService(_PaperService):
        def capability(self):
            raise RuntimeError("provider payload contains top-secret-token")

    with TestClient(_app(FailingService()), base_url="http://localhost") as client:
        failed = client.get("/api/v1/paper/capability")
    assert failed.status_code == 500
    assert failed.json() == {
        "error": {
            "code": "PAPER_RUNTIME_INTERNAL_ERROR",
            "message": "PAPER runtime operation could not be completed.",
            "details": {},
        }
    }
    assert "top-secret-token" not in failed.text


def test_paper_routes_redact_service_error_messages() -> None:
    class LeakingService(_PaperService):
        def capability(self):
            raise PaperRuntimeServiceError(
                "PAPER_RUNTIME_INTERNAL_ERROR",
                "raw provider payload contains top-secret-token",
            )

    with TestClient(_app(LeakingService()), base_url="http://localhost") as client:
        failed = client.get("/api/v1/paper/capability")

    assert failed.status_code == 500
    assert failed.json() == {
        "error": {
            "code": "PAPER_RUNTIME_INTERNAL_ERROR",
            "message": "PAPER runtime operation could not be completed.",
            "details": {},
        }
    }
    assert "top-secret-token" not in failed.text


def test_paper_active_and_detail_routes_use_safe_not_found_contracts() -> None:
    class NoActivationService(_PaperService):
        def get_active(self):
            return None

        def status(self, activation_id: UUID):
            raise PaperRuntimeServiceError(
                "ACTIVATION_NOT_FOUND", "activation was not found"
            )

    with TestClient(_app(NoActivationService()), base_url="http://localhost") as client:
        active = client.get("/api/v1/paper/activations/active")
        detail = client.get(f"/api/v1/paper/activations/{ACTIVATION_ID}")

    assert active.status_code == 404
    assert active.json()["error"]["code"] == "PAPER_ACTIVATION_NOT_ACTIVE"
    assert detail.status_code == 404
    assert detail.json()["error"]["code"] == "ACTIVATION_NOT_FOUND"


def test_paper_service_errors_map_to_safe_contract_status() -> None:
    class ConflictService(_PaperService):
        def activate(self, request: object):
            raise PaperRuntimeServiceError(
                "ACTIVATION_IDENTITY_CONFLICT",
                "activation request identity conflicts with durable evidence",
            )

    with TestClient(_app(ConflictService()), base_url="http://localhost") as client:
        response = client.post(
            "/api/v1/paper/activations",
            json={
                "activationRequestId": str(ACTIVATION_ID),
                "strategyVersionId": str(VERSION_ID),
                "parameters": {},
                "riskPerTrade": "0.01",
                "confirmation": "ACTIVATE_PAPER",
            },
        )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ACTIVATION_IDENTITY_CONFLICT"
