from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest

from backend.worker.protocols import (
    BotPipeline,
    BotSnapshot,
    PipelineFactory,
    Reconciler,
    ReconciliationResult,
    ReconciliationStatus,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

_BOT_ID = UUID("00000000-0000-0000-0000-000000000001")
_ACCOUNT_ID = UUID("00000000-0000-0000-0000-000000000010")


def make_bot() -> BotSnapshot:
    return BotSnapshot(
        id=_BOT_ID,
        name="momentum",
        account_id=_ACCOUNT_ID,
        broker="paper",
        mode="paper",
        instrument="BTCUSDT",
        timeframe="1m",
        desired_status="running",
        status="stopped",
    )


class FakePipeline:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False
        self.execution_enabled = False

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    def set_execution_enabled(self, enabled: bool) -> None:
        self.execution_enabled = enabled


class FakeFactory:
    def create_pipeline(self, bot: BotSnapshot) -> BotPipeline:
        assert bot.id == _BOT_ID
        return FakePipeline()


class FakeReconciler:
    async def reconcile(self, bot: BotSnapshot) -> ReconciliationResult:
        assert bot.id == _BOT_ID
        return ReconciliationResult(status=ReconciliationStatus.MATCHED)


def test_runtime_implementations_satisfy_injected_protocols() -> None:
    pipeline = FakePipeline()

    assert isinstance(pipeline, BotPipeline)
    assert isinstance(FakeFactory(), PipelineFactory)
    assert isinstance(FakeReconciler(), Reconciler)


@pytest.mark.asyncio
async def test_pipeline_contract_controls_execution_independently_of_lifecycle() -> None:
    pipeline = FakePipeline()

    await pipeline.start()
    pipeline.set_execution_enabled(True)
    await pipeline.stop()

    assert pipeline.started is True
    assert pipeline.execution_enabled is True
    assert pipeline.stopped is True


@pytest.mark.parametrize(
    ("status", "safe"),
    [
        (ReconciliationStatus.MATCHED, True),
        (ReconciliationStatus.MISMATCHED, False),
        (ReconciliationStatus.FAILED, False),
    ],
)
def test_only_matched_reconciliation_is_safe_to_execute(
    status: ReconciliationStatus,
    safe: bool,
) -> None:
    result = ReconciliationResult(
        status=status,
        broker_snapshot={"position": "flat"},
        differences={"orders": ["order-1"]} if status is not ReconciliationStatus.MATCHED else {},
        error="broker unavailable" if status is ReconciliationStatus.FAILED else None,
    )

    assert result.is_safe_to_execute is safe


def test_reconciliation_result_preserves_typed_snapshot_mappings() -> None:
    snapshot: Mapping[str, object] = {"balance": "100.00", "positions": []}
    differences: Mapping[str, object] = {"orders": ["order-1"]}

    result = ReconciliationResult(
        status=ReconciliationStatus.MISMATCHED,
        broker_snapshot=snapshot,
        differences=differences,
    )

    assert result.broker_snapshot == snapshot
    assert result.differences == differences
