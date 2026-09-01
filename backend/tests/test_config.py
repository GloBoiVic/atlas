import pytest
from pydantic import ValidationError

from backend.config import Environment, LogLevel, Settings


def valid_values() -> dict[str, object]:
    return {
        "database_url": "postgresql+psycopg://user:password@localhost/atlas",
    }


def test_valid_configuration_and_defaults() -> None:
    settings = Settings(_env_file=None, **valid_values())  # type: ignore[call-arg]
    assert settings.environment is Environment.DEVELOPMENT
    assert settings.log_level is LogLevel.INFO
    assert settings.database_connect_timeout_seconds == 3
    assert settings.oanda_account_id is None


def test_valid_explicit_oanda_account_id() -> None:
    settings = Settings(
        _env_file=None,
        **valid_values(),
        oanda_account_id="001-011-5838423-001",
    )  # type: ignore[call-arg]
    assert settings.oanda_account_id == "001-011-5838423-001"


@pytest.mark.parametrize(
    "account_id",
    ["", "001-011-5838423", "001-011-5838423-001/other", " 001-011-5838423-001"],
)
def test_invalid_oanda_account_id(account_id: str) -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            **valid_values(),
            oanda_account_id=account_id,
        )  # type: ignore[call-arg]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("database_url", "sqlite:///tmp/atlas.db"),
        ("environment", "invalid"),
        ("log_level", "invalid"),
        ("database_connect_timeout_seconds", 31),
    ],
)
def test_invalid_configuration(field: str, value: object) -> None:
    values = valid_values()
    values[field] = value
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, **values)  # type: ignore[call-arg]
    assert "password" not in str(error.value).lower()
    assert "postgresql+psycopg://user:password" not in str(error.value)


def test_missing_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ATLAS_DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_malformed_database_url() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url="postgresql+psycopg://user@/atlas")  # type: ignore[call-arg]
