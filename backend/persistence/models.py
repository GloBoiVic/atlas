"""SQLAlchemy persistence models for the Phase 1 Strategy provenance slice."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class StrategyModel(Base):
    __tablename__ = "strategies"

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    strategy_key: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(2000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    versions: Mapped[list["StrategyVersionModel"]] = relationship(
        back_populates="strategy", passive_deletes=True
    )


class StrategyVersionModel(Base):
    __tablename__ = "strategy_versions"
    __table_args__ = (
        CheckConstraint("version_number > 0", name="positive_version_number"),
        CheckConstraint(
            "source_fingerprint ~ '^[0-9a-f]{64}$'", name="sha256_fingerprint"
        ),
        UniqueConstraint(
            "strategy_id", "version_number", name="uq_strategy_versions_strategy_id"
        ),
        UniqueConstraint(
            "strategy_id",
            "source_fingerprint",
            name="uq_strategy_versions_strategy_id_source_fingerprint",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    strategy_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("strategies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(nullable=False)
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    implementation_key: Mapped[str] = mapped_column(String(200), nullable=False)
    parameter_schema: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False
    )
    context_timeframes: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    capabilities: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    source_manifest: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    exact_source_snapshot: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False)
    primary_timeframe: Mapped[str] = mapped_column(String(20), nullable=False)
    warm_up_bars: Mapped[int] = mapped_column(nullable=False)
    state_schema_version: Mapped[int] = mapped_column(nullable=False)
    git_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    strategy: Mapped[StrategyModel] = relationship(back_populates="versions")
