import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from backend.api.app import create_app
from backend.config import Settings


@pytest.fixture
def app():
    return create_app()


@pytest.mark.asyncio
async def test_health_returns_ok(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_health_returns_json_content_type(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert "application/json" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_cors_allows_configured_frontend_origin(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert response.headers["access-control-allow-credentials"] == "true"


@pytest.mark.asyncio
async def test_cors_does_not_allow_unconfigured_origin(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health", headers={"Origin": "https://untrusted.example"})
    assert "access-control-allow-origin" not in response.headers


def test_cors_configuration_rejects_wildcard_origins_with_credentials():
    with pytest.raises(ValidationError, match="must not contain"):
        Settings(API_CORS_ORIGINS=["*"])
