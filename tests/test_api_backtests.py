from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from backend.api.app import create_app
from backend.api.deps import get_backtest_service
from backend.backtester.models import BacktestResult, BacktestRun, BacktestStatus, BacktestTrade
from backend.backtester.service import BacktestRunConflict


def _run(run_id: UUID | None = None) -> BacktestRun:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return BacktestRun(
        id=run_id or uuid4(),
        strategy_name="sma",
        strategy_version="1.0.0",
        strategy_commit_sha="abc123",
        strategy_parameters={},
        instrument_id=uuid4(),
        symbol="BTCUSDT",
        timeframe="1h",
        data_source="csv",
        dataset_id="sha256:test",
        start_date=now,
        end_date=now,
        risk_config={},
        execution_config={
            "fee_rate": Decimal("0.001"),
            "fill_model": "next_candle_open",
            "protective_trigger_rule": "stop_loss_first",
        },
        fill_model="next_candle_open",
        status=BacktestStatus.COMPLETED,
        created_at=now,
        result=BacktestResult(
            total_return=Decimal("0.125"),
            total_pnl=Decimal("12.50"),
            starting_equity=Decimal("100.00"),
            ending_equity=Decimal("112.50"),
        ),
        completed_at=now,
    )


class FakeBacktestService:
    def __init__(
        self,
        run: BacktestRun | None = None,
        error: Exception | None = None,
        trades: list[BacktestTrade] | None = None,
        empty_list: bool = False,
    ) -> None:
        self.result_run = run or _run()
        self.error = error
        self.trades = trades or []
        self.empty_list = empty_list

    async def run(self, config: Any) -> BacktestRun:
        if self.error:
            raise self.error
        return self.result_run

    async def list_runs(self) -> list[BacktestRun]:
        return [] if self.empty_list else [self.result_run]

    async def get_run(self, run_id: UUID) -> BacktestRun | None:
        return self.result_run if run_id == self.result_run.id else None

    async def get_trades(self, run_id: UUID) -> list[BacktestTrade]:
        return self.trades


def _service_override(service: FakeBacktestService) -> Callable[[], FakeBacktestService]:
    def override() -> FakeBacktestService:
        return service

    return override


@pytest.fixture
def app():
    return create_app()


async def _post(app: Any, payload: dict[str, Any]) -> Any:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post("/backtests", json=payload)


def _payload() -> dict[str, Any]:
    return {
        "instrument_id": str(uuid4()),
        "account_id": str(uuid4()),
        "strategy_version_id": str(uuid4()),
        "timeframe": "1h",
        "start_date": "2026-01-01T00:00:00Z",
        "end_date": "2026-01-02T00:00:00Z",
        "initial_balance": "100.00",
    }


@pytest.mark.asyncio
async def test_create_backtest_serializes_decimal_metrics_as_strings(app):
    service = FakeBacktestService()
    app.dependency_overrides[get_backtest_service] = lambda: service
    try:
        response = await _post(app, _payload())
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["result"]["total_return"] == "0.125"
    assert response.json()["result"]["total_pnl"] == "12.50"


@pytest.mark.asyncio
async def test_create_backtest_rejects_imports_as_untrusted_configuration(app):
    payload = _payload()
    payload["strategy_parameters"] = {"import_path": "os.system"}
    response = await _post(app, payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_backtest_maps_conflicts_and_infrastructure_failures(app):
    for error, expected in (
        (BacktestRunConflict("active"), 409),
        (RuntimeError("database unavailable"), 500),
    ):
        service = FakeBacktestService(error=error)
        app.dependency_overrides[get_backtest_service] = _service_override(service)
        try:
            response = await _post(app, _payload())
        finally:
            app.dependency_overrides.clear()
        assert response.status_code == expected


@pytest.mark.asyncio
async def test_create_backtest_maps_resolution_value_errors_to_conflict(app):
    service = FakeBacktestService(error=ValueError("strategy version is not runnable"))
    app.dependency_overrides[get_backtest_service] = _service_override(service)
    try:
        response = await _post(app, _payload())
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 409
    assert response.json()["detail"] == "strategy version is not runnable"


@pytest.mark.asyncio
async def test_list_backtests_returns_empty_array(app):
    service = FakeBacktestService(empty_list=True)
    app.dependency_overrides[get_backtest_service] = _service_override(service)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/backtests")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_backtest_trades_serializes_trade_fields(app):
    run = _run()
    trade = BacktestTrade(
        backtest_run_id=run.id,
        instrument_id=run.instrument_id,
        symbol=run.symbol,
        direction="long",
        entry_price=Decimal("100.10"),
        exit_price=Decimal("101.20"),
        quantity=Decimal("0.50"),
        pnl=Decimal("0.55"),
        entry_time=run.start_date,
        exit_time=run.end_date,
        signal_metadata={"source": "test"},
    )
    service = FakeBacktestService(run=run, trades=[trade])
    app.dependency_overrides[get_backtest_service] = _service_override(service)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/backtests/{run.id}/trades")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json() == [
        {
            "id": str(trade.id),
            "backtest_run_id": str(run.id),
            "instrument_id": str(run.instrument_id),
            "symbol": "BTCUSDT",
            "direction": "long",
            "entry_price": "100.10",
            "exit_price": "101.20",
            "quantity": "0.50",
            "pnl": "0.55",
            "entry_time": "2026-01-01T00:00:00Z",
            "exit_time": "2026-01-01T00:00:00Z",
            "signal_metadata": {"source": "test"},
        }
    ]


@pytest.mark.asyncio
async def test_get_backtest_and_trades_return_404_for_missing_id(app):
    service = FakeBacktestService()
    app.dependency_overrides[get_backtest_service] = lambda: service
    missing = uuid4()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/backtests/{missing}")
        trades = await client.get(f"/backtests/{missing}/trades")
    app.dependency_overrides.clear()
    assert response.status_code == 404
    assert trades.status_code == 404
