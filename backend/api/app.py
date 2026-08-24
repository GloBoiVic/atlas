from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.api.experiments import create_experiment_router
from backend.api.health import create_health_router
from backend.api.strategies import create_strategy_router
from backend.config import get_settings
from backend.experiments.configuration import ExperimentConfigurationService
from backend.experiments.lifecycle import (
    ExperimentRunService,
    LifecycleDiagnosticSink,
)
from backend.experiments.results import ExperimentResultReadService
from backend.experiments.runner import ExperimentRunner, RunnerComparisonDiagnosticSink
from backend.logging import configure_logging
from backend.persistence.database import create_database_engine, create_session_factory
from backend.persistence.strategy_catalog import synchronize_strategy_catalog
from backend.strategies.production import create_production_strategy_registry


def create_app(
    *,
    settings: Any | None = None,
    engine: Any | None = None,
    registry: Any | None = None,
    runner: Any | None = None,
    session_factory: Callable[[], Any] | None = None,
    lifecycle_diagnostic_sink: LifecycleDiagnosticSink | None = None,
    runner_diagnostic_sink: RunnerComparisonDiagnosticSink | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)
    engine = engine or create_database_engine(settings)
    session_factory = session_factory or create_session_factory(engine)
    registry = registry or create_production_strategy_registry(
        Path(__file__).resolve().parents[2]
    )
    runner = runner or ExperimentRunner(
        strategy_registry=registry, comparison_diagnostic_sink=runner_diagnostic_sink
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        try:
            synchronize_strategy_catalog(session_factory, registry)
            yield
        finally:
            engine.dispose()

    app = FastAPI(title="Atlas API", lifespan=lifespan)
    app.state.database_engine = engine
    app.state.session_factory = session_factory
    app.state.strategy_registry = registry
    app.state.experiment_configuration = ExperimentConfigurationService(registry)
    app.state.experiment_runner = runner
    app.state.experiment_lifecycle = ExperimentRunService(
        session_factory, runner, lifecycle_diagnostic_sink=lifecycle_diagnostic_sink
    )
    app.state.experiment_results = ExperimentResultReadService()
    app.include_router(create_health_router(engine))
    app.include_router(
        create_strategy_router(session_factory=session_factory, registry=registry)
    )
    app.include_router(
        create_experiment_router(
            session_factory=session_factory,
            configuration=app.state.experiment_configuration,
            lifecycle=app.state.experiment_lifecycle,
            results=app.state.experiment_results,
        )
    )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Any, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                    "details": {"fields": jsonable_encoder(exc.errors())},
                }
            },
        )

    return app
