import hashlib
import hmac
from collections.abc import AsyncGenerator
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from civic_lantern.core.config import Settings, get_settings
from civic_lantern.db.session import AsyncSessionLocal

# auto_error=False so every failure returns the same 401 below.
_bearer = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session."""
    async with AsyncSessionLocal() as session:
        yield session


@dataclass
class PaginationParams:
    """Shared limit/offset query params for paginated list endpoints."""

    limit: int = Query(100, ge=1, le=1000)
    offset: int = Query(0, ge=0)


def require_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> None:
    """Reject requests without one of the configured API keys as a bearer token."""
    keys = settings.api_keys_list
    if not keys:
        # Fail closed: a missing setting must never leave the API open.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API_KEYS is not configured",
        )
    presented = credentials.credentials if credentials else ""
    if not any(_same_secret(presented, key) for key in keys):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _same_secret(a: str, b: str) -> bool:
    # Hash first so the comparison is constant-time and leaks no length.
    return hmac.compare_digest(_sha256(a), _sha256(b))


def _sha256(value: str) -> bytes:
    return hashlib.sha256(value.encode()).digest()
