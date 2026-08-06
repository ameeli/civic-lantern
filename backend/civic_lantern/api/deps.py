from collections.abc import AsyncGenerator
from dataclasses import dataclass

from fastapi import Query
from sqlalchemy.ext.asyncio import AsyncSession

from civic_lantern.db.session import AsyncSessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session."""
    async with AsyncSessionLocal() as session:
        yield session


@dataclass
class PaginationParams:
    """Shared limit/offset query params for paginated list endpoints."""

    limit: int = Query(100, ge=1, le=1000)
    offset: int = Query(0, ge=0)
