"""Focused create/read repository for Strategy and immutable StrategyVersion."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from backend.domain.market_data import Timeframe
from backend.domain.strategy import ParameterSchema, StrategyVersion
from backend.strategies.fingerprint import SourceArchive

from .models import ExperimentModel, StrategyModel, StrategyVersionModel


class StrategyVersionUsage:
    """Immutable usage facts composed from durable Experiment rows."""

    def __init__(self, count: int, last_used_at):
        self.count = count
        self.last_used_at = last_used_at


@dataclass(frozen=True)
class StrategyCatalogProjection:
    """Catalog facts composed by one bounded aggregate query."""

    strategy: StrategyModel
    latest_version: StrategyVersionModel | None
    version_count: int
    experiment_count: int
    last_experiment_at: datetime | None


class StrategyRepository:
    """Persistence boundary; it deliberately has no update or delete methods."""

    def create_strategy(
        self, session: Session, *, strategy_key: str, name: str, description: str
    ) -> StrategyModel:
        strategy = StrategyModel(
            strategy_key=strategy_key, name=name, description=description
        )
        session.add(strategy)
        session.flush()
        return strategy

    def get_strategy(self, session: Session, strategy_key: str) -> StrategyModel | None:
        return session.scalar(
            select(StrategyModel).where(StrategyModel.strategy_key == strategy_key)
        )

    def get_version(
        self, session: Session, version_id: UUID
    ) -> StrategyVersionModel | None:
        return session.get(StrategyVersionModel, version_id)

    def list_versions(
        self, session: Session, strategy_key: str
    ) -> Sequence[StrategyVersionModel]:
        return session.scalars(
            select(StrategyVersionModel)
            .join(StrategyModel)
            .where(StrategyModel.strategy_key == strategy_key)
            .order_by(StrategyVersionModel.version_number)
        ).all()

    def list_all_versions(self, session: Session) -> Sequence[StrategyVersionModel]:
        """Focused option read; immutable versions are newest-first by identity."""
        return session.scalars(
            select(StrategyVersionModel)
            .join(StrategyModel)
            .order_by(StrategyModel.strategy_key, StrategyVersionModel.version_number)
        ).all()

    def list_strategy_summaries(self, session: Session) -> Sequence[StrategyModel]:
        """Return the Atlas Strategy catalog in stable trader-facing order."""
        return session.scalars(
            select(StrategyModel).order_by(
                StrategyModel.name, StrategyModel.strategy_key
            )
        ).all()

    def list_catalog_projections(
        self, session: Session
    ) -> tuple[StrategyCatalogProjection, ...]:
        """Return catalog metadata without per-Strategy version/usage reads."""
        latest_version_number = (
            select(func.max(StrategyVersionModel.version_number))
            .where(StrategyVersionModel.strategy_id == StrategyModel.id)
            .correlate(StrategyModel)
            .scalar_subquery()
        )
        version_count = (
            select(func.count(StrategyVersionModel.id))
            .where(StrategyVersionModel.strategy_id == StrategyModel.id)
            .correlate(StrategyModel)
            .scalar_subquery()
        )
        experiment_count = (
            select(func.count(ExperimentModel.id))
            .join(
                StrategyVersionModel,
                ExperimentModel.strategy_version_id == StrategyVersionModel.id,
            )
            .where(StrategyVersionModel.strategy_id == StrategyModel.id)
            .correlate(StrategyModel)
            .scalar_subquery()
        )
        last_experiment_at = (
            select(func.max(ExperimentModel.created_at))
            .join(
                StrategyVersionModel,
                ExperimentModel.strategy_version_id == StrategyVersionModel.id,
            )
            .where(StrategyVersionModel.strategy_id == StrategyModel.id)
            .correlate(StrategyModel)
            .scalar_subquery()
        )
        rows = session.execute(
            select(
                StrategyModel,
                StrategyVersionModel,
                version_count,
                experiment_count,
                last_experiment_at,
            )
            .outerjoin(
                StrategyVersionModel,
                and_(
                    StrategyVersionModel.strategy_id == StrategyModel.id,
                    StrategyVersionModel.version_number == latest_version_number,
                ),
            )
            .order_by(StrategyModel.name, StrategyModel.strategy_key)
        ).all()
        return tuple(
            StrategyCatalogProjection(
                strategy=row[0],
                latest_version=row[1],
                version_count=int(row[2] or 0),
                experiment_count=int(row[3] or 0),
                last_experiment_at=row[4],
            )
            for row in rows
        )

    def strategy_usage(
        self, session: Session, strategy_id: UUID
    ) -> StrategyVersionUsage:
        count, last_used_at = session.execute(
            select(func.count(ExperimentModel.id), func.max(ExperimentModel.created_at))
            .join(
                StrategyVersionModel,
                ExperimentModel.strategy_version_id == StrategyVersionModel.id,
            )
            .where(StrategyVersionModel.strategy_id == strategy_id)
        ).one()
        return StrategyVersionUsage(int(count or 0), last_used_at)

    def version_usage(self, session: Session, version_id: UUID) -> StrategyVersionUsage:
        count, last_used_at = session.execute(
            select(
                func.count(ExperimentModel.id), func.max(ExperimentModel.created_at)
            ).where(ExperimentModel.strategy_version_id == version_id)
        ).one()
        return StrategyVersionUsage(int(count or 0), last_used_at)

    def create_version(
        self,
        session: Session,
        version: StrategyVersion,
        *,
        strategy_name: str,
        strategy_description: str,
        context_timeframes: tuple[str, ...] = (),
        capabilities: tuple[str, ...] = (),
        source_archive: SourceArchive,
        git_sha: str | None = None,
    ) -> StrategyVersionModel:
        if version.source_fingerprint != source_archive.fingerprint:
            raise ValueError(
                "StrategyVersion fingerprint does not match source archive"
            )

        strategy = session.scalar(
            select(StrategyModel)
            .where(StrategyModel.strategy_key == version.strategy_key)
            .with_for_update()
        )
        if strategy is None:
            session.execute(
                insert(StrategyModel)
                .values(
                    strategy_key=version.strategy_key,
                    name=strategy_name,
                    description=strategy_description,
                )
                .on_conflict_do_nothing(index_elements=[StrategyModel.strategy_key])
            )
            strategy = session.scalar(
                select(StrategyModel)
                .where(StrategyModel.strategy_key == version.strategy_key)
                .with_for_update()
            )
            if strategy is None:  # pragma: no cover - database failure guard
                raise RuntimeError("strategy could not be created or loaded")
        existing = session.scalar(
            select(StrategyVersionModel).where(
                StrategyVersionModel.strategy_id == strategy.id,
                StrategyVersionModel.source_fingerprint == version.source_fingerprint,
            )
        )
        if existing is not None:
            return existing

        latest = session.scalar(
            select(func.max(StrategyVersionModel.version_number)).where(
                StrategyVersionModel.strategy_id == strategy.id
            )
        )
        row = StrategyVersionModel(
            id=version.id,
            strategy_id=strategy.id,
            version_number=(latest or 0) + 1,
            source_fingerprint=version.source_fingerprint,
            implementation_key=version.implementation_key,
            parameter_schema=[item.to_json() for item in version.parameter_schema],
            context_timeframes=list(context_timeframes),
            capabilities=list(capabilities),
            source_manifest=[
                {"relative_path": path, "byte_length": length}
                for path, length in source_archive.manifest
            ],
            exact_source_snapshot={
                path: content.decode("utf-8")
                for path, content in source_archive.exact_source_snapshot
            },
            primary_timeframe=version.primary_timeframe.value,
            required_historical_context_bars=version.required_historical_context_bars,
            state_schema_version=version.state_schema_version,
            git_sha=git_sha,
            created_at=version.created_at,
        )
        session.add(row)
        session.flush()
        return row


def version_to_domain(row: StrategyVersionModel) -> StrategyVersion:
    """Map the durable identity back to the existing immutable domain value."""

    schema = tuple(
        ParameterSchema(
            key=item["key"],
            label=item["label"],
            type=item["type"],
            default=item["default"],
            nullable=item["nullable"],
            minimum=item["min"],
            maximum=item["max"],
            description=item["description"],
            allowed_values=tuple(item.get("allowed_values", [])),
        )
        for item in row.parameter_schema
    )
    created_at = row.created_at
    # PostgreSQL ``timestamptz`` may be returned with the connection timezone,
    # while test doubles/legacy rows may be naive. Persisted Atlas timestamps
    # are UTC instants: normalize an aware value, and treat a naive persisted
    # value as the documented UTC storage representation (never local time).
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    else:
        created_at = created_at.astimezone(UTC)
    return StrategyVersion(
        id=row.id,
        strategy_key=row.strategy.strategy_key,
        version_number=row.version_number,
        source_fingerprint=row.source_fingerprint,
        implementation_key=row.implementation_key,
        parameter_schema=schema,
        primary_timeframe=Timeframe(row.primary_timeframe),
        required_historical_context_bars=row.required_historical_context_bars,
        state_schema_version=row.state_schema_version,
        created_at=created_at,
    )
