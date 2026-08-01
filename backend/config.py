import os
import re
from enum import StrEnum
from pathlib import Path
from typing import Any

import structlog
import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.core.errors import ConfigError

logger = structlog.get_logger(__name__)


class Environment(StrEnum):
    PAPER = "paper"
    TESTNET = "testnet"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Environment
    ATLAS_ENVIRONMENT: Environment = Environment.PAPER

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://atlas:atlas@localhost:5432/atlas"
    DATABASE_URL_SYNC: str = "postgresql://atlas:atlas@localhost:5432/atlas"

    # Binance
    BINANCE_API_KEY: str = ""
    BINANCE_API_SECRET: str = ""

    # Strategy repository
    STRATEGY_REPOSITORY_PATH: str = "/opt/atlas/strategies"

    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    @property
    def is_paper(self) -> bool:
        return self.ATLAS_ENVIRONMENT == Environment.PAPER

    @property
    def is_testnet(self) -> bool:
        return self.ATLAS_ENVIRONMENT == Environment.TESTNET

    @property
    def is_production(self) -> bool:
        return self.ATLAS_ENVIRONMENT == Environment.PRODUCTION


class StrategyConfig(BaseModel):
    """Strategy name and parameters loaded from the YAML configuration."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    parameters: dict[str, Any]


class RiskConfig(BaseModel):
    """Risk limits loaded from the YAML configuration."""

    model_config = ConfigDict(extra="forbid")

    max_open_positions: int = Field(gt=0)
    per_trade_risk: float = Field(gt=0, le=1)


class BrokerConfig(BaseModel):
    """Broker selection and deployment mode loaded from YAML."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    mode: Environment


class YamlConfig(BaseModel):
    """Typed strategy, risk, and broker configuration."""

    model_config = ConfigDict(extra="forbid")

    strategy: StrategyConfig
    risk: RiskConfig
    broker: BrokerConfig


_ENVIRONMENT_VARIABLE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _expand_environment_variables(contents: str) -> str:
    def replace(match: re.Match[str]) -> str:
        variable_name = match.group(1)
        value = os.environ.get(variable_name)
        if value is None:
            raise ConfigError(
                f"Environment variable {variable_name!r} is not set"
            )
        return value

    return _ENVIRONMENT_VARIABLE.sub(replace, contents)


def load_config(path: Path = Path("config/default.yaml")) -> YamlConfig:
    """Load and validate the typed YAML configuration.

    Args:
        path: YAML configuration file path.

    Returns:
        Validated strategy, risk, and broker configuration.

    Raises:
        ConfigError: If the file, environment expansion, YAML, or validation is invalid.
    """
    try:
        contents = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        logger.exception("configuration_read_failed", path=str(path))
        raise ConfigError(f"Unable to read configuration file {path}: {error}") from error

    try:
        expanded_contents = _expand_environment_variables(contents)
    except ConfigError:
        logger.exception("configuration_environment_expansion_failed", path=str(path))
        raise

    try:
        raw_config = yaml.safe_load(expanded_contents)
    except yaml.YAMLError as error:
        logger.exception("configuration_yaml_parse_failed", path=str(path))
        raise ConfigError(f"Malformed YAML in configuration file {path}: {error}") from error

    if not isinstance(raw_config, dict):
        logger.error("configuration_root_invalid", path=str(path))
        raise ConfigError("Configuration must contain strategy, risk, and broker sections")

    missing_sections = {"strategy", "risk", "broker"} - raw_config.keys()
    if missing_sections:
        section_names = ", ".join(sorted(missing_sections))
        logger.error(
            "configuration_sections_missing",
            path=str(path),
            missing_sections=section_names,
        )
        raise ConfigError(f"Configuration is missing required section(s): {section_names}")

    try:
        return YamlConfig.model_validate(raw_config)
    except ValidationError as error:
        logger.exception("configuration_validation_failed", path=str(path))
        raise ConfigError(f"Invalid configuration: {error}") from error


settings = Settings()
