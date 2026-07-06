"""Integration tests for ScheduleETotalsByCandidateService."""

from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from civic_lantern.db.models.candidate import Candidate
from civic_lantern.db.models.schedule_e_totals_by_candidate import (
    ScheduleETotalsByCandidate,
)
from civic_lantern.services.data.schedule_e_totals_by_candidate import (
    ScheduleETotalsByCandidateService,
)


async def _seed(session: AsyncSession, candidates: list, rows: list) -> None:
    for c in candidates:
        session.add(c)
    await session.flush()
    for row in rows:
        session.add(row)
    await session.commit()
    session.expunge_all()


@pytest_asyncio.fixture
async def seeded(async_db: AsyncSession):
    await _seed(
        async_db,
        candidates=[
            Candidate(candidate_id="P001", name="Alice", state="CA", party="DEM"),
        ],
        rows=[
            ScheduleETotalsByCandidate(
                candidate_id="P001",
                cycle=2024,
                support_oppose_indicator="S",
                total=Decimal("2000000.00"),
            ),
            ScheduleETotalsByCandidate(
                candidate_id="P001",
                cycle=2024,
                support_oppose_indicator="O",
                total=Decimal("500000.00"),
            ),
        ],
    )


@pytest.mark.integration
@pytest.mark.asyncio
class TestScheduleETotalsByCandidateUpsert:
    async def test_insert_new_record(self, async_db, seeded):
        result = await async_db.get(
            ScheduleETotalsByCandidate,
            {"candidate_id": "P001", "cycle": 2024, "support_oppose_indicator": "S"},
        )
        assert result is not None
        assert result.total == Decimal("2000000.00")

    async def test_support_and_oppose_are_separate_rows(self, async_db, seeded):
        support = await async_db.get(
            ScheduleETotalsByCandidate,
            {"candidate_id": "P001", "cycle": 2024, "support_oppose_indicator": "S"},
        )
        oppose = await async_db.get(
            ScheduleETotalsByCandidate,
            {"candidate_id": "P001", "cycle": 2024, "support_oppose_indicator": "O"},
        )
        assert support.total == Decimal("2000000.00")
        assert oppose.total == Decimal("500000.00")

    async def test_upsert_updates_existing_record(self, async_db, seeded):
        service = ScheduleETotalsByCandidateService(db=async_db)
        stats = await service.upsert_batch(
            [
                {
                    "candidate_id": "P001",
                    "cycle": 2024,
                    "support_oppose_indicator": "S",
                    "total": Decimal("3000000.00"),
                }
            ]
        )
        assert stats["updated"] == 1

        updated = await async_db.get(
            ScheduleETotalsByCandidate,
            {"candidate_id": "P001", "cycle": 2024, "support_oppose_indicator": "S"},
        )
        assert updated.total == Decimal("3000000.00")

    async def test_null_total_stored(self, async_db):
        await _seed(
            async_db,
            candidates=[Candidate(candidate_id="P001", name="Alice")],
            rows=[
                ScheduleETotalsByCandidate(
                    candidate_id="P001",
                    cycle=2024,
                    support_oppose_indicator="S",
                    total=None,
                )
            ],
        )
        result = await async_db.get(
            ScheduleETotalsByCandidate,
            {"candidate_id": "P001", "cycle": 2024, "support_oppose_indicator": "S"},
        )
        assert result.total is None
