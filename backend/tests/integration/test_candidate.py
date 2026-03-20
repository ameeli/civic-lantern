import asyncio
from datetime import date

import pytest
from sqlalchemy import select

from civic_lantern.db.models.enums import OfficeTypeEnum
from civic_lantern.schemas.candidate import CandidateIn
from civic_lantern.services.data.candidate import CandidateService


@pytest.mark.integration
@pytest.mark.asyncio
class TestUpsertBatch:
    async def test_insert_new_candidate(self, async_db):
        """Test that basic insert is successful."""
        service = CandidateService(db=async_db)

        candidates = [CandidateIn(candidate_id="C001", name="Test Candidate")]

        stats = await service.upsert_batch(candidates)

        assert stats["inserted"] == 1
        assert stats["errors"] == 0

        retrieved = await service.get_by_id("C001")
        assert retrieved.name == "Test Candidate"

    async def test_upsert_empty_list(self, async_db):
        """Empty input should resolve without error."""
        service = CandidateService(db=async_db)

        stats = await service.upsert_batch([])

        assert stats["inserted"] == 0
        assert stats["updated"] == 0
        assert stats["errors"] == 0
        assert stats["failed_ids"] == []

    async def test_update_existing_candidate(self, async_db):
        "Existing candidates are successfully updated."
        service = CandidateService(db=async_db)

        c1 = CandidateIn(candidate_id="C001", name="Original Name", party="DEM")
        await service.upsert_batch([c1])

        c2 = CandidateIn(candidate_id="C001", name="Updated Name", party="REP")
        await service.upsert_batch([c2])

        retrieved = await service.get_by_id("C001")
        assert retrieved.name == "Updated Name"
        assert retrieved.party == "REP"

    async def test_created_at_is_immutable(self, async_db):
        """Updating an existing record should not change created_at."""
        service = CandidateService(db=async_db)

        c1 = CandidateIn(candidate_id="C_TIME", name="Original")
        await service.upsert_batch([c1])
        original = await service.get_by_id("C_TIME")
        original_ts = original.created_at

        async_db.expire(original)

        c2 = CandidateIn(candidate_id="C_TIME", name="Updated")
        await service.upsert_batch([c2])

        await async_db.commit()
        updated_record = await service.get_by_id("C_TIME")

        assert updated_record.name == "Updated"
        assert updated_record.created_at == original_ts

    async def test_updated_at_changes_on_update(self, async_db):
        """Verify that the PostgreSQL trigger refreshes updated_at on upsert."""
        service = CandidateService(db=async_db)

        c1 = CandidateIn(candidate_id="C_UPDATE_TIME", name="Original")
        await service.upsert_batch([c1])
        original = await service.get_by_id("C_UPDATE_TIME")
        original_updated_at = original.updated_at

        async_db.expire(original)
        await asyncio.sleep(0.1)

        c2 = CandidateIn(candidate_id="C_UPDATE_TIME", name="Updated")
        await service.upsert_batch([c2])
        updated = await service.get_by_id("C_UPDATE_TIME")

        assert updated.updated_at > original_updated_at

    async def test_batch_pagination_logic(self, async_db):
        """Ensure data is processed correctly even when split across batches."""
        service = CandidateService(db=async_db)
        candidates = [
            CandidateIn(candidate_id=f"C_BATCH_{i}", name=f"Name {i}")
            for i in range(15)
        ]

        stats = await service.upsert_batch(candidates, batch_size=5)
        assert stats["inserted"] == 15

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

    async def test_mixed_insert_and_update_in_same_batch(self, async_db):
        """Batch with both new and existing records should handle correctly."""
        service = CandidateService(db=async_db)

        existing = CandidateIn(candidate_id="C_EXIST", name="Existing")
        await service.upsert_batch([existing])

        mixed_batch = [
            CandidateIn(candidate_id="C_EXIST", name="Updated Existing"),
            CandidateIn(candidate_id="C_NEW_1", name="New One"),
            CandidateIn(candidate_id="C_NEW_2", name="New Two"),
        ]

        stats = await service.upsert_batch(mixed_batch)

        assert stats["inserted"] + stats["updated"] == 3
        assert stats["errors"] == 0

        updated = await service.get_by_id("C_EXIST")
        assert updated.name == "Updated Existing"

        assert await service.get_by_id("C_NEW_1") is not None
        assert await service.get_by_id("C_NEW_2") is not None

    async def test_invalid_data_triggers_row_by_row_fallback(self, async_db):
        """Invalid record in batch should trigger fallback and track errors."""
        service = CandidateService(db=async_db)

        batch = [
            {"candidate_id": "C_VALID_1", "name": "Valid One"},
            {"candidate_id": "C_INVALID"},
            {"candidate_id": "C_VALID_2", "name": "Valid Two"},
        ]

        stats = await service.upsert_batch(batch)

        assert stats["inserted"] + stats["updated"] == 2
        assert stats["errors"] == 1
        assert "C_INVALID" in stats["failed_ids"]

        assert await service.get_by_id("C_VALID_1") is not None
        assert await service.get_by_id("C_VALID_2") is not None
        assert await service.get_by_id("C_INVALID") is None

    async def test_duplicate_ids_in_same_batch(self, async_db):
        """Multiple records with same ID in one batch - last one wins."""
        service = CandidateService(db=async_db)

        batch = [
            CandidateIn(candidate_id="C_DUP", name="First"),
            CandidateIn(candidate_id="C_DUP", name="Second"),
            CandidateIn(candidate_id="C_DUP", name="Third"),
        ]

        stats = await service.upsert_batch(batch)
        assert stats["inserted"] + stats["updated"] == 3

        retrieved = await service.get_by_id("C_DUP")
        assert retrieved.name == "Third"

        result = await async_db.execute(
            select(service.model).where(service.model.candidate_id == "C_DUP")
        )
        all_dups = result.scalars().all()
        assert len(all_dups) == 1


