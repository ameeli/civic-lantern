"""Integration tests for CandidateSpendingService using mv_candidate_spending_summary."""

from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from civic_lantern.core.config import get_settings
from civic_lantern.db.models import Base
from civic_lantern.db.models.candidate import Candidate
from civic_lantern.db.models.inside_totals_by_candidate import InsideTotalsByCandidate
from civic_lantern.db.models.schedule_e_totals_by_candidate import (
    ScheduleETotalsByCandidate,
)
from civic_lantern.services.data.candidate_spending import CandidateSpendingService

MV_SQL = """
    CREATE MATERIALIZED VIEW mv_candidate_spending_summary AS
    WITH inside AS (
        SELECT candidate_id, cycle,
            SUM(receipts)      AS inside_receipts,
            SUM(disbursements) AS inside_disbursements
        FROM inside_totals_by_candidate
        GROUP BY candidate_id, cycle
    ),
    outside AS (
        SELECT candidate_id, cycle,
            SUM(CASE WHEN support_oppose_indicator = 'S' THEN total ELSE 0 END) AS outside_support,
            SUM(CASE WHEN support_oppose_indicator = 'O' THEN total ELSE 0 END) AS outside_oppose
        FROM schedule_e_totals_by_candidate
        GROUP BY candidate_id, cycle
    ),
    all_pairs AS (
        SELECT candidate_id, cycle FROM inside
        UNION
        SELECT candidate_id, cycle FROM outside
    )
    SELECT
        ap.candidate_id,
        ap.cycle,
        COALESCE(i.inside_receipts, 0)      AS inside_receipts,
        COALESCE(i.inside_disbursements, 0) AS inside_disbursements,
        COALESCE(o.outside_support, 0)      AS outside_support,
        COALESCE(o.outside_oppose, 0)       AS outside_oppose,
        ROUND(
            (COALESCE(o.outside_support, 0) + COALESCE(o.outside_oppose, 0)) /
            NULLIF(COALESCE(i.inside_disbursements, 0), 0), 2
        ) AS influence_ratio,
        ROUND(
            COALESCE(o.outside_oppose, 0) /
            NULLIF(COALESCE(i.inside_disbursements, 0), 0), 2
        ) AS vulnerability_factor
    FROM all_pairs ap
    LEFT JOIN inside i  ON ap.candidate_id = i.candidate_id AND ap.cycle = i.cycle
    LEFT JOIN outside o ON ap.candidate_id = o.candidate_id AND ap.cycle = o.cycle;
"""

MV_INDEX_SQL = """
    CREATE UNIQUE INDEX idx_mv_cand_spend_pk
    ON mv_candidate_spending_summary (candidate_id, cycle);
"""


@pytest_asyncio.fixture
async def db_with_mv():
    settings = get_settings()
    engine = create_async_engine(
        settings.TEST_DATABASE_URL_ASYNC, echo=False, poolclass=NullPool
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text(MV_SQL))
        await conn.execute(text(MV_INDEX_SQL))

    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.execute(
            text("DROP MATERIALIZED VIEW IF EXISTS mv_candidate_spending_summary")
        )
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


async def _seed_and_refresh(
    session,
    candidates: list,
    inside_rows: list = None,
    outside_rows: list = None,
) -> None:
    for c in candidates:
        session.add(c)
    await session.flush()

    for row in inside_rows or []:
        session.add(row)
    for row in outside_rows or []:
        session.add(row)
    await session.flush()

    await session.execute(
        text("REFRESH MATERIALIZED VIEW mv_candidate_spending_summary")
    )
    await session.commit()
    session.expunge_all()


@pytest_asyncio.fixture
async def standard_seed_data(db_with_mv):
    await _seed_and_refresh(
        db_with_mv,
        candidates=[
            Candidate(candidate_id="C001", name="Alice", state="CA", party="DEM"),
            Candidate(candidate_id="C002", name="Bob", state="TX", party="REP"),
        ],
        inside_rows=[
            InsideTotalsByCandidate(
                candidate_id="C001",
                cycle=2024,
                receipts=Decimal("10000.00"),
                disbursements=Decimal("10000.00"),
            ),
            InsideTotalsByCandidate(
                candidate_id="C002",
                cycle=2024,
                receipts=Decimal("20000.00"),
                disbursements=Decimal("20000.00"),
            ),
        ],
        outside_rows=[
            ScheduleETotalsByCandidate(
                candidate_id="C001",
                cycle=2024,
                support_oppose_indicator="S",
                total=Decimal("5000.00"),
            ),
            ScheduleETotalsByCandidate(
                candidate_id="C002",
                cycle=2024,
                support_oppose_indicator="S",
                total=Decimal("1000.00"),
            ),
        ],
    )


