import os
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.parse import urlparse

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from backend.api.app import create_app
from backend.config import get_settings


def _configured_test_database_url() -> str:
    database_url = os.environ.get("ATLAS_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("ATLAS_TEST_DATABASE_URL is not configured")
    database_name = urlparse(database_url).path.rsplit("/", 1)[-1]
    if not database_name.endswith("_test"):
        pytest.fail("API health tests require a database name ending in _test")
    return database_url


@pytest.fixture(scope="session", autouse=True)
def ensure_test_schema() -> None:
    database_url = _configured_test_database_url()
    config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
    config.set_main_option("script_location", "backend/persistence/migrations")
    with patch.dict(os.environ, {"ATLAS_DATABASE_URL": database_url}):
        get_settings.cache_clear()
        command.upgrade(config, "head")


def make_app() -> tuple[FastAPI, Engine]:
    get_settings.cache_clear()
    database_url = _configured_test_database_url()
    with patch.dict("os.environ", {"ATLAS_DATABASE_URL": database_url}):
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
