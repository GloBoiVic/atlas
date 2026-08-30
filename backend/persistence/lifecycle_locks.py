"""Small PostgreSQL transaction-local locks used by lifecycle boundaries.

The lifecycle lock serializes historical-load activation with Experiment
snapshot orphan cleanup.  Snapshot attachment has a separate, deliberately
different lock: the DatasetSnapshot row is locked before its referencing row.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .models import DatasetSnapshotModel

HISTORICAL_LOAD_LIFECYCLE_LOCK_KEY = 7_418_203


def acquire_historical_load_lifecycle_lock(session: Session) -> None:
    """Hold the shared historical-load serialization lock until transaction end."""
    session.execute(
        text("SELECT pg_advisory_xact_lock(:lock_key)"),
        {"lock_key": HISTORICAL_LOAD_LIFECYCLE_LOCK_KEY},
    )


def lock_snapshot_then_reference(
    session: Session,
    snapshot_id: UUID,
    *,
    reference_model: type[Any] | None = None,
    reference_id: UUID | None = None,
) -> tuple[DatasetSnapshotModel | None, Any | None]:
    """Lock an existing snapshot before its referencing row.

    Existing-snapshot attachment is intentionally centralized here.  The
    optional reference is used for an already-existing referencing row (for
    example a historical load request); a new Experiment is inserted by its
    caller only after this function returns.  No caller may replace this
    ordering with ``Session.get`` or a direct assignment shortcut.
    """
    snapshot = session.scalar(
        select(DatasetSnapshotModel)
        .where(DatasetSnapshotModel.id == snapshot_id)
        .with_for_update()
    )
    if snapshot is None or reference_model is None:
        return snapshot, None
    if reference_id is None:
        raise ValueError("reference_id is required when reference_model is supplied")
    reference = session.scalar(
        select(reference_model)
        .where(reference_model.id == reference_id)
        .with_for_update()
    )
    return snapshot, reference


__all__ = [
    "HISTORICAL_LOAD_LIFECYCLE_LOCK_KEY",
    "acquire_historical_load_lifecycle_lock",
    "lock_snapshot_then_reference",
]