@pytest.mark.integration
@pytest.mark.asyncio
class TestGetList:
    async def test_returns_seeded_rows(self, db_with_mv, standard_seed_data):
        service = CandidateSpendingService(db=db_with_mv)
        result = await service.get_list()

        assert result["total_count"] == 2
        assert len(result["items"]) == 2

    async def test_empty_returns_empty(self, db_with_mv):
        await db_with_mv.execute(
            text("REFRESH MATERIALIZED VIEW mv_candidate_spending_summary")
        )
        await db_with_mv.commit()

        service = CandidateSpendingService(db=db_with_mv)
        result = await service.get_list()

        assert result["total_count"] == 0
        assert len(result["items"]) == 0

    async def test_pagination_limit_and_offset(self, db_with_mv):
        candidates = [
            Candidate(candidate_id=f"C{i:03d}", name=f"Candidate {i}") for i in range(5)
        ]
        inside_rows = [
            InsideTotalsByCandidate(
                candidate_id=f"C{i:03d}",
                cycle=2024,
                disbursements=Decimal("10000.00"),
            )
            for i in range(5)
        ]
        await _seed_and_refresh(db_with_mv, candidates, inside_rows=inside_rows)

        service = CandidateSpendingService(db=db_with_mv)
        result = await service.get_list(limit=2, offset=0)

        assert result["total_count"] == 5
        assert len(result["items"]) == 2
        assert result["limit"] == 2
        assert result["offset"] == 0

    async def test_total_count_independent_of_limit(self, db_with_mv):
        candidates = [
            Candidate(candidate_id=f"C{i:03d}", name=f"Candidate {i}") for i in range(5)
        ]
        inside_rows = [
            InsideTotalsByCandidate(
                candidate_id=f"C{i:03d}",
                cycle=2024,
                disbursements=Decimal("10000.00"),
            )
            for i in range(5)
        ]
        await _seed_and_refresh(db_with_mv, candidates, inside_rows=inside_rows)

        service = CandidateSpendingService(db=db_with_mv)
        result = await service.get_list(limit=2, offset=2)

        assert result["total_count"] == 5
        assert len(result["items"]) == 2

    async def test_sort_by_cycle_desc(self, db_with_mv):
        await _seed_and_refresh(
            db_with_mv,
            candidates=[Candidate(candidate_id="C001", name="Alice")],
            inside_rows=[
                InsideTotalsByCandidate(
                    candidate_id="C001", cycle=2020, disbursements=Decimal("10000.00")
                ),
                InsideTotalsByCandidate(
                    candidate_id="C001", cycle=2022, disbursements=Decimal("10000.00")
                ),
                InsideTotalsByCandidate(
                    candidate_id="C001", cycle=2024, disbursements=Decimal("10000.00")
                ),
            ],
        )

        service = CandidateSpendingService(db=db_with_mv)
        result = await service.get_list(sort_by="cycle", order="desc")

        assert [r.cycle for r in result["items"]] == [2024, 2022, 2020]

    async def test_sort_by_cycle_asc(self, db_with_mv):
        await _seed_and_refresh(
            db_with_mv,
            candidates=[Candidate(candidate_id="C001", name="Alice")],
            inside_rows=[
                InsideTotalsByCandidate(
                    candidate_id="C001", cycle=2020, disbursements=Decimal("10000.00")
                ),
                InsideTotalsByCandidate(
                    candidate_id="C001", cycle=2022, disbursements=Decimal("10000.00")
                ),
                InsideTotalsByCandidate(
                    candidate_id="C001", cycle=2024, disbursements=Decimal("10000.00")
                ),
            ],
        )

        service = CandidateSpendingService(db=db_with_mv)
        result = await service.get_list(sort_by="cycle", order="asc")

        assert [r.cycle for r in result["items"]] == [2020, 2022, 2024]

    async def test_sort_by_outside_total_desc(self, db_with_mv):
        """outside_total is a computed sort column (support + oppose)."""
        await _seed_and_refresh(
            db_with_mv,
            candidates=[
                Candidate(candidate_id="C001", name="Alice"),
                Candidate(candidate_id="C002", name="Bob"),
                Candidate(candidate_id="C003", name="Carol"),
            ],
            inside_rows=[
                InsideTotalsByCandidate(
                    candidate_id="C001", cycle=2024, disbursements=Decimal("10000.00")
                ),
                InsideTotalsByCandidate(
                    candidate_id="C002", cycle=2024, disbursements=Decimal("10000.00")
                ),
                InsideTotalsByCandidate(
                    candidate_id="C003", cycle=2024, disbursements=Decimal("10000.00")
                ),
            ],
            outside_rows=[
                # C001 total = 6000
                ScheduleETotalsByCandidate(
                    candidate_id="C001",
                    cycle=2024,
                    support_oppose_indicator="S",
                    total=Decimal("5000.00"),
                ),
                ScheduleETotalsByCandidate(
                    candidate_id="C001",
                    cycle=2024,
                    support_oppose_indicator="O",
                    total=Decimal("1000.00"),
                ),
                # C002 total = 2500
                ScheduleETotalsByCandidate(
                    candidate_id="C002",
                    cycle=2024,
                    support_oppose_indicator="S",
                    total=Decimal("2000.00"),
                ),
                ScheduleETotalsByCandidate(
                    candidate_id="C002",
                    cycle=2024,
                    support_oppose_indicator="O",
                    total=Decimal("500.00"),
                ),
                # C003 total = 11000
                ScheduleETotalsByCandidate(
                    candidate_id="C003",
                    cycle=2024,
                    support_oppose_indicator="S",
                    total=Decimal("8000.00"),
                ),
                ScheduleETotalsByCandidate(
                    candidate_id="C003",
                    cycle=2024,
                    support_oppose_indicator="O",
                    total=Decimal("3000.00"),
                ),
            ],
        )

        service = CandidateSpendingService(db=db_with_mv)
        result = await service.get_list(sort_by="outside_total", order="desc")

        assert [r.candidate_id for r in result["items"]] == ["C003", "C001", "C002"]

    async def test_includes_candidate_info(self, db_with_mv, standard_seed_data):
        """_attach_candidates populates the .candidate attribute."""
        service = CandidateSpendingService(db=db_with_mv)
        result = await service.get_list(sort_by="outside_total", order="desc")

        c001 = next(r for r in result["items"] if r.candidate_id == "C001")
        assert c001.candidate is not None
        assert c001.candidate.name == "Alice"
        assert c001.candidate.state == "CA"

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
        self, db_with_mv, standard_seed_data, sort_key
    ):
        service = CandidateSpendingService(db=db_with_mv)
        result_desc = await service.get_list(sort_by=sort_key, order="desc")
        result_asc = await service.get_list(sort_by=sort_key, order="asc")

        assert result_desc["total_count"] == 2
        assert result_asc["total_count"] == 2


