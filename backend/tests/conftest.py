import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from civic_lantern.core.config import get_settings
from civic_lantern.db.models import Base


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
