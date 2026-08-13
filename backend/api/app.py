from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.api.health import create_health_router
from backend.config import get_settings
from backend.logging import configure_logging
from backend.persistence.database import create_database_engine


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)
    engine = create_database_engine(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        engine.dispose()

    app = FastAPI(title="Atlas API", lifespan=lifespan)
    app.state.database_engine = engine
    app.include_router(create_health_router(engine))
    return app
