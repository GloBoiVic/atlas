from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.api.experiments import create_experiment_router
from backend.api.health import create_health_router
from backend.api.historical_data import create_historical_data_router
from backend.api.local_authority import LocalAuthorityMiddleware, PeerAddressResolver
from backend.api.paper import create_paper_router
from backend.api.strategies import create_strategy_router
from backend.config import get_settings
from backend.domain.market_data import Instrument
from backend.experiments.configuration import ExperimentConfigurationService
from backend.experiments.lifecycle import (
    ExperimentRunService,
    LifecycleDiagnosticSink,
)
from backend.experiments.results import ExperimentResultReadService
from backend.experiments.runner import ExperimentRunner
from backend.integrations.oanda.capabilities import OANDA_CAPABILITY
from backend.integrations.oanda.source import OandaHistoricalBarSource
from backend.logging import configure_logging
from backend.market_data.historical_load import HistoricalDataLoadCoordinator
from backend.market_data.ingestion import MarketDataService
from backend.persistence.database import create_database_engine, create_session_factory
from backend.persistence.experiment_deletion import ExperimentDeletionService
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
    historical_coordinator: Any | None = None,
    peer_address_resolver: PeerAddressResolver | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)
    engine = engine or create_database_engine(settings)
    session_factory = session_factory or create_session_factory(engine)
    registry = registry or create_production_strategy_registry(
        Path(__file__).resolve().parents[2]
    )
    market_specification = OANDA_CAPABILITY.market_specification(Instrument.EUR_USD)
    runner = runner or ExperimentRunner(
        strategy_registry=registry, market_specification=market_specification
    )
    if historical_coordinator is None:
        source = OandaHistoricalBarSource(
            settings.oanda_api_token,
            connect_timeout_seconds=settings.oanda_connect_timeout_seconds,
            read_timeout_seconds=settings.oanda_read_timeout_seconds,
        )
        historical_coordinator = HistoricalDataLoadCoordinator(
            session_factory,
            MarketDataService(session_factory, source),
            ExperimentConfigurationService(registry),
            registry,
        )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        try:
            synchronize_strategy_catalog(session_factory, registry)
            with session_factory() as db:
                with db.begin():
                    historical_coordinator.repository.recover_interrupted(db)
            yield
        finally:
            engine.dispose()

    app = FastAPI(title="Atlas API", lifespan=lifespan)
    app.add_middleware(
        LocalAuthorityMiddleware,
        **(
            {"peer_address_resolver": peer_address_resolver}
            if peer_address_resolver is not None
            else {}
        ),
    )
    app.state.database_engine = engine
    app.state.session_factory = session_factory
    app.state.strategy_registry = registry
    app.state.experiment_configuration = ExperimentConfigurationService(registry)
    app.state.experiment_runner = runner
    app.state.experiment_lifecycle = ExperimentRunService(
        session_factory, runner, lifecycle_diagnostic_sink=lifecycle_diagnostic_sink
    )
    app.state.experiment_results = ExperimentResultReadService()
    app.state.experiment_deletion = ExperimentDeletionService()
    app.state.historical_data_coordinator = historical_coordinator
    app.include_router(create_health_router(engine))
    app.include_router(create_paper_router(session_factory=session_factory))
    app.include_router(
        create_strategy_router(session_factory=session_factory, registry=registry)
    )
    historical_available = (
        settings.oanda_api_token is not None
        and bool(settings.oanda_api_token.get_secret_value())
        if hasattr(settings, "oanda_api_token")
        else True
    )
    app.include_router(
        create_historical_data_router(
            session_factory=session_factory,
            coordinator=historical_coordinator,
            available=historical_available,
        )
    )
    app.include_router(
        create_experiment_router(
            session_factory=session_factory,
            configuration=app.state.experiment_configuration,
            lifecycle=app.state.experiment_lifecycle,
            results=app.state.experiment_results,
            deletion=app.state.experiment_deletion,
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

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, exc: HTTPException) -> JSONResponse:
        """Keep Atlas's structured error envelope at the HTTP response root."""
        detail = exc.detail
        if isinstance(detail, dict) and "error" in detail:
            content = detail
        else:
            content = {
                "error": {
                    "code": f"HTTP_{exc.status_code}",
                    "message": str(detail),
                    "details": {},
                }
            }
        return JSONResponse(
            status_code=exc.status_code,
            content=jsonable_encoder(content),
            headers=exc.headers,
        )

    return app
