import pytest

from civic_lantern.core.config import get_settings
from civic_lantern.main import docs_routes


@pytest.mark.unit
class TestDocsExposure:
    def test_docs_are_off_by_default(self):
        settings = get_settings().model_copy(update={"EXPOSE_DOCS": False})
        assert docs_routes(settings) == {
            "docs_url": None,
            "redoc_url": None,
            "openapi_url": None,
        }

    def test_docs_can_be_enabled_locally(self):
        settings = get_settings().model_copy(update={"EXPOSE_DOCS": True})
        assert docs_routes(settings) == {
            "docs_url": "/docs",
            "redoc_url": "/redoc",
            "openapi_url": "/openapi.json",
        }

    def test_setting_defaults_to_off(self, monkeypatch):
        monkeypatch.delenv("EXPOSE_DOCS", raising=False)
        monkeypatch.setenv("DATABASE_URL_ASYNC", "postgresql+asyncpg://unused")
        settings = type(get_settings())(_env_file=None)
        assert settings.EXPOSE_DOCS is False
