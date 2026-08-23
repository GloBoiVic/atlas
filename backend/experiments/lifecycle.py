"""Durable, synchronous Experiment run lifecycle orchestration."""

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.persistence.experiment_repository import ExperimentRepository
from backend.persistence.models import ExperimentModel

from .runner import (
    ExperimentFailure,
    ExperimentRunner,
    ExperimentRunResult,
    FailureCategory,
)


class ExperimentRunInfrastructureError(RuntimeError):
    """A sanitized error raised after durable failure persistence is attempted."""

    code = "PERSISTENCE_FAILURE"

    def __init__(self) -> None:
        super().__init__("Experiment run could not be persisted; retry the Experiment")


SessionFactory = Callable[[], Session]
LifecycleDiagnosticSink = Callable[["ExperimentLifecycleDiagnostic"], None]


class LifecycleDiagnosticStage(StrEnum):
    RUNNER_RETURN = "RUNNER_RETURN"
    FLUSH = "FLUSH"
    COMMIT = "COMMIT"
    FALLBACK_BEGIN = "FALLBACK_BEGIN"
    FALLBACK_FLUSH = "FALLBACK_FLUSH"
    FALLBACK_COMMIT = "FALLBACK_COMMIT"
    FINAL_READ = "FINAL_READ"


@dataclass(frozen=True, slots=True)
class ExperimentLifecycleDiagnostic:
    stage: LifecycleDiagnosticStage
    exception_class: str | None
    sqlstate: str | None
    show_time_zone: str
    backend_pid: int | None
    alembic_revision: str

    def as_dict(self) -> dict[str, object]:
        return {
            "stage": self.stage,
            "exception_class": self.exception_class,
            "sqlstate": self.sqlstate,
            "show_time_zone": self.show_time_zone,
            "backend_pid": self.backend_pid,
            "alembic_revision": self.alembic_revision,
        }


@dataclass(frozen=True, slots=True)
class _ConnectionMetadata:
    show_time_zone: str
    backend_pid: int | None
    alembic_revision: str


_APPROVED_EXCEPTION_CLASSES = frozenset(
    {
        "ValueError", "RuntimeError", "LookupError", "KeyError", "TypeError",
        "IntegrityError", "OperationalError", "DatabaseError", "InterfaceError",
        "DBAPIError", "StatementError", "SQLAlchemyError", "Error",
    }
)
_SQLSTATE = re.compile(r"^[A-Z0-9]{5}$")
_TIME_ZONE = re.compile(r"^[^\x00\r\n]{1,128}$")
_REVISION = re.compile(r"^[A-Za-z0-9_]{1,128}$")


def _exception_class(error: BaseException) -> str:
    name = type(error).__name__
    return name if name in _APPROVED_EXCEPTION_CLASSES else "UNCLASSIFIED_EXCEPTION"


def _sqlstate(error: BaseException) -> str | None:
    candidates: list[object] = []
    try:
        candidates.append(getattr(error, "sqlstate", None))
        diag = getattr(error, "diag", None)
        candidates.append(getattr(diag, "sqlstate", None))
        original = getattr(error, "orig", None)
        candidates.append(getattr(original, "sqlstate", None))
        original_diag = getattr(original, "diag", None)
        candidates.append(getattr(original_diag, "sqlstate", None))
    except Exception:
        return None
    for value in candidates:
        if isinstance(value, str) and _SQLSTATE.fullmatch(value):
            return value
    return None


def _metadata(session: Session) -> _ConnectionMetadata:
    unavailable = _ConnectionMetadata("UNAVAILABLE", None, "UNAVAILABLE")
    try:
        connection = session.connection()
        with session.begin_nested():
            zone = connection.execute(text("SHOW TIME ZONE")).scalar_one_or_none()
            pid = connection.execute(
                text("SELECT pg_backend_pid()")
            ).scalar_one_or_none()
            revision_rows = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalars().all()
            if (
                not isinstance(zone, str)
                or _TIME_ZONE.fullmatch(zone) is None
                or not isinstance(pid, int)
                or pid <= 0
                or len(revision_rows) != 1
                or not isinstance(revision_rows[0], str)
                or _REVISION.fullmatch(revision_rows[0]) is None
            ):
                return unavailable
            return _ConnectionMetadata(zone, pid, revision_rows[0])
    except Exception:
        return unavailable


