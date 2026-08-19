from functools import lru_cache
from pathlib import Path

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str
    DATABASE_URL_ASYNC: str
    TEST_DATABASE_URL_ASYNC: str
    FEC_API_KEY: str | None = None
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    model_config = ConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def allowed_origins_list(self) -> list[str]:
        origins = self.ALLOWED_ORIGINS.split(",")
        return [origin.strip() for origin in origins if origin.strip()]


@lru_cache()
def get_settings() -> Settings:
    return Settings()
