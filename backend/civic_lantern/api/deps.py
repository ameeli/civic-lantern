from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from civic_lantern.db.session import AsyncSessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session."""
    async with AsyncSessionLocal() as session:
        yield session
