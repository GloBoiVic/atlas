from datetime import UTC, datetime, timedelta
from decimal import Decimal
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Numeric

from backend.journal.models import JournalDirection, JournalEntry
from backend.persistence.models import JournalEntryModel
from backend.persistence.repositories.memory import InMemoryJournalRepository


def make_entry(
    *, trade_id: UUID | None = None, opened_at: datetime | None = None, bot_id: UUID | None = None
) -> JournalEntry:
    return JournalEntry(
        account_id=uuid4(),
        trade_id=trade_id or uuid4(),
        bot_id=bot_id,
        instrument_id=uuid4(),
        symbol="BTCUSDT",
        direction=JournalDirection.LONG,
        entry_price=Decimal("100.123456789012"),
        exit_price=Decimal("101.123456789012"),
        quantity=Decimal("0.123456789012"),
        pnl=Decimal("-1.000000000001"),
        strategy_name="breakout",
        signal={"strength": "0.5"},
        market_conditions={"volatility": "high"},
        opened_at=opened_at or datetime(2026, 1, 1, tzinfo=UTC),
        closed_at=datetime(2026, 1, 1, 1, tzinfo=UTC),
    )


def test_journal_domain_accepts_signed_decimal_and_is_frozen() -> None:
    entry = make_entry()
    assert entry.pnl == Decimal("-1.000000000001")
    with pytest.raises((AttributeError, TypeError)):
        entry.notes = "review"  # type: ignore[misc]


def test_journal_model_uses_execution_precision_and_trade_uniqueness() -> None:
    for name in ("entry_price", "quantity", "pnl"):
        column_type = JournalEntryModel.__table__.c[name].type
        assert isinstance(column_type, Numeric)
        assert column_type.precision == 28
        assert column_type.scale == 12
    assert JournalEntryModel.__table__.c.trade_id.unique is True


@pytest.mark.asyncio
async def test_memory_journal_repository_is_idempotent_and_updates_only_notes() -> None:
    trade_id = uuid4()
    entry = make_entry(trade_id=trade_id)
    repository = InMemoryJournalRepository()

    assert await repository.create(entry) == entry
    duplicate = make_entry(trade_id=trade_id)
    assert await repository.create(duplicate) == entry
    updated = await repository.update_notes(entry.id, "good exit")
    assert updated is not None
    assert updated.notes == "good exit"
    assert updated.entry_price == entry.entry_price
    assert await repository.get_by_trade_id(trade_id) == updated


@pytest.mark.asyncio
async def test_memory_journal_repository_filters_inclusive_range_and_bot() -> None:
    bot_id = uuid4()
    first = make_entry(opened_at=datetime(2026, 1, 1, tzinfo=UTC), bot_id=bot_id)
    second = make_entry(opened_at=datetime(2026, 1, 2, tzinfo=UTC))
    repository = InMemoryJournalRepository([first, second])

    result = await repository.list_entries(
        start=first.opened_at,
        end=first.opened_at + timedelta(days=1),
        bot_id=bot_id,
    )
    assert result == [first]


def test_journal_migration_has_safe_revision_and_downgrade_order() -> None:
    path = Path(__file__).parents[1] / "alembic/versions/010_journal_entries.py"
    spec = spec_from_file_location("journal_migration", path)
    assert spec is not None and spec.loader is not None
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.revision == "010"
    assert migration.down_revision == "009"
    assert migration.upgrade.__name__ == "upgrade"
    assert migration.downgrade.__name__ == "downgrade"
