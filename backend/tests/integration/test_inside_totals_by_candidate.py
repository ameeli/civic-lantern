"""Integration tests for InsideTotalsByCandidateService."""

from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from civic_lantern.db.models.candidate import Candidate
from civic_lantern.db.models.inside_totals_by_candidate import InsideTotalsByCandidate
from civic_lantern.services.data.inside_totals_by_candidate import (
    InsideTotalsByCandidateService,
)


async def _seed(
    session: AsyncSession,
    candidates: list,
    rows: list,
) -> None:
    for c in candidates:
        session.add(c)
    await session.flush()
    for row in rows:
        session.add(row)
    await session.commit()
    session.expunge_all()


@pytest_asyncio.fixture
async def two_candidates(async_db: AsyncSession):
    await _seed(
        async_db,
        candidates=[
            Candidate(candidate_id="C001", name="Alice", state="CA", party="DEM"),
            Candidate(candidate_id="C002", name="Bob", state="TX", party="REP"),
        ],
        rows=[
            InsideTotalsByCandidate(
                candidate_id="C001",
                cycle=2024,
                receipts=Decimal("500000.00"),
                disbursements=Decimal("480000.00"),
            ),
            InsideTotalsByCandidate(
                candidate_id="C002",
                cycle=2024,
                receipts=Decimal("300000.00"),
                disbursements=Decimal("290000.00"),
            ),
        ],
    )


@pytest.mark.integration
@pytest.mark.asyncio
class TestInsideTotalsByCandidateUpsert:
    async def test_insert_new_record(self, async_db, two_candidates):
        service = InsideTotalsByCandidateService(db=async_db)
        result = await service.get_by_id("C001")

        assert result is not None
        assert result.candidate_id == "C001"
        assert result.cycle == 2024
        assert result.receipts == Decimal("500000.00")
        assert result.disbursements == Decimal("480000.00")

    async def test_upsert_updates_existing_record(self, async_db, two_candidates):
        service = InsideTotalsByCandidateService(db=async_db)
        stats = await service.upsert_batch(
            [
                {
                    "candidate_id": "C001",
                    "cycle": 2024,
                    "receipts": Decimal("600000.00"),
                    "disbursements": Decimal("580000.00"),
                }
            ]
        )

        assert stats["updated"] == 1
        assert stats["inserted"] == 0

        updated = await service.get_by_id("C001")
        assert updated.receipts == Decimal("600000.00")

    async def test_upsert_inserts_new_cycle(self, async_db, two_candidates):
        service = InsideTotalsByCandidateService(db=async_db)
        stats = await service.upsert_batch(
            [
                {
                    "candidate_id": "C001",
                    "cycle": 2022,
                    "receipts": Decimal("200000.00"),
                    "disbursements": Decimal("190000.00"),
                }
            ]
        )

        assert stats["inserted"] == 1

    async def test_null_receipts_stored(self, async_db):
        await _seed(
            async_db,
            candidates=[Candidate(candidate_id="C003", name="Carol")],
            rows=[
                InsideTotalsByCandidate(
                    candidate_id="C003",
                    cycle=2024,
                    receipts=None,
                    disbursements=None,
                )
            ],
        )
        service = InsideTotalsByCandidateService(db=async_db)
        result = await service.get_by_id("C003")

        assert result.receipts is None
        assert result.disbursements is None

    async def test_multiple_cycles_per_candidate(self, async_db):
        await _seed(
            async_db,
            candidates=[Candidate(candidate_id="C001", name="Alice")],
            rows=[
                InsideTotalsByCandidate(
                    candidate_id="C001",
                    cycle=2020,
                    receipts=Decimal("100000.00"),
                    disbursements=Decimal("90000.00"),
                ),
                InsideTotalsByCandidate(
                    candidate_id="C001",
                    cycle=2022,
                    receipts=Decimal("200000.00"),
                    disbursements=Decimal("190000.00"),
                ),
                InsideTotalsByCandidate(
                    candidate_id="C001",
                    cycle=2024,
                    receipts=Decimal("300000.00"),
                    disbursements=Decimal("290000.00"),
                ),
            ],
        )
        service = InsideTotalsByCandidateService(db=async_db)

        # Each cycle stored independently — PK is (candidate_id, cycle)
        for cycle, expected_receipts in [
            (2020, Decimal("100000.00")),
            (2022, Decimal("200000.00")),
            (2024, Decimal("300000.00")),
        ]:
            result = await async_db.get(
                InsideTotalsByCandidate, {"candidate_id": "C001", "cycle": cycle}
            )
            assert result.receipts == expected_receipts
