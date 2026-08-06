"""REST bot CRUD and idempotent lifecycle commands."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from backend.api.bot_schemas import (
    BotCommandRequest,
    BotCreateRequest,
    BotLifecycleStatus,
    BotReadResponse,
    BotUpdateRequest,
    bot_response,
)
from backend.api.deps import BotServiceDep
from backend.bot.service import BotConflict, BotNotFound, BotValidationError
from backend.core.account_mode import AccountMode

router = APIRouter(prefix="/bots", tags=["bots"])


@router.post("", response_model=BotReadResponse, status_code=status.HTTP_201_CREATED)
async def create_bot(request: BotCreateRequest, service: BotServiceDep) -> BotReadResponse:
    try:
        bot = await service.create_bot(**request.model_dump())
    except BotValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return bot_response(bot)


@router.get("", response_model=list[BotReadResponse])
async def list_bots(
    service: BotServiceDep,
    account_id: Annotated[UUID | None, Query()] = None,
    mode: Annotated[AccountMode | None, Query()] = None,
) -> list[BotReadResponse]:
    return [
        bot_response(bot)
        for bot in await service.list_bots(account_id=account_id, mode=mode)
    ]


@router.get("/{bot_id}", response_model=BotReadResponse)
async def get_bot(
    bot_id: UUID,
    service: BotServiceDep,
    account_id: Annotated[UUID | None, Query()] = None,
    mode: Annotated[AccountMode | None, Query()] = None,
) -> BotReadResponse:
    try:
        return bot_response(await service.get_bot(bot_id, account_id=account_id, mode=mode))
    except BotNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.patch("/{bot_id}", response_model=BotReadResponse)
async def update_bot(
    bot_id: UUID, request: BotUpdateRequest, service: BotServiceDep
) -> BotReadResponse:
    try:
        changes = {key: value for key, value in request.model_dump().items() if value is not None}
        return bot_response(await service.update_bot(bot_id, **changes))
    except BotNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except BotConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except (BotValidationError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


async def _command(
    bot_id: UUID,
    request: BotCommandRequest,
    service: BotServiceDep,
    operation: str,
) -> BotReadResponse:
    try:
        result = await getattr(service, f"{operation}_bot")(
            bot_id, account_id=request.account_id, mode=request.mode
        )
        if result.status == BotLifecycleStatus.ERROR:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "bot_not_safe_to_execute",
                    "status": result.status,
                    "desired_status": result.desired_status,
                    "last_error": result.last_error,
                },
            )
        return bot_response(result)
    except BotNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except BotValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except BotConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/{bot_id}/start", response_model=BotReadResponse)
async def start_bot(
    bot_id: UUID, service: BotServiceDep, request: BotCommandRequest | None = None
) -> BotReadResponse:
    return await _command(bot_id, request or BotCommandRequest(), service, "start")


@router.post("/{bot_id}/stop", response_model=BotReadResponse)
async def stop_bot(
    bot_id: UUID, service: BotServiceDep, request: BotCommandRequest | None = None
) -> BotReadResponse:
    return await _command(bot_id, request or BotCommandRequest(), service, "stop")


@router.post("/{bot_id}/pause", response_model=BotReadResponse)
async def pause_bot(
    bot_id: UUID, service: BotServiceDep, request: BotCommandRequest | None = None
) -> BotReadResponse:
    return await _command(bot_id, request or BotCommandRequest(), service, "pause")


@router.post("/{bot_id}/resume", response_model=BotReadResponse)
async def resume_bot(
    bot_id: UUID, service: BotServiceDep, request: BotCommandRequest | None = None
) -> BotReadResponse:
    return await _command(bot_id, request or BotCommandRequest(), service, "resume")
