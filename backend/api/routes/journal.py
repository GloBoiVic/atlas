"""Journal projection endpoints."""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException, Query

from backend.api.deps import JournalReadServiceDep
from backend.api.schemas import (
    JournalEntryResponse,
    JournalNotesUpdateRequest,
    journal_entry_response,
)
from backend.journal.service import JournalEntryNotFound

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/journal", tags=["journal"])


def _validate_dates(start_date: datetime | None, end_date: datetime | None) -> None:
    for value, name in ((start_date, "start_date"), (end_date, "end_date")):
        if value is not None and (
            value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value)
        ):
            raise HTTPException(status_code=422, detail=f"{name} must be UTC")
    if start_date is not None and end_date is not None and start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must not be after end_date")


@router.get("", response_model=list[JournalEntryResponse])
async def list_journal_entries(
    service: JournalReadServiceDep,
    start_date: Annotated[datetime | None, Query()] = None,
    end_date: Annotated[datetime | None, Query()] = None,
    bot_id: Annotated[UUID | None, Query()] = None,
) -> list[JournalEntryResponse]:
    _validate_dates(start_date, end_date)
    try:
        entries = await service.list_entries(start=start_date, end=end_date, bot_id=bot_id)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:
        logger.exception("journal_list_failure")
        raise HTTPException(status_code=500, detail="journal infrastructure failure") from error
    return [journal_entry_response(entry) for entry in entries]


@router.get("/{entry_id}", response_model=JournalEntryResponse)
async def get_journal_entry(entry_id: UUID, service: JournalReadServiceDep) -> JournalEntryResponse:
    try:
        entry = await service.get_entry(entry_id)
    except JournalEntryNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except Exception as error:
        logger.exception("journal_lookup_failure", entry_id=str(entry_id))
        raise HTTPException(status_code=500, detail="journal infrastructure failure") from error
    return journal_entry_response(entry)


@router.patch("/{entry_id}/notes", response_model=JournalEntryResponse)
async def update_journal_notes(
    entry_id: UUID,
    request: JournalNotesUpdateRequest,
    service: JournalReadServiceDep,
) -> JournalEntryResponse:
    try:
        entry = await service.update_notes(entry_id, request.notes)
    except JournalEntryNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except Exception as error:
        logger.exception("journal_notes_update_failure", entry_id=str(entry_id))
        raise HTTPException(status_code=500, detail="journal infrastructure failure") from error
    return journal_entry_response(entry)
