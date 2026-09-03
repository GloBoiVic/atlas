"""The single PostgreSQL-backed owner of the PAPER runtime.

The ownership row is only an audit projection.  The authority for this
process is the session-level advisory lock held by ``_connection``.  Keeping
that SQLAlchemy connection on this object prevents the pool from reclaiming
the session while the runtime is still alive.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import Engine, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from backend.persistence.models import PaperRuntimeOwnershipModel
from backend.persistence.runtime_repository import (
    PaperRuntimeOwnerLost,
    PaperRuntimeRepository,
)

from .persistence_contracts import (
    PAPER_RUNTIME_SLOT,
    PaperRuntimeOwnership,
    PaperRuntimeOwnershipPhase,
)

# This is deliberately a distinct, fixed singleton key.  Changing it would
# create a second runtime ownership domain and requires an explicit operational
# migration, so it must not be derived from mutable configuration.
PAPER_RUNTIME_ADVISORY_LOCK_KEY = 7_418_204

_TRY_ADVISORY_LOCK = text("SELECT pg_try_advisory_lock(CAST(:lock_key AS BIGINT))")
_RELEASE_ADVISORY_LOCK = text("SELECT pg_advisory_unlock(CAST(:lock_key AS BIGINT))")
_CHECK_ADVISORY_LOCK = text(
    """
    SELECT EXISTS (
        SELECT 1
        FROM pg_locks
        WHERE locktype = 'advisory'
          AND pid = pg_backend_pid()
          AND granted
          AND classid = 0
          AND objid = :lock_key
    )
    """
)


class PaperRuntimeOwnerError(RuntimeError):
    """Base error for the dedicated runtime owner seam."""


class PaperRuntimeOwnerConfigurationError(PaperRuntimeOwnerError):
    """The owner was configured with a non-PostgreSQL or invalid input."""


class PaperRuntimeOwnerNotAcquired(PaperRuntimeOwnerError):
    """An operation requiring the singleton owner ran before acquisition."""


class PaperRuntimeOwnerUnavailable(PaperRuntimeOwnerError):
    """Another live PostgreSQL session already owns the singleton lock."""

    code = "RUNTIME_OWNER_PRESENT"


def _now() -> datetime:
    return datetime.now(UTC)


SessionFactory = Callable[[], Session]
Clock = Callable[[], datetime]


class PaperRuntimeOwner:
    """Acquire and hold the one PAPER runtime advisory lock.

    ``try_acquire`` opens one dedicated SQLAlchemy connection.  A successful
    ``pg_try_advisory_lock`` is committed and the connection remains checked
    out for this object's lifetime.  Only then is the durable ownership row
    written.  A failed attempt closes its candidate connection immediately
    and performs no persistence or provider work.
    """

    def __init__(
        self,
        engine: Engine,
        session_factory: SessionFactory,
        *,
        repository: PaperRuntimeRepository | None = None,
        owner_id: UUID | None = None,
        activation_id: UUID | None = None,
        clock: Clock = _now,
    ) -> None:
        if owner_id is not None and type(owner_id) is not UUID:
            raise PaperRuntimeOwnerConfigurationError("owner_id must be a UUID")
        if activation_id is not None and type(activation_id) is not UUID:
            raise PaperRuntimeOwnerConfigurationError("activation_id must be a UUID")
        self._engine = engine
        self._session_factory = session_factory
        self._repository = repository or PaperRuntimeRepository()
        self._owner_id = owner_id or uuid4()
        self._activation_id = activation_id
        self._clock = clock
        self._connection: Connection | None = None
        self._ownership: PaperRuntimeOwnership | None = None
        self._finished = False
        self._lost = False

    @property
    def ownership(self) -> PaperRuntimeOwnership:
        """Return the immutable identity used for guarded repository writes."""
        if self._ownership is None:
            raise PaperRuntimeOwnerNotAcquired("runtime ownership is not acquired")
        return self._ownership

    @property
    def owner_id(self) -> UUID:
        return self._owner_id

    @property
    def owner_generation(self) -> int:
        return self.ownership.owner_generation

    @property
    def connection(self) -> Connection:
        """Expose the pinned connection for controlled process-lifetime use."""
        return self._require_connection()

    @property
    def acquired(self) -> bool:
        return (
            self._ownership is not None
            and self._connection is not None
            and not self._finished
            and not self._lost
            and not self._connection.closed
            and not self._connection.invalidated
        )

    def try_acquire(
        self, *, activation_id: UUID | None = None
    ) -> PaperRuntimeOwnership | None:
        """Try to become the owner, returning ``None`` for a live loser.

        An acquired owner is not allowed to reacquire after connection loss;
        callers must construct a new owner object for a new process/session.
        """
        requested_activation_id = self._resolve_activation_id(activation_id)
        if self._ownership is not None:
            self._assert_advisory_lock()
            return self._ownership
        if self._finished:
            raise PaperRuntimeOwnerError("runtime owner is closed")
        self._validate_engine()

        candidate = self._engine.connect()
        try:
            acquired = candidate.scalar(
                _TRY_ADVISORY_LOCK,
                {"lock_key": PAPER_RUNTIME_ADVISORY_LOCK_KEY},
            )
            # The session lock survives this transaction.  Ending the
            # transaction also prevents the dedicated connection from sitting
            # idle in transaction while the runtime is waiting for its tick.
            candidate.commit()
            if not bool(acquired):
                candidate.close()
                return None
            self._connection = candidate
            ownership = self._persist_acquired_ownership(requested_activation_id)
            self._ownership = ownership
            return ownership
        except Exception:
            if self._connection is candidate:
                self._mark_lost()
            else:
                self._close_connection(candidate)
            self._finished = True
            raise

    def acquire(self, *, activation_id: UUID | None = None) -> PaperRuntimeOwnership:
        """Acquire the singleton or raise a bounded owner-present error."""
        ownership = self.try_acquire(activation_id=activation_id)
        if ownership is None:
            raise PaperRuntimeOwnerUnavailable("another runtime owner is present")
        return ownership

    def assert_current(
        self,
        session: Session,
        *,
        activation_id: UUID | None = None,
    ) -> PaperRuntimeOwnershipModel:
        """Prove both live lock ownership and current durable generation."""
        self._assert_advisory_lock()
        requested_activation_id = self._resolve_activation_id(activation_id)
        try:
            return self._repository.assert_owner(
                session,
                self._owner_id,
                self.owner_generation,
                activation_id=requested_activation_id,
            )
        except PaperRuntimeOwnerLost:
            self._mark_lost()
            raise

    def heartbeat(
        self,
        session: Session,
        *,
        heartbeat_at: datetime | None = None,
        phase: PaperRuntimeOwnershipPhase | None = None,
    ) -> PaperRuntimeOwnershipModel:
        """Write audit heartbeat evidence under the current owner generation."""
        self._assert_advisory_lock()
        try:
            return self._repository.heartbeat_ownership(
                session,
                owner_id=self._owner_id,
                owner_generation=self.owner_generation,
                heartbeat_at=heartbeat_at,
                phase=phase,
            )
        except PaperRuntimeOwnerLost:
            self._mark_lost()
            raise

    def guarded_update(
        self,
        session: Session,
        values: dict[str, object],
    ) -> PaperRuntimeOwnershipModel:
        """Apply a narrow owner-generation-guarded projection update."""
        self._assert_advisory_lock()
        try:
            return self._repository.guarded_owner_update(
                session,
                owner_id=self._owner_id,
                owner_generation=self.owner_generation,
                values=values,
            )
        except PaperRuntimeOwnerLost:
            self._mark_lost()
            raise

    def attach_activation(
        self, session: Session, activation_id: UUID
    ) -> PaperRuntimeOwnershipModel:
        """Attach the selected activation without changing owner generation."""
        if type(activation_id) is not UUID:
            raise PaperRuntimeOwnerConfigurationError("activation_id must be a UUID")
        self._assert_advisory_lock()
        try:
            current = self._repository.assert_owner(
                session,
                self._owner_id,
                self.owner_generation,
            )
            if (
                current.activation_id is not None
                and current.activation_id != activation_id
            ):
                raise PaperRuntimeOwnerLost(
                    "runtime owner is already attached to another activation"
                )
            if current.activation_id == activation_id:
                self._remember_activation(
                    activation_id, PaperRuntimeOwnershipPhase(current.phase)
                )
                return current
            row = self._repository.guarded_owner_update(
                session,
                owner_id=self._owner_id,
                owner_generation=self.owner_generation,
                values={"activation_id": activation_id},
            )
        except PaperRuntimeOwnerLost:
            self._mark_lost()
            raise
        self._remember_activation(activation_id, PaperRuntimeOwnershipPhase(row.phase))
        return row

    def set_phase(
        self,
        session: Session,
        phase: PaperRuntimeOwnershipPhase,
        *,
        heartbeat_at: datetime | None = None,
    ) -> PaperRuntimeOwnershipModel:
        """Update the durable audit phase while preserving the lock fence."""
        if type(phase) is not PaperRuntimeOwnershipPhase:
            raise PaperRuntimeOwnerConfigurationError("ownership phase is invalid")
        return self.guarded_update(
            session,
            {
                "phase": phase.value,
                "heartbeat_at": heartbeat_at or self._clock(),
            },
        )

    def close(self) -> None:
        """Release the session lock by closing its dedicated connection.

        Closing the PostgreSQL session is the release operation.  Durable
        ownership evidence is intentionally not rewritten here: a successor
        must first acquire the lock and then advance the generation.
        """
        self._finished = True
        connection = self._connection
        self._connection = None
        self._lost = True
        if connection is not None:
            self._release_connection(connection)

    release = close

    def __enter__(self) -> PaperRuntimeOwner:
        self.acquire()
        return self

    def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
        self.close()

    def _resolve_activation_id(self, activation_id: UUID | None) -> UUID | None:
        if activation_id is not None and type(activation_id) is not UUID:
            raise PaperRuntimeOwnerConfigurationError("activation_id must be a UUID")
        if (
            activation_id is not None
            and self._activation_id is not None
            and activation_id != self._activation_id
        ):
            raise PaperRuntimeOwnerConfigurationError(
                "activation_id does not match owner configuration"
            )
        return activation_id if activation_id is not None else self._activation_id

    def _validate_engine(self) -> None:
        if self._engine.dialect.name != "postgresql":
            raise PaperRuntimeOwnerConfigurationError(
                "PAPER runtime ownership requires PostgreSQL"
            )

    def _remember_activation(
        self, activation_id: UUID, phase: PaperRuntimeOwnershipPhase
    ) -> None:
        prior = self.ownership
        self._activation_id = activation_id
        if prior.activation_id == activation_id:
            return
        self._ownership = PaperRuntimeOwnership(
            owner_id=prior.owner_id,
            activation_id=activation_id,
            owner_generation=prior.owner_generation,
            acquired_at=prior.acquired_at,
            heartbeat_at=prior.heartbeat_at,
            phase=phase,
            slot_key=prior.slot_key,
        )

    def _persist_acquired_ownership(
        self, activation_id: UUID | None
    ) -> PaperRuntimeOwnership:
        session = self._session_factory()
        try:
            with session.begin():
                current = self._repository.get_ownership(session, for_update=True)
                generation = (current.owner_generation + 1) if current else 1
                timestamp = self._clock()
                ownership = PaperRuntimeOwnership(
                    owner_id=self._owner_id,
                    activation_id=activation_id,
                    owner_generation=generation,
                    acquired_at=timestamp,
                    heartbeat_at=timestamp,
                    phase=PaperRuntimeOwnershipPhase.ACQUIRED,
                    slot_key=PAPER_RUNTIME_SLOT,
                )
                self._repository.record_ownership_after_lock(session, ownership)
            return ownership
        finally:
            session.close()

    def _require_connection(self) -> Connection:
        if self._connection is None:
            if self._lost:
                raise PaperRuntimeOwnerLost("runtime advisory-lock connection is lost")
            raise PaperRuntimeOwnerNotAcquired("runtime ownership is not acquired")
        return self._connection

    def _assert_advisory_lock(self) -> None:
        connection = self._require_connection()
        if connection.closed:
            self._mark_lost()
            raise PaperRuntimeOwnerLost("runtime advisory-lock connection is closed")
        try:
            held = connection.scalar(
                _CHECK_ADVISORY_LOCK,
                {"lock_key": PAPER_RUNTIME_ADVISORY_LOCK_KEY},
            )
            connection.commit()
        except Exception as error:
            self._mark_lost()
            raise PaperRuntimeOwnerLost(
                "runtime advisory-lock connection is lost"
            ) from error
        if not bool(held):
            self._mark_lost()
            raise PaperRuntimeOwnerLost("runtime advisory lock is no longer held")

    def _mark_lost(self) -> None:
        self._lost = True
        self._finished = True
        connection = self._connection
        self._connection = None
        if connection is not None:
            self._release_connection(connection)

    @staticmethod
    def _release_connection(connection: Connection) -> None:
        if not connection.closed and not connection.invalidated:
            try:
                connection.execute(
                    _RELEASE_ADVISORY_LOCK,
                    {"lock_key": PAPER_RUNTIME_ADVISORY_LOCK_KEY},
                )
                connection.commit()
            except Exception:
                # A dead connection has already released the session lock.
                # Cleanup must not replace the owner-loss cause.
                pass
        PaperRuntimeOwner._close_connection(connection)

    @staticmethod
    def _close_connection(connection: Connection) -> None:
        try:
            connection.close()
        except Exception:
            # The primary owner failure or acquisition result must not be
            # hidden by cleanup of an already-dead PostgreSQL connection.
            pass


__all__ = [
    "PAPER_RUNTIME_ADVISORY_LOCK_KEY",
    "PaperRuntimeOwner",
    "PaperRuntimeOwnerConfigurationError",
    "PaperRuntimeOwnerError",
    "PaperRuntimeOwnerLost",
    "PaperRuntimeOwnerNotAcquired",
    "PaperRuntimeOwnerUnavailable",
]