class ExperimentRunService:
    """Claim, execute, and atomically finalize one Experiment."""

    def __init__(
        self,
        session_factory: SessionFactory,
        runner: ExperimentRunner,
        *,
        repository: ExperimentRepository | None = None,
        lifecycle_diagnostic_sink: LifecycleDiagnosticSink | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._runner = runner
        self._experiments = repository or ExperimentRepository()
        self._diagnostic_sink = lifecycle_diagnostic_sink

    def run(self, experiment_id: UUID) -> ExperimentRunResult:
        """Run synchronously; the committed RUNNING claim precedes all facts."""
        try:
            decision = self._claim(experiment_id)
            if decision is not None:
                return decision
            with self._session_factory() as session:
                primary_commit_ready = False
                try:
                    with session.begin():
                        if self._diagnostic_sink is not None:
                            self._prepare(session)
                        row = self._experiments.get_for_update(session, experiment_id)
                        if row is None:
                            raise ValueError("experiment does not exist")
                        # A duplicate command waits for this transaction's row lock,
                        # then observes the terminal state without rerunning.
                        if row.status in {"COMPLETED", "FAILED"}:
                            result = self._result(row)
                        else:
                            try:
                                result = self._runner.run(session, experiment_id)
                            except Exception as error:
                                self._emit(
                                    session,
                                    LifecycleDiagnosticStage.RUNNER_RETURN,
                                    error,
                                )
                                raise
                            self._emit(session, LifecycleDiagnosticStage.RUNNER_RETURN)
                            if result.status not in {"COMPLETED", "FAILED"}:
                                raise RuntimeError(
                                    "runner did not produce terminal state"
                                )
                            try:
                                if self._diagnostic_sink is not None:
                                    self._prepare(session)
                                    session.flush()
                            except Exception as error:
                                self._emit(
                                    session, LifecycleDiagnosticStage.FLUSH, error
                                )
                                raise
                            self._emit(session, LifecycleDiagnosticStage.FLUSH)
                            primary_commit_ready = True
                            if self._diagnostic_sink is not None:
                                self._prepare(session)
                except Exception as error:
                    if primary_commit_ready:
                        self._emit(session, LifecycleDiagnosticStage.COMMIT, error)
                    raise
                self._emit(session, LifecycleDiagnosticStage.COMMIT)
                self._emit_final_read(experiment_id)
                return result
        except ExperimentRunInfrastructureError:
            raise
        except Exception:
            self._persist_failure_fallback(experiment_id)
            self._emit_final_read(experiment_id)
            raise ExperimentRunInfrastructureError() from None

    def _claim(self, experiment_id: UUID) -> ExperimentRunResult | None:
        with self._session_factory() as session:
            with session.begin():
                row = self._experiments.get_for_update(session, experiment_id)
                if row is None:
                    raise ValueError("experiment does not exist")
                if row.status in {"COMPLETED", "FAILED"}:
                    return self._result(row)
                if row.status == "RUNNING":
                    if self._experiments.has_run_facts(session, experiment_id):
                        self._experiments.mark_failed(
                            session,
                            experiment_id,
                            category=FailureCategory.PERSISTENCE.value,
                            code="INCOMPLETE_RUN_STATE",
                            detail=(
                                "A prior run left committed partial facts; "
                                "create a new Experiment"
                            ),
                            completed_at=datetime.now(UTC),
                        )
                        return self._result(row)
                    # A clean RUNNING row is a crash-equivalent recovery claim.
                    return None
                if row.status != "PENDING":
                    raise ValueError("invalid Experiment status")
                self._experiments.mark_running(session, experiment_id)
                # Exiting this transaction commits the durable claim before the
                # runner transaction is opened.
                return None

    def _persist_failure_fallback(self, experiment_id: UUID) -> None:
        """Use a fresh Session after an unusable runner transaction."""
        try:
            with self._session_factory() as session:
                fallback_commit_ready = False
                fallback_started = False
                fallback_flush_started = False
                try:
                    with session.begin():
                        if self._diagnostic_sink is not None:
                            self._prepare(session)
                        row = self._experiments.get_for_update(session, experiment_id)
                        if row is not None and row.status in {"PENDING", "RUNNING"}:
                            fallback_started = True
                            self._emit(session, LifecycleDiagnosticStage.FALLBACK_BEGIN)
                            if self._diagnostic_sink is not None:
                                self._prepare(session)
                            fallback_flush_started = True
                            self._experiments.mark_failed(
                                session,
                                experiment_id,
                                category=FailureCategory.PERSISTENCE.value,
                                code="PERSISTENCE_FAILURE",
                                detail=(
                                "Experiment persistence failed; create a new "
                                "Experiment"
                                ),
                                completed_at=datetime.now(UTC),
                            )
                            self._emit(session, LifecycleDiagnosticStage.FALLBACK_FLUSH)
                        fallback_commit_ready = True
                except Exception as error:
                    if fallback_commit_ready:
                        self._emit(
                            session, LifecycleDiagnosticStage.FALLBACK_COMMIT, error
                        )
                    elif fallback_flush_started:
                        self._emit(
                            session, LifecycleDiagnosticStage.FALLBACK_FLUSH, error
                        )
                    elif fallback_started:
                        self._emit(
                            session, LifecycleDiagnosticStage.FALLBACK_BEGIN, error
                        )
                    else:
                        self._emit(
                            session, LifecycleDiagnosticStage.FALLBACK_BEGIN, error
                        )
                    return
                self._emit(session, LifecycleDiagnosticStage.FALLBACK_COMMIT)
        except Exception:
            # The caller still receives the sanitized infrastructure error. A
            # subsequent status read remains the authority if fallback failed.
            return

    def _emit(
        self,
        session: Session,
        stage: LifecycleDiagnosticStage,
        error: BaseException | None = None,
    ) -> None:
        if self._diagnostic_sink is None:
            return
        metadata = self._prepare(session)
        record = ExperimentLifecycleDiagnostic(
            stage=stage,
            exception_class=None if error is None else _exception_class(error),
            sqlstate=None if error is None else _sqlstate(error),
            show_time_zone=metadata.show_time_zone,
            backend_pid=metadata.backend_pid,
            alembic_revision=metadata.alembic_revision,
        )
        try:
            self._diagnostic_sink(record)
        except Exception:
            return

    def _prepare(self, session: Session) -> _ConnectionMetadata:
        key = "atlas_lifecycle_diagnostic_metadata"
        if key not in session.info:
            session.info[key] = _metadata(session)
        return session.info[key]

    def _emit_final_read(self, experiment_id: UUID) -> None:
        if self._diagnostic_sink is None:
            return
        session: Session | None = None
        try:
            session = self._session_factory()
            with session:
                with session.begin():
                    self._prepare(session)
                    self._experiments.get(session, experiment_id)
                self._emit(session, LifecycleDiagnosticStage.FINAL_READ)
        except Exception as error:
            # A diagnostic read must never replace the lifecycle result.
            try:
                if session is not None:
                    self._emit(session, LifecycleDiagnosticStage.FINAL_READ, error)
            except Exception:
                return

    @staticmethod
    def _result(row: ExperimentModel) -> ExperimentRunResult:
        failure = None
        if row.status == "FAILED":
            failure = ExperimentFailure(
                FailureCategory(row.failure_category),
                row.failure_code or "PERSISTENCE_FAILURE",
                row.failure_detail or "Experiment failed",
            )
        return ExperimentRunResult(row.id, row.status, False, failure)


__all__ = [
    "ExperimentLifecycleDiagnostic",
    "ExperimentRunInfrastructureError",
    "ExperimentRunService",
    "LifecycleDiagnosticStage",
]
