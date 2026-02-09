import pytest

from civic_lantern.schemas.candidate import CandidateIn
from civic_lantern.services.data.candidate import CandidateService


@pytest.mark.asyncio
class TestCandidateUpsert:
    """Test database upsert logic."""

    async def test_insert_new_candidate(self, async_db):
        """New candidate should be inserted."""
        service = CandidateService(db=async_db)

        candidates = [CandidateIn(candidate_id="C001", name="Test Candidate")]

        stats = await service.upsert_batch(candidates)

        assert stats["upserted"] == 1
        assert stats["errors"] == 0

        retrieved = await service.get_by_id("C001")
        assert retrieved.name == "Test Candidate"

    async def test_update_existing_candidate(self, async_db):
        """Existing candidate should be updated, not duplicated."""
        service = CandidateService(db=async_db)

        c1 = CandidateIn(candidate_id="C001", name="Original Name", party="DEM")
        await service.upsert_batch([c1])

        c2 = CandidateIn(candidate_id="C001", name="Updated Name", party="REP")
        await service.upsert_batch([c2])

        retrieved = await service.get_by_id("C001")
        assert retrieved.name == "Updated Name"
        assert retrieved.party == "REP"

    async def test_created_at_is_immutable(self, async_db):
        """Updating a record should NOT change its created_at timestamp."""
        service = CandidateService(db=async_db)

        c1 = CandidateIn(candidate_id="C_TIME", name="Original")
        await service.upsert_batch([c1])
        original_record = await service.get_by_id("C_TIME")
        original_ts = original_record.created_at

        async_db.expire(original_record)

        c2 = CandidateIn(candidate_id="C_TIME", name="Updated")
        await service.upsert_batch([c2])

        await async_db.commit()
        updated_record = await service.get_by_id("C_TIME")

        assert updated_record.name == "Updated"
        assert updated_record.created_at == original_ts
