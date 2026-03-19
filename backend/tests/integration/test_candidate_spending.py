"""Integration tests for CandidateSpendingService."""

from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from civic_lantern.db.models.candidate import Candidate
from civic_lantern.db.models.candidate_spending import CandidateSpendingTotals
from civic_lantern.services.data.candidate_spending import CandidateSpendingService


async def _seed(
    session: AsyncSession,
    candidates: list,
    spending_rows: list,
) -> None:
    """Insert candidates and spending rows."""
    for c in candidates:
        session.add(c)
    await session.flush()

    for row in spending_rows:
        session.add(row)
    await session.commit()

    session.expunge_all()


@pytest_asyncio.fixture
async def standard_seed_data(async_db: AsyncSession):
    """Baseline seed: two candidates with one 2024 spending row each.

    Expunges all objects after commit so that joinedload tests cannot be
    satisfied from the session identity map — the service must actually
    execute the JOIN against the database.
    """
    candidates = [
        Candidate(candidate_id="C001", name="Alice", state="CA", party="DEM"),
        Candidate(candidate_id="C002", name="Bob", state="TX", party="REP"),
    ]
    spending_rows = [
        CandidateSpendingTotals(
            candidate_id="C001",
            cycle=2024,
            inside_disbursements=Decimal("10000.00"),
            outside_support=Decimal("5000.00"),
        ),
        CandidateSpendingTotals(
            candidate_id="C002",
            cycle=2024,
            inside_disbursements=Decimal("20000.00"),
            outside_support=Decimal("1000.00"),
        ),
    ]

    for c in candidates:
        async_db.add(c)
    await async_db.flush()

    for row in spending_rows:
        async_db.add(row)
    await async_db.commit()

    async_db.expunge_all()


@pytest.mark.integration
@pytest.mark.asyncio
class TestGetList:
    async def test_returns_seeded_rows(self, async_db, standard_seed_data):
        service = CandidateSpendingService(db=async_db)
        result = await service.get_list()

        assert result["total_count"] == 2
        assert len(result["items"]) == 2

    async def test_empty_returns_empty(self, async_db):
        service = CandidateSpendingService(db=async_db)
        result = await service.get_list()

        assert result["total_count"] == 0
        assert len(result["items"]) == 0

    async def test_pagination_limit_and_offset(self, async_db):
        await _seed(
            async_db,
            candidates=[
                Candidate(candidate_id=f"C{i:03d}", name=f"Candidate {i}")
                for i in range(5)
            ],
            spending_rows=[
                CandidateSpendingTotals(
                    candidate_id=f"C{i:03d}",
                    cycle=2024,
                    inside_disbursements=Decimal("10000.00"),
                    outside_support=Decimal("1000.00"),
                    outside_oppose=Decimal("500.00"),
                )
                for i in range(5)
            ],
        )

        service = CandidateSpendingService(db=async_db)
        result = await service.get_list(limit=2, offset=0)

        assert result["total_count"] == 5
        assert len(result["items"]) == 2
        assert result["limit"] == 2
        assert result["offset"] == 0

    async def test_total_count_independent_of_limit(self, async_db):
        """total_count reflects all rows even when limit reduces the page."""
        await _seed(
            async_db,
            candidates=[
                Candidate(candidate_id=f"C{i:03d}", name=f"Candidate {i}")
                for i in range(5)
            ],
            spending_rows=[
                CandidateSpendingTotals(
                    candidate_id=f"C{i:03d}",
                    cycle=2024,
                    inside_disbursements=Decimal("10000.00"),
                    outside_support=Decimal("1000.00"),
                    outside_oppose=Decimal("500.00"),
                )
                for i in range(5)
            ],
        )

        service = CandidateSpendingService(db=async_db)
        result = await service.get_list(limit=2, offset=2)

        assert result["total_count"] == 5
        assert len(result["items"]) == 2

    async def test_sort_by_cycle_desc(self, async_db):
        await _seed(
            async_db,
            candidates=[Candidate(candidate_id="C001", name="Alice")],
            spending_rows=[
                CandidateSpendingTotals(
                    candidate_id="C001",
                    cycle=2020,
                    inside_disbursements=Decimal("10000.00"),
                    outside_support=Decimal("1000.00"),
                    outside_oppose=Decimal("0.00"),
                ),
                CandidateSpendingTotals(
                    candidate_id="C001",
                    cycle=2022,
                    inside_disbursements=Decimal("10000.00"),
                    outside_support=Decimal("1000.00"),
                    outside_oppose=Decimal("0.00"),
                ),
                CandidateSpendingTotals(
                    candidate_id="C001",
                    cycle=2024,
                    inside_disbursements=Decimal("10000.00"),
                    outside_support=Decimal("1000.00"),
                    outside_oppose=Decimal("0.00"),
                ),
            ],
        )

        service = CandidateSpendingService(db=async_db)
        result = await service.get_list(sort_by="cycle", order="desc")

        assert [r.cycle for r in result["items"]] == [2024, 2022, 2020]

    async def test_sort_by_cycle_asc(self, async_db):
        await _seed(
            async_db,
            candidates=[Candidate(candidate_id="C001", name="Alice")],
            spending_rows=[
                CandidateSpendingTotals(
                    candidate_id="C001",
                    cycle=2020,
                    inside_disbursements=Decimal("10000.00"),
                    outside_support=Decimal("1000.00"),
                    outside_oppose=Decimal("0.00"),
                ),
                CandidateSpendingTotals(
                    candidate_id="C001",
                    cycle=2022,
                    inside_disbursements=Decimal("10000.00"),
                    outside_support=Decimal("1000.00"),
                    outside_oppose=Decimal("0.00"),
                ),
                CandidateSpendingTotals(
                    candidate_id="C001",
                    cycle=2024,
                    inside_disbursements=Decimal("10000.00"),
                    outside_support=Decimal("1000.00"),
                    outside_oppose=Decimal("0.00"),
                ),
            ],
        )

        service = CandidateSpendingService(db=async_db)
        result = await service.get_list(sort_by="cycle", order="asc")

        assert [r.cycle for r in result["items"]] == [2020, 2022, 2024]

    async def test_sort_by_outside_total_desc(self, async_db):
        """outside_total is a computed sort column (support + oppose)."""
        await _seed(
            async_db,
            candidates=[
                Candidate(candidate_id="C001", name="Alice"),
                Candidate(candidate_id="C002", name="Bob"),
                Candidate(candidate_id="C003", name="Carol"),
            ],
            spending_rows=[
                CandidateSpendingTotals(
                    candidate_id="C001",
                    cycle=2024,
                    inside_disbursements=Decimal("10000.00"),
                    outside_support=Decimal("5000.00"),
                    outside_oppose=Decimal("1000.00"),
                ),  # total=6000
                CandidateSpendingTotals(
                    candidate_id="C002",
                    cycle=2024,
                    inside_disbursements=Decimal("10000.00"),
                    outside_support=Decimal("2000.00"),
                    outside_oppose=Decimal("500.00"),
                ),  # total=2500
                CandidateSpendingTotals(
                    candidate_id="C003",
                    cycle=2024,
                    inside_disbursements=Decimal("10000.00"),
                    outside_support=Decimal("8000.00"),
                    outside_oppose=Decimal("3000.00"),
                ),  # total=11000
            ],
        )

        service = CandidateSpendingService(db=async_db)
        result = await service.get_list(sort_by="outside_total", order="desc")

        assert [r.candidate_id for r in result["items"]] == ["C003", "C001", "C002"]

    async def test_includes_candidate_info(self, async_db, standard_seed_data):
        """joinedload populates the candidate relationship."""
        service = CandidateSpendingService(db=async_db)
        result = await service.get_list(sort_by="outside_total", order="desc")

        c001 = next(r for r in result["items"] if r.candidate_id == "C001")
        assert c001.candidate is not None
        assert c001.candidate.name == "Alice"
        assert c001.candidate.state == "CA"


