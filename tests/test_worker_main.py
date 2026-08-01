from __future__ import annotations

import asyncio

import pytest

from backend.worker import main as worker_main


class FakeSupervisor:
    def __init__(self) -> None:
        self.restored = False
        self.shutdown_called = False

    async def restore_active(self) -> list[str]:
        self.restored = True
        worker_main.shutdown_event.set()
        return []

    async def shutdown(self) -> None:
        self.shutdown_called = True


@pytest.fixture(autouse=True)
def reset_shutdown_event() -> None:
    worker_main.shutdown_event.clear()


@pytest.mark.asyncio
async def test_worker_restores_and_shuts_down_injected_supervisor() -> None:
    supervisor = FakeSupervisor()

    await worker_main.run_worker(supervisor)  # type: ignore[arg-type]

    assert supervisor.restored is True
    assert supervisor.shutdown_called is True


@pytest.mark.asyncio
async def test_worker_without_supervisor_does_not_construct_runtime() -> None:
    worker_main.shutdown_event.set()

    await worker_main.run_worker()


@pytest.mark.asyncio
async def test_worker_shuts_down_supervisor_when_runtime_loop_is_cancelled() -> None:
    class BlockingSupervisor(FakeSupervisor):
        async def restore_active(self) -> list[str]:
            await asyncio.Event().wait()
            return []

    supervisor = BlockingSupervisor()
    task = asyncio.create_task(worker_main.run_worker(supervisor))  # type: ignore[arg-type]
    await asyncio.sleep(0)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert supervisor.shutdown_called is True


@pytest.mark.parametrize(
    "restore_error",
    [RuntimeError("restore failed"), asyncio.CancelledError()],
)
@pytest.mark.asyncio
async def test_worker_preserves_restore_failure_when_shutdown_also_fails(
    restore_error: BaseException,
) -> None:
    shutdown_error = RuntimeError("shutdown failed")

    class FailingSupervisor(FakeSupervisor):
        async def restore_active(self) -> list[str]:
            raise restore_error

        async def shutdown(self) -> None:
            self.shutdown_called = True
            raise shutdown_error

    supervisor = FailingSupervisor()

    with pytest.raises(RuntimeError, match="shutdown failed") as raised:
        await worker_main.run_worker(supervisor)  # type: ignore[arg-type]

    assert supervisor.shutdown_called is True
    assert raised.value.__context__ is restore_error
