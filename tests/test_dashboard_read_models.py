from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.api.dashboard_schemas import PositionResponse, position_response
from backend.api.deps import AnalyticsScope, get_analytics_scope, get_dashboard_read_service
from backend.core.account_mode import AccountMode
from backend.dashboard.models import AccountRead, PositionRead
from backend.dashboard.service import DashboardReadService
from backend.persistence.repositories.dashboard_memory import InMemoryDashboardReadRepository


def _position(account_id, mode=AccountMode.PAPER):
    return PositionRead(
        id=uuid4(), account_id=account_id, bot_id=None, strategy_version_id=None,
        instrument_id=uuid4(), symbol="BTCUSDT", mode=mode, side="long",
        quantity=Decimal("0.10"), entry_price=Decimal("100"), current_price=Decimal("101"),
        unrealized_pnl=Decimal("0.10"), realized_pnl=Decimal("0"),
        opened_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_position_transport_serializes_decimal_values_as_strings():
    response = position_response(_position(uuid4()))
    assert response.quantity == "0.10"


def test_position_transport_rejects_naive_timestamp():
    position = _position(uuid4())
    with pytest.raises(ValueError, match="opened_at must be UTC"):
        PositionResponse.model_validate(
            {**asdict(position), "mode": "paper", "quantity": "0.10",
             "entry_price": "100", "current_price": "101", "unrealized_pnl": "0.10",
             "realized_pnl": "0", "opened_at": datetime(2026, 1, 1)},
        )


@pytest.mark.asyncio
async def test_dashboard_service_keeps_account_and_mode_isolation():
    account_id = uuid4()
    account = AccountRead(account_id, "Paper", "binance_usdm", AccountMode.PAPER,
                          datetime(2026, 1, 1, tzinfo=UTC))
    repository = InMemoryDashboardReadRepository(
        accounts=[account],
        positions=[_position(account_id), _position(account_id, AccountMode.TESTNET)],
    )
    result = await DashboardReadService(repository).list_positions(
        AnalyticsScope(account_id, Decimal("1000"), AccountMode.PAPER)
    )
    assert len(result) == 1
    assert result[0].mode is AccountMode.PAPER


def test_dashboard_routes_fail_closed_without_deployment_scope():
    app = create_app()
    app.dependency_overrides[get_analytics_scope] = lambda: None
    app.dependency_overrides[get_dashboard_read_service] = lambda: DashboardReadService(
        InMemoryDashboardReadRepository()
    )
    with TestClient(app) as client:
        response = client.get("/dashboard")
    assert response.status_code == 503