@pytest.mark.integration
@pytest.mark.asyncio
class TestGetSpendingByCandidateId:
    async def test_returns_correct_records(self, db_with_mv, standard_seed_data):
        service = CandidateSpendingService(db=db_with_mv)
        results = await service.get_spending_by_candidate_id("C001")

        assert len(results) == 1
        assert results[0].candidate_id == "C001"

    async def test_ordered_by_cycle_desc(self, db_with_mv):
        await _seed_and_refresh(
            db_with_mv,
            candidates=[Candidate(candidate_id="C001", name="Alice")],
            inside_rows=[
                InsideTotalsByCandidate(
                    candidate_id="C001", cycle=2020, disbursements=Decimal("10000.00")
                ),
                InsideTotalsByCandidate(
                    candidate_id="C001", cycle=2022, disbursements=Decimal("20000.00")
                ),
                InsideTotalsByCandidate(
                    candidate_id="C001", cycle=2024, disbursements=Decimal("30000.00")
                ),
            ],
        )

        service = CandidateSpendingService(db=db_with_mv)
        results = await service.get_spending_by_candidate_id("C001")

        assert [r.cycle for r in results] == [2024, 2022, 2020]

    async def test_unknown_candidate_returns_empty(self, db_with_mv):
        await db_with_mv.execute(
            text("REFRESH MATERIALIZED VIEW mv_candidate_spending_summary")
        )
        await db_with_mv.commit()

        service = CandidateSpendingService(db=db_with_mv)
        results = await service.get_spending_by_candidate_id("NONEXISTENT")

        assert len(results) == 0

    async def test_includes_candidate_info(self, db_with_mv, standard_seed_data):
        """_attach_candidates populates .candidate on spending-by-candidate results."""
        service = CandidateSpendingService(db=db_with_mv)
        results = await service.get_spending_by_candidate_id("C001")

        assert results[0].candidate is not None
        assert results[0].candidate.name == "Alice"
        assert results[0].candidate.party == "DEM"
