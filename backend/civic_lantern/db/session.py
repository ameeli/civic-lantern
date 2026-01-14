from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from civic_lantern.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.DATABASE_URL_ASYNC,
    future=True,
    echo=False,
    pool_size=5,
    max_overflow=10,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)
