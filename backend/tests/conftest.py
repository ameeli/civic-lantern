import pytest
import pytest_asyncio
from aiolimiter import AsyncLimiter
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from civic_lantern.core.config import get_settings
from civic_lantern.db.models import Base
from civic_lantern.services.fec_client import FECClient


@pytest.fixture(scope="session")
def test_database_url() -> str:
    url = get_settings().TEST_DATABASE_URL_ASYNC
    if not url:
        pytest.fail("TEST_DATABASE_URL_ASYNC must be set to run integration tests")
    return url


@pytest_asyncio.fixture
async def async_db(test_database_url):
    engine = create_async_engine(test_database_url, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def client():
    """Standard fixture to ensure the httpx client is closed after tests.

    Progress bars are off, and rate limiters are replaced with permissive ones
    so retry/pagination tests run at full speed (see TestFECClientRateLimiting).
    """
    async with FECClient(show_progress=False) as client:
        # FEC_API_KEY is optional in settings; pin one so tests don't depend on env.
        client.api_key = "test-api-key"
        client.limiter = AsyncLimiter(max_rate=10000, time_period=1)
        client.minute_limiter = AsyncLimiter(max_rate=10000, time_period=1)
        yield client
