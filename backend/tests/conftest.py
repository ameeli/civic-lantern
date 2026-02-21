import asyncio
from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from civic_lantern.core.config import get_settings
from civic_lantern.db.models import Base
from civic_lantern.services.fec_client import FECClient


@pytest_asyncio.fixture
async def async_db():
    settings = get_settings()

    engine = create_async_engine(settings.TEST_DATABASE_URL_ASYNC, echo=False)

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
    """Standard fixture to ensure the httpx client is closed after tests."""
    async with FECClient() as client:
        yield client


@pytest.fixture(autouse=True, scope="session")
def globally_silence_tqdm():
    """Silence all tqdm animations during tests by shimming gather."""

    async def silent_gather(*args, **kwargs):
        return await asyncio.gather(*args)

    with (
        patch(
            "civic_lantern.services.fec_client.tqdm_asyncio.gather",
            side_effect=silent_gather,
        ),
        patch("civic_lantern.services.fec_client.tqdm.write"),
    ):
        yield
