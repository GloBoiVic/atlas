from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from backend.api.app import create_app
from backend.config import get_settings


def make_app() -> tuple[FastAPI, Engine]:
    get_settings.cache_clear()
    with patch.dict(
        "os.environ", {"ATLAS_DATABASE_URL": "postgresql+psycopg://u:p@localhost/atlas"}
    ):
        app = create_app()
    return app, app.state.database_engine


def test_liveness_does_not_check_database() -> None:
    app, _ = make_app()
    with patch("backend.api.health.check_database") as check:
        with TestClient(app) as client:
            response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "atlas-api"}
    check.assert_not_called()


def test_readiness_success() -> None:
    app, _ = make_app()
    with patch("backend.api.health.check_database"):
        with TestClient(app) as client:
            response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "service": "atlas-api",
        "checks": {"database": "ok"},
    }


def test_readiness_failure_is_sanitized() -> None:
    app, _ = make_app()
    with patch(
        "backend.api.health.check_database",
        side_effect=RuntimeError("secret database password"),
    ):
        with TestClient(app) as client:
            response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "service": "atlas-api",
        "checks": {"database": "unavailable"},
    }
    assert "secret" not in response.text


def test_lifespan_disposes_engine() -> None:
    app, engine = make_app()
    engine.dispose = Mock()  # type: ignore[method-assign]
    with TestClient(app):
        pass
    engine.dispose.assert_called_once()