@pytest.mark.integration
@pytest.mark.asyncio
class TestCandidateGetList:
    async def test_returns_seeded_rows(self, async_db):
        service = CandidateService(db=async_db)
        await service.upsert_batch([CandidateIn(candidate_id="C001", name="Alice")])

        result = await service.get_list(state=None, office=None, cycle=None)

        assert result["total_count"] == 1
        assert len(result["items"]) == 1
        assert result["items"][0].candidate_id == "C001"

    async def test_empty_returns_empty(self, async_db):
        service = CandidateService(db=async_db)
        result = await service.get_list(state=None, office=None, cycle=None)

        assert result["total_count"] == 0
        assert len(result["items"]) == 0

    async def test_filter_by_state(self, async_db):
        service = CandidateService(db=async_db)
        await service.upsert_batch(
            [
                CandidateIn(candidate_id="C001", name="Alice", state="CA"),
                CandidateIn(candidate_id="C002", name="Bob", state="TX"),
                CandidateIn(candidate_id="C003", name="Carol", state="CA"),
            ]
        )

        result = await service.get_list(state="CA", office=None, cycle=None)

        assert result["total_count"] == 2
        ids = {r.candidate_id for r in result["items"]}
        assert ids == {"C001", "C003"}

    async def test_filter_by_office(self, async_db):
        service = CandidateService(db=async_db)
        await service.upsert_batch(
            [
                CandidateIn(
                    candidate_id="C001", name="Alice", office=OfficeTypeEnum.HOUSE
                ),
                CandidateIn(
                    candidate_id="C002", name="Bob", office=OfficeTypeEnum.SENATE
                ),
                CandidateIn(
                    candidate_id="C003", name="Carol", office=OfficeTypeEnum.HOUSE
                ),
            ]
        )

        result = await service.get_list(
            state=None, office=OfficeTypeEnum.HOUSE, cycle=None
        )

        assert result["total_count"] == 2
        ids = {r.candidate_id for r in result["items"]}
        assert ids == {"C001", "C003"}

    async def test_filter_by_cycle(self, async_db):
        service = CandidateService(db=async_db)
        await service.upsert_batch(
            [
                CandidateIn(candidate_id="C001", name="Alice", cycles=[2020, 2022]),
                CandidateIn(candidate_id="C002", name="Bob", cycles=[2022, 2024]),
                CandidateIn(candidate_id="C003", name="Carol", cycles=[2024]),
            ]
        )

        result = await service.get_list(state=None, office=None, cycle=2022)

        assert result["total_count"] == 2
        ids = {r.candidate_id for r in result["items"]}
        assert ids == {"C001", "C002"}

    async def test_filters_are_combinable(self, async_db):
        """state + office together narrow results correctly."""
        service = CandidateService(db=async_db)
        await service.upsert_batch(
            [
                CandidateIn(
                    candidate_id="C001",
                    name="Alice",
                    state="CA",
                    office=OfficeTypeEnum.HOUSE,
                ),
                CandidateIn(
                    candidate_id="C002",
                    name="Bob",
                    state="CA",
                    office=OfficeTypeEnum.SENATE,
                ),
                CandidateIn(
                    candidate_id="C003",
                    name="Carol",
                    state="TX",
                    office=OfficeTypeEnum.HOUSE,
                ),
            ]
        )

        result = await service.get_list(
            state="CA", office=OfficeTypeEnum.HOUSE, cycle=None
        )

        assert result["total_count"] == 1
        assert result["items"][0].candidate_id == "C001"

    async def test_pagination_limit_and_offset(self, async_db):
        service = CandidateService(db=async_db)
        await service.upsert_batch(
            [
                CandidateIn(candidate_id=f"C{i:03d}", name=f"Candidate {i}")
                for i in range(5)
            ]
        )

        result = await service.get_list(
            state=None, office=None, cycle=None, limit=2, offset=0
        )

        assert result["total_count"] == 5
        assert len(result["items"]) == 2
        assert result["limit"] == 2
        assert result["offset"] == 0

    async def test_total_count_independent_of_limit(self, async_db):
        service = CandidateService(db=async_db)
        await service.upsert_batch(
            [
                CandidateIn(candidate_id=f"C{i:03d}", name=f"Candidate {i}")
                for i in range(5)
            ]
        )

        result = await service.get_list(
            state=None, office=None, cycle=None, limit=2, offset=2
        )

        assert result["total_count"] == 5
        assert len(result["items"]) == 2

    async def test_sort_by_name_asc(self, async_db):
        service = CandidateService(db=async_db)
        await service.upsert_batch(
            [
                CandidateIn(candidate_id="C001", name="Charlie"),
                CandidateIn(candidate_id="C002", name="Alice"),
                CandidateIn(candidate_id="C003", name="Bob"),
            ]
        )

        result = await service.get_list(
            state=None, office=None, cycle=None, sort_by="name", order="asc"
        )

        assert [r.name for r in result["items"]] == ["Alice", "Bob", "Charlie"]

    async def test_sort_by_name_desc(self, async_db):
        service = CandidateService(db=async_db)
        await service.upsert_batch(
            [
                CandidateIn(candidate_id="C001", name="Charlie"),
                CandidateIn(candidate_id="C002", name="Alice"),
                CandidateIn(candidate_id="C003", name="Bob"),
            ]
        )

        result = await service.get_list(
            state=None, office=None, cycle=None, sort_by="name", order="desc"
        )

        assert [r.name for r in result["items"]] == ["Charlie", "Bob", "Alice"]

    async def test_sort_by_first_file_date_asc(self, async_db):
        service = CandidateService(db=async_db)
        await service.upsert_batch(
            [
                CandidateIn(
                    candidate_id="C001", name="Alice", first_file_date=date(2018, 3, 1)
                ),
                CandidateIn(
                    candidate_id="C002", name="Bob", first_file_date=date(2016, 1, 15)
                ),
                CandidateIn(
                    candidate_id="C003", name="Carol", first_file_date=date(2020, 6, 10)
                ),
            ]
        )

        result = await service.get_list(
            state=None, office=None, cycle=None, sort_by="first_file_date", order="asc"
        )

        assert [r.candidate_id for r in result["items"]] == ["C002", "C001", "C003"]

    @pytest.mark.parametrize(
        "sort_key", ["name", "state", "first_file_date", "last_file_date"]
    )
    async def test_all_sort_keys_execute_successfully(self, async_db, sort_key):
        """
        Ensures every defined sort key maps to a valid column and
        executes a query without KeyError or SQL errors.
        """
        service = CandidateService(db=async_db)

        result_desc = await service.get_list(
            state=None, office=None, cycle=None, sort_by=sort_key, order="desc"
        )
        result_asc = await service.get_list(
            state=None, office=None, cycle=None, sort_by=sort_key, order="asc"
        )

        assert "items" in result_desc
        assert "items" in result_asc
