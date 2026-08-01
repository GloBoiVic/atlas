"""Cancellation-safe helpers for runtime resource cleanup."""

import asyncio
from collections.abc import Coroutine


async def await_cleanup[ResultT](coroutine: Coroutine[object, object, ResultT]) -> ResultT:
    """Finish cleanup before propagating cancellation from the caller."""
    task = asyncio.create_task(coroutine)
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True
    result = await task
    if cancelled:
        raise asyncio.CancelledError
    return result
