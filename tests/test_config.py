from pathlib import Path

import pytest

from backend.config import Environment, Settings, load_config
from backend.core.errors import ConfigError


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


def test_settings_rejects_unknown_environment():
    with pytest.raises(ValueError):
        Settings(ATLAS_ENVIRONMENT="staging")


def test_load_config_returns_typed_yaml_config():
    config = load_config(Path("config/default.yaml"))

    assert config.strategy.name == "sma_crossover"
    assert config.strategy.parameters["fast_period"] == 10
    assert config.risk.max_open_positions == 5
    assert config.broker.mode == Environment.PAPER


def test_load_config_expands_environment_variables(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """strategy:
  name: ${STRATEGY_NAME}
  parameters: {}
risk:
  max_open_positions: 1
  per_trade_risk: 0.01
broker:
  name: paper
  mode: paper
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("STRATEGY_NAME", "breakout")

    assert load_config(config_path).strategy.name == "breakout"


def test_load_config_rejects_missing_environment_variable(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """strategy:
  name: ${MISSING_STRATEGY}
  parameters: {}
risk:
  max_open_positions: 1
  per_trade_risk: 0.01
broker:
  name: paper
  mode: paper
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="MISSING_STRATEGY"):
        load_config(config_path)


def test_load_config_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="Unable to read"):
        load_config(tmp_path / "missing.yaml")


def test_load_config_rejects_malformed_yaml(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("strategy: [", encoding="utf-8")

    with pytest.raises(ConfigError, match="Malformed YAML"):
        load_config(config_path)


def test_load_config_rejects_missing_sections(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("strategy:\n  name: test\n  parameters: {}\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="broker, risk"):
        load_config(config_path)


def test_load_config_rejects_invalid_mode(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """strategy:
  name: test
  parameters: {}
risk:
  max_open_positions: 1
  per_trade_risk: 0.01
broker:
  name: paper
  mode: staging
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="Invalid configuration"):
        load_config(config_path)


def test_broker_config_rejects_production_mode() -> None:
    """PRODUCTION mode must be rejected by the MVP safety guard.

    See ``context/architecture.md`` Production Mode section.
    """
    from pydantic import ValidationError

    from backend.config import BrokerConfig

    with pytest.raises(ValidationError, match="reserved"):
        BrokerConfig(name="binance", mode="production")
