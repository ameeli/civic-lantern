import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from civic_lantern.api.deps import get_db
from civic_lantern.core.config import get_settings
from civic_lantern.main import app

TEST_API_KEY = "test-api-key"


@pytest_asyncio.fixture
async def api_client(mock_session):
    """AsyncClient wired to the FastAPI app with get_db overridden by mock_session,
    authenticated with a test API key."""

    async def _override():
        yield mock_session

    settings = get_settings().model_copy(update={"API_KEYS": TEST_API_KEY})
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_db] = _override
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {TEST_API_KEY}"},
    ) as client:
        yield client
    app.dependency_overrides.clear()