@pytest.mark.integration
@pytest.mark.asyncio
class TestGetSpendingByCandidateId:
    async def test_returns_correct_records(self, async_db, standard_seed_data):
        """Only records for the requested candidate are returned."""
        service = CandidateSpendingService(db=async_db)
        results = await service.get_spending_by_candidate_id("C001")

        assert len(results) == 1
        assert results[0].candidate_id == "C001"

    async def test_ordered_by_cycle_desc(self, async_db):
        await _seed(
            async_db,
            candidates=[Candidate(candidate_id="C001", name="Alice")],
            spending_rows=[
                CandidateSpendingTotals(
                    candidate_id="C001",
                    cycle=2020,
                    inside_disbursements=Decimal("10000.00"),
                    outside_support=Decimal("0.00"),
                    outside_oppose=Decimal("0.00"),
                ),
                CandidateSpendingTotals(
                    candidate_id="C001",
                    cycle=2022,
                    inside_disbursements=Decimal("20000.00"),
                    outside_support=Decimal("0.00"),
                    outside_oppose=Decimal("0.00"),
                ),
                CandidateSpendingTotals(
                    candidate_id="C001",
                    cycle=2024,
                    inside_disbursements=Decimal("30000.00"),
                    outside_support=Decimal("0.00"),
                    outside_oppose=Decimal("0.00"),
                ),
            ],
        )

        service = CandidateSpendingService(db=async_db)
        results = await service.get_spending_by_candidate_id("C001")

        assert [r.cycle for r in results] == [2024, 2022, 2020]

    async def test_unknown_candidate_returns_empty(self, async_db):
        service = CandidateSpendingService(db=async_db)
        results = await service.get_spending_by_candidate_id("NONEXISTENT")

        assert len(results) == 0

    async def test_includes_candidate_info(self, async_db, standard_seed_data):
        """joinedload populates the candidate relationship."""
        service = CandidateSpendingService(db=async_db)
        results = await service.get_spending_by_candidate_id("C001")

        assert results[0].candidate is not None
        assert results[0].candidate.name == "Alice"
        assert results[0].candidate.party == "DEM"


@pytest.mark.integration
@pytest.mark.asyncio
class TestSortingKeys:
    @pytest.mark.parametrize(
        "sort_key",
        [
            "cycle",
            "inside_receipts",
            "inside_disbursements",
            "outside_support",
            "outside_oppose",
            "outside_total",
            "influence_ratio",
            "vulnerability_factor",
        ],
    )
    async def test_all_sort_keys_execute_successfully(
        self, async_db, standard_seed_data, sort_key
    ):
        """Ensures every defined sort key maps to a valid SQLAlchemy column/expression."""
        service = CandidateSpendingService(db=async_db)

        # If the key is missing from the dict, or invalid in SQL, this throws an error.
        result_desc = await service.get_list(sort_by=sort_key, order="desc")
        result_asc = await service.get_list(sort_by=sort_key, order="asc")

        assert result_desc["total_count"] == 2
        assert result_asc["total_count"] == 2
