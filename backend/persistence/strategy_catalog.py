"""Startup synchronization of the explicit local Strategy catalog."""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from backend.domain.strategy import StrategyVersion
from backend.strategies.registry import StrategyRegistry

from .strategy_repository import StrategyRepository


def synchronize_strategy_catalog(
    session_factory: Callable[[], Session], registry: StrategyRegistry
) -> None:
    """Persist every local registration atomically, or fail startup.

    ``create_version`` deduplicates by the immutable source fingerprint.  The
    single transaction ensures a failed catalog cannot become partially
    available to the application.
    """
    repository = StrategyRepository()
    with session_factory.begin() as session:
        for entry in registry.catalog():
            definition = entry.definition
            version = StrategyVersion(
                id=uuid4(),
                strategy_key=definition.strategy_key,
                version_number=1,
                source_fingerprint=entry.source_archive.fingerprint,
                implementation_key=definition.implementation_key,
                parameter_schema=definition.parameter_schema,
                primary_timeframe=definition.primary_timeframe,
                required_historical_context_bars=definition.required_historical_context_bars,
                state_schema_version=definition.state_schema_version,
                created_at=datetime.now(UTC),
            )
            repository.create_version(
                session,
                version,
                strategy_name=definition.name,
                strategy_description=definition.description,
                context_timeframes=tuple(
                    timeframe.value for timeframe in definition.context_timeframes
                ),
                capabilities=definition.capabilities,
                source_archive=entry.source_archive,
            )
