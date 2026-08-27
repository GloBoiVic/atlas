"""HTTP boundary for server-owned OANDA historical loading."""

from datetime import UTC
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.market_data.historical_load import HistoricalDataLoadError
from backend.persistence.database import session_scope
from backend.persistence.historical_data_load_repository import (
    HistoricalDataLoadRepository,
)
from backend.persistence.models import DatasetSnapshotModel

from .schemas import (
    HistoricalDataCapabilityResponse,
    HistoricalDataLoadRequest,
    HistoricalDataLoadStatusResponse,
)

_HISTORICAL_PRODUCTS = [
    {"product": "analytical", "resolution": "M15", "components": ["MID"]},
    {"product": "execution", "resolution": "M1", "components": ["BID", "ASK"]},
]


def _error(code, message, details=None, code_status=400):
    return HTTPException(
        code_status,
        {"error": {"code": code, "message": message, "details": details or {}}},
    )


def _active_conflict_details(row):
    return {
        "requestId": str(row.id),
        "displayLabel": f"EUR/USD historical load · {_iso(row.created_at)}",
        "status": row.status,
        "statusUrl": f"/api/v1/historical-data/load-requests/{row.id}",
    }


def _iso(v):
    return v.astimezone(UTC).isoformat().replace("+00:00", "Z") if v else None


def _payload(
    row,
    base="/api/v1/historical-data/load-requests",
    snapshot_fingerprint=None,
    snapshot_policy_version=None,
):
    return {
        "id": row.id,
        "displayLabel": f"EUR/USD historical load · {_iso(row.created_at)}",
        "status": row.status,
        "statusUrl": f"{base}/{row.id}",
        "source": {
            "provider": "OANDA Practice",
            "instrument": "EUR/USD",
            "products": _HISTORICAL_PRODUCTS,
        },
        "requestedPeriod": {
            "start": _iso(row.trading_start),
            "end": _iso(row.trading_end),
        },
        "loadRange": {"start": _iso(row.load_start), "end": _iso(row.load_end)},
        "progress": {
            "fetchedRanges": row.fetched_ranges,
            "committedRanges": row.committed_ranges,
            "inserted": row.inserted,
            "reactivated": row.reactivated,
            "unchanged": row.unchanged,
        "incompleteMinuteCount": row.incomplete_minute_count,
        **(row.coverage_summary or {}).get("progress", {}),
        },
        "coverage": row.coverage_summary,
        "snapshot": {
            "id": row.snapshot_id,
            "fingerprint": snapshot_fingerprint,
            "policy_version": snapshot_policy_version,
        }
        if row.snapshot_id
        else None,
        "experimentValidation": row.experiment_validation,
        "failure": {
            "category": row.failure_category,
            "code": row.failure_code,
            "message": row.failure_detail,
            "nextAction": "Retry explicitly after reviewing coverage.",
            "partialDataMayExist": True,
        }
        if row.status == "FAILED"
        else None,
        "createdAt": _iso(row.created_at),
        "startedAt": _iso(row.started_at),
        "finishedAt": _iso(row.finished_at),
    }


def create_historical_data_router(
    *, session_factory, coordinator, available: bool
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/historical-data", tags=["historical-data"])
    repo = HistoricalDataLoadRepository()

    def db():
        with session_scope(session_factory) as session:
            yield session

    @router.get("/capability", response_model=HistoricalDataCapabilityResponse)
    def capability():
        return {
            "provider": "OANDA Practice",
            "instrument": "EUR/USD",
            "products": _HISTORICAL_PRODUCTS,
            "available": available,
            "reasonCode": None if available else "OANDA_HISTORICAL_UNAVAILABLE",
        }

    @router.get(
        "/load-requests/active", response_model=HistoricalDataLoadStatusResponse
    )
    def active(session: Session = Depends(db)):  # noqa: B008
        row = repo.active(session)
        if row is None:
            raise _error(
                "HISTORICAL_LOAD_NOT_ACTIVE",
                "No historical load is active.",
                code_status=404,
            )
        snapshot = (
            session.get(DatasetSnapshotModel, row.snapshot_id)
            if row.snapshot_id
            else None
        )
        return _payload(
            row,
            snapshot_fingerprint=snapshot.fingerprint if snapshot else None,
            snapshot_policy_version=(
                snapshot.session_policy if snapshot else None
            ),
        )

    @router.post(
        "/load-requests",
        status_code=202,
        response_model=HistoricalDataLoadStatusResponse,
    )
    def create(
        request: HistoricalDataLoadRequest,
        background: BackgroundTasks,
        response: Response,
        session: Session = Depends(db),  # noqa: B008
    ):
        if not available:
            raise _error(
                "OANDA_HISTORICAL_UNAVAILABLE",
                "Historical market data is unavailable.",
                code_status=503,
            )
        try:
            with session.begin():
                load_start, load_end = coordinator.prepare(
                    session,
                    strategy_version_id=request.strategy_version_id,
                    trading_start=request.trading_start,
                    trading_end=request.trading_end,
                )
                row = repo.create_pending(
                    session,
                    strategy_version_id=request.strategy_version_id,
                    trading_start=request.trading_start,
                    trading_end=request.trading_end,
                    load_start=load_start,
                    load_end=load_end,
                )
        except HistoricalDataLoadError as exc:
            raise _error(exc.code, str(exc), code_status=422) from exc
        except IntegrityError as exc:
            session.rollback()
            winner = repo.active(session)
            if winner:
                raise _error(
                    "HISTORICAL_LOAD_ACTIVE",
                    "Another historical load is already active.",
                    _active_conflict_details(winner),
                    409,
                ) from exc
            raise _error(
                "HISTORICAL_LOAD_ACTIVE",
                "Another historical load is already active.",
                code_status=409,
            ) from exc
        background.add_task(coordinator.run, row.id)
        response.headers["Location"] = f"/api/v1/historical-data/load-requests/{row.id}"
        snapshot = (
            session.get(DatasetSnapshotModel, row.snapshot_id)
            if row.snapshot_id
            else None
        )
        return _payload(
            row,
            snapshot_fingerprint=snapshot.fingerprint if snapshot else None,
            snapshot_policy_version=(
                snapshot.session_policy if snapshot else None
            ),
        )

    @router.get(
        "/load-requests/{request_id}", response_model=HistoricalDataLoadStatusResponse
    )
    def get(request_id: UUID, session: Session = Depends(db)):  # noqa: B008
        row = repo.get(session, request_id)
        if row is None:
            raise _error(
                "HISTORICAL_LOAD_NOT_FOUND",
                "Historical load was not found.",
                code_status=404,
            )
        snapshot = (
            session.get(DatasetSnapshotModel, row.snapshot_id)
            if row.snapshot_id
            else None
        )
        return _payload(
            row,
            snapshot_fingerprint=snapshot.fingerprint if snapshot else None,
            snapshot_policy_version=(
                snapshot.session_policy if snapshot else None
            ),
        )

    @router.post(
        "/load-requests/{request_id}/resume",
        response_model=HistoricalDataLoadStatusResponse,
        status_code=202,
    )
    def resume(
        request_id: UUID,
        background: BackgroundTasks,
        session: Session = Depends(db),  # noqa: B008
    ):
        with session.begin():
            if not repo.resume(session, request_id):
                raise _error(
                    "HISTORICAL_LOAD_NOT_RESUMABLE",
                    "Only a terminal historical load can be resumed explicitly.",
                    code_status=409,
                )
            row = repo.get(session, request_id)
        background.add_task(coordinator.run, request_id)
        return _payload(row)

    return router
