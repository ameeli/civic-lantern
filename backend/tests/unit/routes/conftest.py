import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from civic_lantern.api.deps import get_db
from civic_lantern.main import app


@pytest_asyncio.fixture
async def api_client(mock_session):
    """AsyncClient wired to the FastAPI app with get_db overridden by mock_session."""

    async def _override():
        yield mock_session

    app.dependency_overrides[get_db] = _override
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
    app.dependency_overrides.clear()
