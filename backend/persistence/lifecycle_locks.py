"""Small PostgreSQL transaction-local locks used by lifecycle boundaries.

The lifecycle lock serializes historical-load activation with Experiment
snapshot orphan cleanup.  Snapshot attachment has a separate, deliberately
different lock: the DatasetSnapshot row is locked before its referencing row.
"""

from __future__ import annotations

import hashlib
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from .models import DatasetSnapshotModel

HISTORICAL_LOAD_LIFECYCLE_LOCK_KEY = 7_418_203


def deployment_advisory_lock_key(deployment_id: UUID) -> int:
    """Return a stable positive PostgreSQL bigint for one Deployment UUID."""
    if type(deployment_id) is not UUID:
        raise TypeError("deployment_id must be a UUID")
    value = int.from_bytes(hashlib.sha256(deployment_id.bytes).digest()[:8], "big")
    return value & ((1 << 63) - 1) or 1


def acquire_deployment_runtime_lock(session: Session, deployment_id: UUID) -> bool:
    """Try to own the Deployment for this database session.

    The connection backing ``session`` must remain open for the entire runtime;
    PostgreSQL releases this session-level lock when that connection dies.
    """
    result = session.execute(
        text("SELECT pg_try_advisory_lock(:lock_key)"),
        {"lock_key": deployment_advisory_lock_key(deployment_id)},
    )
    return bool(result.scalar_one())


def release_deployment_runtime_lock(session: Session, deployment_id: UUID) -> bool:
    """Release the Deployment lock held by this session, if any."""
    result = session.execute(
        text("SELECT pg_advisory_unlock(:lock_key)"),
        {"lock_key": deployment_advisory_lock_key(deployment_id)},
    )
    return bool(result.scalar_one())


class DeploymentRuntimeLock:
    """Own a Deployment advisory lock on one long-lived DB connection.

    The connection must not be returned to the pool while the runtime owns the
    lock.  This is intentionally separate from short ORM transactions used to
    write heartbeat and lifecycle facts.
    """

    def __init__(self, connection: Connection, deployment_id: UUID) -> None:
        self.connection = connection
        self.deployment_id = deployment_id

    @property
    def key(self) -> int:
        return deployment_advisory_lock_key(self.deployment_id)

    def acquire(self) -> bool:
        result = self.connection.execute(
            text("SELECT pg_try_advisory_lock(:lock_key)"), {"lock_key": self.key}
        )
        return bool(result.scalar_one())

    def release(self) -> bool:
        result = self.connection.execute(
            text("SELECT pg_advisory_unlock(:lock_key)"), {"lock_key": self.key}
        )
        return bool(result.scalar_one())

    def is_held(self) -> bool:
        """Probe the owning session without changing the lock contract."""
        result = self.connection.execute(
            text("SELECT pg_try_advisory_lock(:lock_key)"), {"lock_key": self.key}
        )
        return bool(result.scalar_one())


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
    "acquire_deployment_runtime_lock",
    "DeploymentRuntimeLock",
    "deployment_advisory_lock_key",
    "lock_snapshot_then_reference",
    "release_deployment_runtime_lock",
]
