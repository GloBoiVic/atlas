from backend.config import Environment, Settings


def test_default_environment_is_paper():
    settings = Settings(
        DATABASE_URL="sqlite+aiosqlite://",
        DATABASE_URL_SYNC="sqlite://",
    )
    assert settings.ATLAS_ENVIRONMENT == Environment.PAPER
    assert settings.is_paper is True
    assert settings.is_testnet is False
    assert settings.is_production is False


def test_paper_mode_properties():
    settings = Settings(
        ATLAS_ENVIRONMENT="paper",
        DATABASE_URL="sqlite+aiosqlite://",
        DATABASE_URL_SYNC="sqlite://",
    )
    assert settings.is_paper is True
    assert settings.is_testnet is False
    assert settings.is_production is False


def test_testnet_mode_properties():
    settings = Settings(
        ATLAS_ENVIRONMENT="testnet",
        DATABASE_URL="sqlite+aiosqlite://",
        DATABASE_URL_SYNC="sqlite://",
    )
    assert settings.is_paper is False
    assert settings.is_testnet is True
    assert settings.is_production is False


def test_production_mode_properties():
    settings = Settings(
        ATLAS_ENVIRONMENT="production",
        DATABASE_URL="sqlite+aiosqlite://",
        DATABASE_URL_SYNC="sqlite://",
    )
    assert settings.is_paper is False
    assert settings.is_testnet is False
    assert settings.is_production is True
