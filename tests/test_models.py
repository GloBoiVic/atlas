from uuid import UUID, uuid4

from backend.core.account_mode import AccountMode
from backend.persistence.database import Base
from backend.persistence.models import (
    Account,
    Bot,
    Candle,
    Instrument,
    ReconciliationRun,
    Strategy,
    StrategyVersion,
)


def test_account_mode_values() -> None:
    assert AccountMode.PAPER.value == "paper"
    assert AccountMode.TESTNET.value == "testnet"
    assert AccountMode.PRODUCTION.value == "production"


def test_account_has_required_fields() -> None:
    account_id = uuid4()
    account = Account(
        id=account_id,
        name="Test Account",
        broker="binance",
        mode=AccountMode.PAPER,
    )
    assert account.id == account_id
    assert isinstance(account.id, UUID)
    assert account.name == "Test Account"
    assert account.broker == "binance"
    assert account.mode == AccountMode.PAPER


def test_account_defaults_are_none_before_flush() -> None:
    account = Account(
        name="Test Account",
        broker="binance",
        mode=AccountMode.PAPER,
    )
    assert account.id is None
    assert account.created_at is None
    assert account.updated_at is None


def test_bot_contains_requested_and_observed_lifecycle_state() -> None:
    bot = Bot(
        name="momentum",
        account_id=uuid4(),
        broker="binance",
        mode="paper",
        instrument="BTCUSDT",
        timeframe="1m",
    )
    assert bot.desired_status is None
    assert bot.status is None
    assert "desired_status" in Bot.__table__.c
    assert "account_id" in Bot.__table__.c


def test_metadata_registers_all_bot_foreign_key_targets() -> None:
    assert {table.name for table in Base.metadata.sorted_tables} == {
        "accounts",
        "bots",
        "candles",
        "instruments",
        "reconciliation_runs",
        "strategies",
        "strategy_versions",
        "orders",
        "fills",
        "positions",
        "trades",
            "backtest_runs",
            "backtest_trades",
            "funding_adjustments",
            "journal_entries",
        }
    assert Strategy.__table__.c.name.unique is True
    assert StrategyVersion.__table__.c.strategy_id.foreign_keys


def test_strategy_timestamps_are_nullable_per_documented_schema() -> None:
    assert Strategy.__table__.c.created_at.nullable is True
    assert Strategy.__table__.c.updated_at.nullable is True


def test_bot_pnl_matches_documented_schema() -> None:
    pnl = Bot.__table__.c.pnl
    assert pnl.nullable is True
    assert str(pnl.type) == "NUMERIC(20, 8)"
    assert str(pnl.server_default.arg) == "0"


def test_reconciliation_run_has_json_snapshots() -> None:
    assert ReconciliationRun.__table__.c.broker_snapshot.nullable is False
    assert ReconciliationRun.__table__.c.differences.nullable is False


def test_bot_columns_use_uuid_type() -> None:
    from sqlalchemy import Uuid

    assert isinstance(Bot.__table__.c.id.type, Uuid)


def test_instrument_has_unique_symbol_provider_constraint() -> None:
    constraints = [
        c
        for c in Instrument.__table__.constraints  # type: ignore[attr-defined]
        if "symbol" in str(c) and "provider" in str(c)
    ]
    assert len(constraints) >= 1


def test_instrument_has_provider_columns() -> None:
    assert "symbol" in Instrument.__table__.c
    assert "provider" in Instrument.__table__.c
    assert "asset_type" in Instrument.__table__.c
    assert "constraints" in Instrument.__table__.c


def test_candle_has_uniqueness_constraint() -> None:
    constraints = [
        c
        for c in Candle.__table__.constraints  # type: ignore[attr-defined]
        if "instrument_id" in str(c) and "price_basis" in str(c)
    ]
    assert len(constraints) >= 1


def test_candle_has_lookup_index_matching_migration() -> None:
    indexes = {
        index.name: [column.name for column in index.columns]
        for index in Candle.__table__.indexes  # type: ignore[attr-defined]
    }

    assert indexes["idx_candles_lookup"] == [
        "instrument_id",
        "provider",
        "timeframe",
        "open_time",
    ]


def test_candle_has_volume_columns() -> None:
    assert "base_volume" in Candle.__table__.c
    assert "quote_volume" in Candle.__table__.c
    assert "trade_count" in Candle.__table__.c
    assert "tick_volume" in Candle.__table__.c


def test_candle_fk_to_instrument() -> None:
    assert Candle.__table__.c.instrument_id.foreign_keys
