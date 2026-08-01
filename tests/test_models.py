from backend.core.account_mode import AccountMode
from backend.persistence.models import Account, Bot, BotRun, ReconciliationRun


def test_account_mode_values():
    assert AccountMode.PAPER == "paper"
    assert AccountMode.TESTNET == "testnet"
    assert AccountMode.PRODUCTION == "production"


def test_account_has_required_fields():
    account = Account(
        id="test-id-123",
        name="Test Account",
        broker="binance",
        mode=AccountMode.PAPER,
    )
    assert account.id == "test-id-123"
    assert account.name == "Test Account"
    assert account.broker == "binance"
    assert account.mode == AccountMode.PAPER


def test_account_defaults_are_none_before_flush():
    account = Account(
        name="Test Account",
        broker="binance",
        mode=AccountMode.PAPER,
    )
    assert account.id is None
    assert account.created_at is None
    assert account.updated_at is None


def test_bot_contains_requested_and_observed_lifecycle_state():
    bot = Bot(
        name="momentum",
        account_id="account-id",
        broker="binance",
        mode="paper",
        instrument="BTCUSDT",
        timeframe="1m",
    )

    assert bot.desired_status is None
    assert bot.status is None
    assert "desired_status" in Bot.__table__.c
    assert "account_id" in Bot.__table__.c


def test_bot_run_has_worker_lease_fields():
    assert BotRun.__table__.c.worker_id.nullable is True
    assert BotRun.__table__.c.locked_at.nullable is True
    assert BotRun.__table__.c.bot_id.foreign_keys.pop().ondelete == "CASCADE"


def test_reconciliation_run_has_json_snapshots():
    assert ReconciliationRun.__table__.c.broker_snapshot.nullable is False
    assert ReconciliationRun.__table__.c.differences.nullable is False
