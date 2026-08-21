from enum import StrEnum
from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ATLAS_", env_file=".env", extra="forbid", hide_input_in_errors=True
    )

    database_url: SecretStr
    environment: Environment = Environment.DEVELOPMENT
    log_level: LogLevel = LogLevel.INFO
    database_connect_timeout_seconds: int = Field(default=3, ge=1, le=30)
    oanda_api_token: SecretStr | None = None
    oanda_connect_timeout_seconds: int = Field(default=5, ge=1, le=30)
    oanda_read_timeout_seconds: int = Field(default=20, ge=1, le=120)

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        url = value.get_secret_value()
        if not url.startswith("postgresql+psycopg://"):
            raise ValueError("database_url must use postgresql+psycopg")
        if "@" not in url or "/" not in url.rsplit("@", 1)[-1]:
            raise ValueError("database_url is malformed")
        try:
            parsed = make_url(url)
        except Exception as error:
            raise ValueError("database_url is malformed") from error
        if not parsed.database or (not parsed.host and not parsed.query.get("host")):
            raise ValueError("database_url is malformed")
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
