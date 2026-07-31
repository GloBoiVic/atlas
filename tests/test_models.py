from backend.persistence.models import Account, AccountMode


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
