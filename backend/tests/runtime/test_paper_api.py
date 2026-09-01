from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.paper import create_paper_router

DEPLOYMENT_ID = uuid4()


class Transaction:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class Database:
    def begin(self):
        return Transaction()

    def close(self):
        pass


class Repository:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def request_state(self, db, deployment_id: UUID, desired_state: str):
        assert deployment_id == DEPLOYMENT_ID
        self.calls.append(desired_state)
        return SimpleNamespace(
            id=deployment_id,
            desired_state=desired_state,
            actual_state="DRAFT",
            safety_reason=None,
        )


def app_with(repository: Repository) -> FastAPI:
    app = FastAPI()

    def factory():
        return Database()

    app.include_router(
        create_paper_router(session_factory=factory, repository=repository)
    )
    return app


def test_start_is_accepted_as_desired_state_and_does_not_claim_running() -> None:
    repository = Repository()
    with TestClient(app_with(repository)) as client:
        response = client.post(
            f"/api/v1/paper/deployments/{DEPLOYMENT_ID}/control",
            json={"command": "START"},
        )

    assert response.status_code == 202
    assert response.json() == {
        "deploymentId": str(DEPLOYMENT_ID),
        "desiredState": "RUNNING",
        "actualState": "DRAFT",
        "safetyReason": None,
    }
    assert repository.calls == ["RUNNING"]


def test_invalid_command_is_rejected_without_persistence() -> None:
    repository = Repository()
    with TestClient(app_with(repository)) as client:
        response = client.post(
            f"/api/v1/paper/deployments/{DEPLOYMENT_ID}/control",
            json={"command": "SUBMIT_ORDER"},
        )

    assert response.status_code == 422
    assert repository.calls == []
