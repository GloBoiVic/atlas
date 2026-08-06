from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from backend.analytics.metrics import EquityPoint, PerformanceMetrics
from backend.api.app import create_app
from backend.api.deps import (
    AnalyticsScope,
    get_analytics_scope,
    get_analytics_service,
    get_journal_read_service,
)
from backend.journal.models import JournalDirection, JournalEntry
from backend.journal.service import JournalEntryNotFound

NOW = datetime(2026, 1, 2, tzinfo=UTC)


def _entry() -> JournalEntry:
    return JournalEntry(
        account_id=uuid4(),
        trade_id=uuid4(),
        symbol="BTCUSDT",
        direction=JournalDirection.LONG,
        entry_price=Decimal("100.10"),
        exit_price=Decimal("101.20"),
        quantity=Decimal("0.50"),
        pnl=Decimal("0.55"),
        strategy_name="breakout",
        opened_at=NOW,
        closed_at=NOW,
        signal={"reason": "breakout"},
    )


class FakeJournalReadService:
    def __init__(self, entries: list[JournalEntry]) -> None:
        self.entries = entries
        self.received: dict[str, object] = {}

    async def list_entries(
        self, *, start: datetime | None, end: datetime | None, bot_id: UUID | None
    ) -> list[JournalEntry]:
        self.received = {"start": start, "end": end, "bot_id": bot_id}
        return self.entries

    async def get_entry(self, entry_id: UUID) -> JournalEntry:
        for entry in self.entries:
            if entry.id == entry_id:
                return entry
        raise JournalEntryNotFound("journal entry not found")

    async def update_notes(self, entry_id: UUID, notes: str | None) -> JournalEntry:
        entry = await self.get_entry(entry_id)
        return replace(entry, notes=notes)


class FakeAnalyticsService:
    async def get_metrics(self, **_: object) -> PerformanceMetrics:
        return PerformanceMetrics(
            total_return=Decimal("0.125"),
            total_pnl=Decimal("12.50"),
            starting_equity=Decimal("100.00"),
            ending_equity=Decimal("112.50"),
            win_rate=1.0,
            closed_trade_daily_sharpe=None,
            max_drawdown=Decimal("0"),
            profit_factor=None,
            total_trades=1,
            winning_trades=1,
            losing_trades=0,
            equity_curve=(EquityPoint(NOW, Decimal("100.00"), Decimal("0")),),
        )


async def _request(app: Any, method: str, path: str, **kwargs: Any) -> Any:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, **kwargs)


@pytest.fixture
def app():
    return create_app()


@pytest.mark.asyncio
async def test_journal_list_filters_and_serializes_decimal_strings(app: Any) -> None:
    entry = _entry()
    service = FakeJournalReadService([entry])
    bot_id = uuid4()
    app.dependency_overrides[get_journal_read_service] = lambda: service
    try:
        response = await _request(
            app,
            "GET",
            f"/journal?start_date={NOW.isoformat().replace('+00:00', 'Z')}&"
            f"end_date={NOW.isoformat().replace('+00:00', 'Z')}&bot_id={bot_id}",
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()[0]["entry_price"] == "100.10"
    assert service.received["bot_id"] == bot_id


@pytest.mark.asyncio
async def test_journal_empty_and_detail_not_found(app: Any) -> None:
    service = FakeJournalReadService([])
    app.dependency_overrides[get_journal_read_service] = lambda: service
    try:
        empty = await _request(app, "GET", "/journal")
        missing = await _request(app, "GET", f"/journal/{uuid4()}")
    finally:
        app.dependency_overrides.clear()
    assert empty.status_code == 200 and empty.json() == []
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_journal_notes_update(app: Any) -> None:
    entry = _entry()
    service = FakeJournalReadService([entry])
    app.dependency_overrides[get_journal_read_service] = lambda: service
    try:
        response = await _request(
            app, "PATCH", f"/journal/{entry.id}/notes", json={"notes": "reviewed"}
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["notes"] == "reviewed"


@pytest.mark.asyncio
async def test_journal_rejects_non_utc_and_invalid_uuid(app: Any) -> None:
    service = FakeJournalReadService([])
    app.dependency_overrides[get_journal_read_service] = lambda: service
    try:
        naive = await _request(app, "GET", "/journal?start_date=2026-01-01T00:00:00")
        invalid = await _request(app, "GET", "/journal/not-a-uuid")
    finally:
        app.dependency_overrides.clear()
    assert naive.status_code == 422
    assert invalid.status_code == 422


@pytest.mark.asyncio
async def test_analytics_serializes_decimal_values_and_null_ratios(app: Any) -> None:
    app.dependency_overrides[get_analytics_service] = FakeAnalyticsService
    app.dependency_overrides[get_analytics_scope] = lambda: AnalyticsScope(
        account_id=uuid4(), starting_equity=Decimal("100.00")
    )
    try:
        response = await _request(app, "GET", "/analytics")
    finally:
        app.dependency_overrides.clear()
    body = response.json()
    assert response.status_code == 200
    assert body["total_return"] == "0.125"
    assert body["total_pnl"] == "12.50"
    assert body["profit_factor"] is None
    assert body["equity_curve"][0]["equity"] == "100.00"


@pytest.mark.asyncio
async def test_analytics_scope_is_fail_closed_and_dates_are_utc(app: Any) -> None:
    app.dependency_overrides[get_analytics_service] = FakeAnalyticsService
    try:
        unavailable = await _request(app, "GET", "/analytics")
        invalid = await _request(app, "GET", "/analytics?start_date=2026-01-01T00:00:00")
    finally:
        app.dependency_overrides.clear()
    assert unavailable.status_code == 503
    assert invalid.status_code == 422
