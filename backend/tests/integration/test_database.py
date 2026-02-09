import pytest
from sqlalchemy import select

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

    async def test_batch_pagination_logic(self, async_db):
        """Ensure data is processed correctly even when split across batches."""
        service = CandidateService(db=async_db)
        candidates = [
            CandidateIn(candidate_id=f"C_BATCH_{i}", name=f"Name {i}")
            for i in range(15)
        ]

        stats = await service.upsert_batch(candidates, batch_size=5)
        assert stats["upserted"] == 15

        result = await async_db.execute(
            select(service.model).where(service.model.candidate_id.like("C_BATCH_%"))
        )
        saved_candidates = result.scalars().all()

        assert len(saved_candidates) == 15

        saved_ids = {c.candidate_id for c in saved_candidates}
        assert "C_BATCH_0" in saved_ids
        assert "C_BATCH_14" in saved_ids

        batch_0 = next(c for c in saved_candidates if c.candidate_id == "C_BATCH_0")
        assert batch_0.name == "Name 0"
