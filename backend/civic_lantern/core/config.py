from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    DATABASE_URL_ASYNC: str
    TEST_DATABASE_URL_ASYNC: str
    FEC_API_KEY: str | None = None
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    model_config = SettingsConfigDict(
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
    # Required fields with no default are sourced from the environment/.env
    # file at runtime by BaseSettings; mypy has no way to know that.
    return Settings()  # type: ignore[call-arg]
