"""Integration tests for BaseService's generic upsert keyed on the full primary key."""

from decimal import Decimal

import pytest
from sqlalchemy import select

from civic_lantern.db.models.candidate import Candidate
from civic_lantern.db.models.enums import SupportOpposeEnum
from civic_lantern.db.models.inside_totals_by_candidate import InsideTotalsByCandidate
from civic_lantern.db.models.schedule_e_totals_by_candidate import (
    ScheduleETotalsByCandidate,
)
from civic_lantern.schemas.candidate import CandidateIn
from civic_lantern.schemas.inside_totals_by_candidate import InsideTotalsByCandidateIn
from civic_lantern.schemas.schedule_e_totals_by_candidate import (
    ScheduleETotalsByCandidateIn,
)
from civic_lantern.services.data.base import BaseService


@pytest.mark.integration
@pytest.mark.asyncio
class TestCompositeKeyUpsert:
    async def test_conflict_key_is_the_full_primary_key(self, async_db):
        async_db.add(Candidate(candidate_id="P001", name="Alice"))
        await async_db.commit()
        service = BaseService(InsideTotalsByCandidate, db=async_db)

        rows = [
            InsideTotalsByCandidateIn(
                candidate_id="P001", cycle=2022, receipts=1, disbursements=1
            ),
            InsideTotalsByCandidateIn(
                candidate_id="P001", cycle=2024, receipts=2, disbursements=2
            ),
        ]
        first = await service.upsert_batch(rows)
        rows[1] = rows[1].model_copy(update={"receipts": 5})
        second = await service.upsert_batch(rows)

        assert (first["inserted"], second["updated"]) == (2, 1)
        stored = await async_db.get(
            InsideTotalsByCandidate, {"candidate_id": "P001", "cycle": 2024}
        )
        assert stored.receipts == Decimal("5.00")

    async def test_failed_rows_report_their_full_key(self, async_db):
        service = BaseService(ScheduleETotalsByCandidate, db=async_db)

        stats = await service.upsert_batch(
            [
                ScheduleETotalsByCandidateIn(
                    candidate_id="P_MISSING",
                    cycle=2024,
                    support_oppose_indicator=SupportOpposeEnum.SUPPORT,
                    total=1,
                )
            ]
        )

        assert stats["errors"] == 1
        assert stats["failed_ids"] == [("P_MISSING", 2024, "S")]


@pytest.mark.integration
@pytest.mark.asyncio
class TestTransactionBoundary:
    async def _stored_ids(self, session) -> set:
        session.expunge_all()
        return set((await session.execute(select(Candidate.candidate_id))).scalars())

    async def test_a_failing_batch_keeps_the_earlier_batches(self, async_db):
        service = BaseService(Candidate, db=async_db)
        rows = [
            CandidateIn(candidate_id="C1", name="One"),
            CandidateIn(candidate_id="C2", name="Two"),
            # Skips validation, so the database rejects the missing name.
            CandidateIn.model_construct(candidate_id="C_BAD"),
            CandidateIn(candidate_id="C3", name="Three"),
        ]

        stats = await service.upsert_batch(rows, batch_size=2)

        assert (stats["inserted"], stats["errors"]) == (3, 1)
        assert stats["failed_ids"] == ["C_BAD"]
        assert await self._stored_ids(async_db) == {"C1", "C2", "C3"}

    async def test_leaves_the_commit_to_the_caller(self, async_db):
        service = BaseService(Candidate, db=async_db)
        rows = [CandidateIn(candidate_id=f"C{i}", name="Name") for i in range(5)]

        await service.upsert_batch(rows, batch_size=2)
        await async_db.rollback()

        assert await self._stored_ids(async_db) == set()
