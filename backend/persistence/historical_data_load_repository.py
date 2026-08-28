"""Persistence transitions for the one narrow historical-load command."""

import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import DatasetSnapshotModel, HistoricalDataLoadRequestModel

ACTIVE = ("PENDING", "RUNNING")
_PROGRESS_SCHEMA = "ATLAS_HISTORICAL_PROGRESS_V1"
_PROGRESS_PHASES = {
    "PLANNING",
    "ACQUIRING",
    "VALIDATING",
    "SNAPSHOT_MEMBERSHIP",
    "FINGERPRINTING",
    "FINALIZING",
    "COMPLETED",
    "FAILED",
}


def _validate_progress_payload(payload: dict) -> None:
    """Reject request-sized or ambiguous durable progress before writing it."""
    common = {
        "schema",
        "phase",
        "unit",
        "plan_generation",
        "completed_units",
        "total_units",
        "products",
    }
    phase = payload.get("phase")
    if payload.get("schema") != _PROGRESS_SCHEMA or phase not in _PROGRESS_PHASES:
        raise ValueError("invalid historical progress schema or phase")
    if set(payload) - (
        common
        | (
            {
                "current_product",
                "provider_calls_total",
                "inserted_rows",
                "reactivated_rows",
                "unchanged_rows",
                "latest_window",
            }
            if phase == "ACQUIRING"
            else {"elapsed_ms", "rows", "batches"}
            if phase != "PLANNING"
            else set()
        )
    ):
        raise ValueError("historical progress contains unsupported fields")
    for name in ("completed_units", "total_units"):
        values = payload.get(name)
        if not isinstance(values, dict) or set(values) != {"m15", "m1"}:
            raise ValueError("historical progress requires m15 and m1 units")
        if any(type(value) is not int or value < 0 for value in values.values()):
            raise ValueError("historical progress units must be non-negative integers")
    products = payload.get("products")
    if not isinstance(products, dict) or set(products) != {"m15", "m1"}:
        raise ValueError("historical progress requires both products")
    for key, product in products.items():
        if not isinstance(product, dict) or not {
            "expected_requests",
            "completed_requests",
        } <= set(product):
            raise ValueError("historical progress product counts are incomplete")
        allowed_product = (
            {
                "expected_requests",
                "completed_requests",
                "already_covered_window_count",
                "uncovered_span_count",
                "planning_elapsed_ms",
            }
            if phase == "PLANNING"
            else {"expected_requests", "completed_requests"}
        )
        if set(product) - allowed_product:
            raise ValueError("historical progress product contains unsupported fields")
        if any(
            type(product[key]) is not int or product[key] < 0
            for key in ("expected_requests", "completed_requests")
        ):
            raise ValueError("historical progress request counts are invalid")
        if product["completed_requests"] > product["expected_requests"]:
            raise ValueError("historical progress completion exceeds expected work")
        if (
            product["expected_requests"] != payload["total_units"][key]
            or product["completed_requests"] != payload["completed_units"][key]
        ):
            raise ValueError("historical progress product counts do not match units")
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    if len(encoded) > 8 * 1024:
        raise ValueError("historical progress exceeds the 8 KiB limit")


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
        progress_payload=None,
        telemetry=None,
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
        if progress_payload is not None:
            progress = dict(progress_payload)
            if "plan_generation" not in progress:
                progress["plan_generation"] = int(
                    previous_progress.get("plan_generation", 0)
                )
            _validate_progress_payload(progress)
            if progress["phase"] == "PLANNING":
                progress["plan_generation"] = int(
                    previous_progress.get("plan_generation", 0)
                ) + 1
                _validate_progress_payload(progress)
            summary = dict(coverage_summary or row.coverage_summary or {})
            summary["progress"] = progress
            if telemetry is not None:
                encoded = json.dumps(
                    telemetry, separators=(",", ":"), sort_keys=True
                ).encode()
                if len(encoded) > 8 * 1024:
                    raise ValueError("historical telemetry exceeds the 8 KiB limit")
                summary["telemetry"] = telemetry
            row.coverage_summary = summary
            row.updated_at = _now()
            session.flush()
            return True
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
            or session.get(DatasetSnapshotModel, snapshot_id) is None
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
