from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    DATABASE_URL_ASYNC: str
    # Only the test suite needs this; deployed jobs must never be given one.
    TEST_DATABASE_URL_ASYNC: str | None = None
    FEC_API_KEY: str | None = None
    ALLOWED_ORIGINS: str = "http://localhost:3000"
    # Comma-separated bearer keys the API accepts; two only while rotating.
    API_KEYS: str | None = None
    # Off unless a local .env turns it on: the API is private, so is its schema.
    EXPOSE_DOCS: bool = False

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def allowed_origins_list(self) -> list[str]:
        origins = self.ALLOWED_ORIGINS.split(",")
        return [origin.strip() for origin in origins if origin.strip()]

    @property
    def api_keys_list(self) -> list[str]:
        keys = (self.API_KEYS or "").split(",")
        return [key.strip() for key in keys if key.strip()]


@lru_cache()
def get_settings() -> Settings:
    # Required fields with no default are sourced from the environment/.env
    # file at runtime by BaseSettings; mypy has no way to know that.
    return Settings()  # type: ignore[call-arg]
