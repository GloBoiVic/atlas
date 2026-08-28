"""Persistence transitions for the one narrow historical-load command."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import HistoricalDataLoadRequestModel

ACTIVE = ("PENDING", "RUNNING")


def _now() -> datetime:
    return datetime.now(UTC)


def _ranges(values):
    return [
        {
            "start": a.isoformat().replace("+00:00", "Z"),
            "end": b.isoformat().replace("+00:00", "Z"),
        }
        for a, b in values
    ]


class HistoricalDataLoadRepository:
    def create_pending(
        self,
        session: Session,
        *,
        strategy_version_id: UUID,
        trading_start: datetime,
        trading_end: datetime,
        load_start: datetime,
        load_end: datetime,
    ) -> HistoricalDataLoadRequestModel:
        row = HistoricalDataLoadRequestModel(
            strategy_version_id=strategy_version_id,
            trading_start=trading_start,
            trading_end=trading_end,
            load_start=load_start,
            load_end=load_end,
        )
        session.add(row)
        session.flush()
        return row

    def get(
        self, session: Session, request_id: UUID
    ) -> HistoricalDataLoadRequestModel | None:
        return session.get(HistoricalDataLoadRequestModel, request_id)

    def active(self, session: Session) -> HistoricalDataLoadRequestModel | None:
        return session.scalar(
            select(HistoricalDataLoadRequestModel)
            .where(HistoricalDataLoadRequestModel.status.in_(ACTIVE))
            .order_by(
                HistoricalDataLoadRequestModel.created_at.desc(),
                HistoricalDataLoadRequestModel.id.desc(),
            )
            .limit(1)
        )

    def claim(
        self, session: Session, request_id: UUID
    ) -> HistoricalDataLoadRequestModel | None:
        row = session.scalar(
            select(HistoricalDataLoadRequestModel)
            .where(HistoricalDataLoadRequestModel.id == request_id)
            .with_for_update()
        )
        if row is not None and row.status == "PENDING":
            row.status = "RUNNING"
            row.started_at = _now()
            row.updated_at = _now()
            session.flush()
        return row

    def record_progress(
        self,
        session: Session,
        request_id: UUID,
        *,
        fetched_ranges=(),
        committed_ranges=(),
        inserted=0,
        reactivated=0,
        unchanged=0,
        incomplete_minutes=(),
        coverage_summary=None,
        phase="Fetching M1 execution data",
        completed_units=None,
        total_units=None,
        unit="database_commit",
        product=None,
        window=None,
    ) -> bool:
        row = session.scalar(
            select(HistoricalDataLoadRequestModel)
            .where(HistoricalDataLoadRequestModel.id == request_id)
            .with_for_update()
        )
        if row is None or row.status != "RUNNING":
            return False
        # These legacy columns are retained for schema compatibility, but a
        # progress update must never copy the request-sized window history into
        # JSON.  The durable acquisition-window table is the resume authority;
        # progress stores only bounded counters and the latest window below.
        row.fetched_ranges = []
        row.committed_ranges = []
        row.inserted, row.reactivated, row.unchanged = inserted, reactivated, unchanged
        row.incomplete_minute_count = len(incomplete_minutes)
        previous_progress = (row.coverage_summary or {}).get("progress", {})
        if completed_units is None:
            completed_units = 0
        if previous_progress.get("completed_units") is not None:
            completed_units = max(completed_units, previous_progress["completed_units"])
        progress = {
            "phase": phase,
            "completed_units": completed_units,
            "total_units": total_units,
            "unit": unit,
            "fetched_range_count": 0,
            "committed_range_count": 0,
        }
        if product is not None:
            products = dict(previous_progress.get("products", {}))
            product_progress = dict(products.get(product, {}))
            if window is not None:
                product_progress["last_committed_window"] = window
            product_progress["completed_units"] = max(
                completed_units, product_progress.get("completed_units", 0)
            )
            products[product] = product_progress
            progress["products"] = products
        # Keep additive progress durable without introducing a second lifecycle
        # table.  Final coverage retains these facts for auditability.
        summary = dict(coverage_summary or row.coverage_summary or {})
        summary["progress"] = progress
        row.coverage_summary = summary
        row.updated_at = _now()
        session.flush()
        return True

    def complete(
        self,
        session: Session,
        request_id: UUID,
        *,
        snapshot_id: UUID,
        coverage_summary: dict,
        experiment_validation: dict,
    ) -> bool:
        row = session.scalar(
            select(HistoricalDataLoadRequestModel)
            .where(HistoricalDataLoadRequestModel.id == request_id)
            .with_for_update()
        )
        if (
            row is None
            or row.status != "RUNNING"
            or coverage_summary.get("valid") is not True
            or experiment_validation.get("valid") is not True
        ):
            return False
        row.status = "COMPLETED"
        row.snapshot_id = snapshot_id
        row.coverage_summary = coverage_summary
        row.experiment_validation = experiment_validation
        row.finished_at = _now()
        row.updated_at = _now()
        session.flush()
        return True

    def fail_if_active(
        self,
        session: Session,
        request_id: UUID,
        *,
        category: str,
        code: str,
        detail: str,
    ) -> bool:
        row = session.scalar(
            select(HistoricalDataLoadRequestModel)
            .where(HistoricalDataLoadRequestModel.id == request_id)
            .with_for_update()
        )
        if row is None or row.status not in ACTIVE:
            return False
        row.status = "FAILED"
        row.failure_category = category
        row.failure_code = code[:80]
        row.failure_detail = detail[:500]
        row.finished_at = _now()
        row.updated_at = _now()
        session.flush()
        return True

    def resume(self, session: Session, request_id: UUID) -> bool:
        """Explicitly resume a failed load, retaining committed coverage facts."""
        row = session.scalar(
            select(HistoricalDataLoadRequestModel)
            .where(HistoricalDataLoadRequestModel.id == request_id)
            .with_for_update()
        )
        if row is None or row.status != "FAILED":
            return False
        row.status = "RUNNING"
        row.started_at = _now()
        row.finished_at = None
        row.failure_category = row.failure_code = row.failure_detail = None
        row.updated_at = _now()
        session.flush()
        return True

    def recover_interrupted(self, session: Session) -> int:
        rows = session.scalars(
            select(HistoricalDataLoadRequestModel)
            .where(HistoricalDataLoadRequestModel.status.in_(ACTIVE))
            .with_for_update()
        ).all()
        now = _now()
        for row in rows:
            previous = row.status
            row.status = "FAILED"
            row.failure_category = "RUNTIME"
            row.failure_code = (
                "LOAD_INTERRUPTED_BEFORE_START"
                if previous == "PENDING"
                else "LOAD_INTERRUPTED"
            )
            row.failure_detail = (
                "Historical load was interrupted and must be explicitly retried."
            )
            row.finished_at = now
            row.updated_at = now
        session.flush()
        return len(rows)
