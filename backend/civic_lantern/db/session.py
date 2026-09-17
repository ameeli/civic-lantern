from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from civic_lantern.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.DATABASE_URL_ASYNC,
    future=True,
    echo=False,
    hide_parameters=True,
    pool_size=5,
    max_overflow=10,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)

# The nightly ingestion job is a batch process, not a request server: it
# alternates brief DB reads/writes with long DB-free stretches (paginated,
# rate-limited FEC API pulls that can run for hours on a full historical
# pull — see BaseIngestor._resolve_dates). Sharing the pooled `engine` above
# would keep a connection checked out idle for each such stretch, which
# blocks Neon's (or any autosuspend-on-idle Postgres's) ability to suspend
# compute and burns billed compute time for no reason. NullPool closes each
# connection as soon as it's checked back in instead of holding it for
# reuse, so a properly-ended transaction (see BaseIngestor._resolve_dates)
# actually releases the compute, not just the pool slot.
job_engine = create_async_engine(
    settings.DATABASE_URL_ASYNC,
    future=True,
    echo=False,
    hide_parameters=True,
    poolclass=NullPool,
)

JobSessionLocal = async_sessionmaker(
    bind=job_engine, class_=AsyncSession, expire_on_commit=False
)
