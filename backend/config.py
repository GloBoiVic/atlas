from enum import StrEnum

from pydantic_settings import BaseSettings


class Environment(StrEnum):
    PAPER = "paper"
    TESTNET = "testnet"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

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


settings = Settings()
