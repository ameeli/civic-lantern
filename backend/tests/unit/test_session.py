import pytest
from sqlalchemy.pool import NullPool

from civic_lantern.db.session import job_engine


@pytest.mark.unit
def test_job_engine_uses_null_pool():
    """The ingestion job's engine must not pool connections.

    Ingestion alternates brief DB reads/writes with long DB-free stretches
    (rate-limited FEC API pulls that can run for hours). A pooled engine
    would keep a connection checked out idle across those stretches,
    blocking Neon's autosuspend and burning compute for no reason.
    """
    assert isinstance(job_engine.pool, NullPool)
