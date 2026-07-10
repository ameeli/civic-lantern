"""Integration tests for ElectionSpendingService using mv_election_spending_summary."""

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
from civic_lantern.services.data.election_spending import ElectionSpendingService

MV_CANDIDATE_SQL = """
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

MV_ELECTION_SQL = """
    CREATE MATERIALIZED VIEW mv_election_spending_summary AS
    SELECT
        cycle,
        COUNT(DISTINCT candidate_id) AS candidate_count,
        SUM(inside_receipts)         AS total_inside_receipts,
        SUM(inside_disbursements)    AS total_inside_disbursements,
        SUM(outside_support)         AS total_outside_support,
        SUM(outside_oppose)          AS total_outside_oppose,
        ROUND(
            SUM(outside_support + outside_oppose) /
            NULLIF(SUM(inside_disbursements), 0), 2
        ) AS global_influence_ratio
    FROM mv_candidate_spending_summary
    GROUP BY cycle;
"""

MV_ELECTION_INDEX_SQL = """
    CREATE UNIQUE INDEX idx_spending_summary_cycle
    ON mv_election_spending_summary (cycle);
"""


@pytest_asyncio.fixture
async def db_with_mv():
    settings = get_settings()
    engine = create_async_engine(
        settings.TEST_DATABASE_URL_ASYNC, echo=False, poolclass=NullPool
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text(MV_CANDIDATE_SQL))
        await conn.execute(text(MV_ELECTION_SQL))
        await conn.execute(text(MV_ELECTION_INDEX_SQL))

    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.execute(text("DROP MATERIALIZED VIEW IF EXISTS mv_election_spending_summary"))
        await conn.execute(text("DROP MATERIALIZED VIEW IF EXISTS mv_candidate_spending_summary"))
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

    await session.execute(text("REFRESH MATERIALIZED VIEW mv_candidate_spending_summary"))
    await session.execute(text("REFRESH MATERIALIZED VIEW mv_election_spending_summary"))
    await session.commit()


@pytest.mark.integration
@pytest.mark.asyncio
class TestElectionSpendingServiceIntegration:
    async def test_get_all_spending_returns_seeded_rows(self, db_with_mv):
        await _seed_and_refresh(
            db_with_mv,
            candidates=[Candidate(candidate_id="C001", name="Alice")],
            inside_rows=[
                InsideTotalsByCandidate(
                    candidate_id="C001", cycle=2024,
                    receipts=Decimal("100000.00"), disbursements=Decimal("80000.00"),
                )
            ],
        )

        service = ElectionSpendingService(db=db_with_mv)
        results = await service.get_all_spending()

        assert len(results) == 1
        assert results[0].cycle == 2024

    async def test_get_all_spending_ordered_by_cycle_desc(self, db_with_mv):
        await _seed_and_refresh(
            db_with_mv,
            candidates=[
                Candidate(candidate_id="C002", name="Bob"),
                Candidate(candidate_id="C003", name="Carol"),
            ],
            inside_rows=[
                InsideTotalsByCandidate(candidate_id="C002", cycle=2020, disbursements=Decimal("50000.00")),
                InsideTotalsByCandidate(candidate_id="C003", cycle=2022, disbursements=Decimal("60000.00")),
            ],
        )

        service = ElectionSpendingService(db=db_with_mv)
        results = await service.get_all_spending()

        assert len(results) == 2
        assert results[0].cycle == 2022
        assert results[1].cycle == 2020

    async def test_get_all_spending_empty_mv_returns_empty_list(self, db_with_mv):
        await db_with_mv.execute(text("REFRESH MATERIALIZED VIEW mv_candidate_spending_summary"))
        await db_with_mv.execute(text("REFRESH MATERIALIZED VIEW mv_election_spending_summary"))
        await db_with_mv.commit()

        service = ElectionSpendingService(db=db_with_mv)
        results = await service.get_all_spending()

        assert results == []

    async def test_get_spending_by_cycle_returns_correct_cycle(self, db_with_mv):
        await _seed_and_refresh(
            db_with_mv,
            candidates=[
                Candidate(candidate_id="C004", name="Dave"),
                Candidate(candidate_id="C005", name="Eve"),
            ],
            inside_rows=[
                InsideTotalsByCandidate(candidate_id="C004", cycle=2020, disbursements=Decimal("40000.00")),
                InsideTotalsByCandidate(candidate_id="C005", cycle=2024, disbursements=Decimal("70000.00")),
            ],
        )

        service = ElectionSpendingService(db=db_with_mv)
        result = await service.get_spending_by_cycle(2024)

        assert result is not None
        assert result.cycle == 2024

    async def test_get_spending_by_cycle_unknown_cycle_returns_none(self, db_with_mv):
        await db_with_mv.execute(text("REFRESH MATERIALIZED VIEW mv_candidate_spending_summary"))
        await db_with_mv.execute(text("REFRESH MATERIALIZED VIEW mv_election_spending_summary"))
        await db_with_mv.commit()

        service = ElectionSpendingService(db=db_with_mv)
        result = await service.get_spending_by_cycle(9999)

        assert result is None

    async def test_aggregates_are_correct(self, db_with_mv):
        """Seed known values and verify SUM/ROUND aggregates in the MV chain."""
        await _seed_and_refresh(
            db_with_mv,
            candidates=[
                Candidate(candidate_id="C006", name="Frank"),
                Candidate(candidate_id="C007", name="Grace"),
            ],
            inside_rows=[
                InsideTotalsByCandidate(
                    candidate_id="C006", cycle=2024,
                    receipts=Decimal("100000.00"), disbursements=Decimal("80000.00"),
                ),
                InsideTotalsByCandidate(
                    candidate_id="C007", cycle=2024,
                    receipts=Decimal("50000.00"), disbursements=Decimal("40000.00"),
                ),
            ],
            outside_rows=[
                ScheduleETotalsByCandidate(candidate_id="C006", cycle=2024, support_oppose_indicator="S", total=Decimal("20000.00")),
                ScheduleETotalsByCandidate(candidate_id="C006", cycle=2024, support_oppose_indicator="O", total=Decimal("4000.00")),
                ScheduleETotalsByCandidate(candidate_id="C007", cycle=2024, support_oppose_indicator="S", total=Decimal("10000.00")),
                ScheduleETotalsByCandidate(candidate_id="C007", cycle=2024, support_oppose_indicator="O", total=Decimal("6000.00")),
            ],
        )

        service = ElectionSpendingService(db=db_with_mv)
        result = await service.get_spending_by_cycle(2024)

        assert result is not None
        assert result.candidate_count == 2
        assert result.total_inside_receipts == Decimal("150000.00")
        assert result.total_inside_disbursements == Decimal("120000.00")
        assert result.total_outside_support == Decimal("30000.00")
        assert result.total_outside_oppose == Decimal("10000.00")
        # (30000 + 10000) / 120000 = 0.33
        assert result.global_influence_ratio == Decimal("0.33")

    async def test_global_influence_ratio_handles_zero_disbursements(self, db_with_mv):
        """NULLIF prevents division by zero — ratio should be None when disbursements = 0."""
        await _seed_and_refresh(
            db_with_mv,
            candidates=[Candidate(candidate_id="C008", name="Zero Spend")],
            inside_rows=[
                InsideTotalsByCandidate(
                    candidate_id="C008", cycle=2024,
                    receipts=Decimal("1000.00"), disbursements=Decimal("0.00"),
                )
            ],
            outside_rows=[
                ScheduleETotalsByCandidate(candidate_id="C008", cycle=2024, support_oppose_indicator="S", total=Decimal("500.00")),
                ScheduleETotalsByCandidate(candidate_id="C008", cycle=2024, support_oppose_indicator="O", total=Decimal("100.00")),
            ],
        )

        service = ElectionSpendingService(db=db_with_mv)
        result = await service.get_spending_by_cycle(2024)

        assert result is not None
        assert result.total_inside_disbursements == Decimal("0.00")
        assert result.global_influence_ratio is None
