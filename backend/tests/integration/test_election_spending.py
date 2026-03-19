"""Integration tests for ElectionSpendingService using a real materialized view."""

from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from civic_lantern.core.config import get_settings
from civic_lantern.db.models import Base
from civic_lantern.db.models.candidate import Candidate
from civic_lantern.db.models.candidate_spending import CandidateSpendingTotals
from civic_lantern.services.data.election_spending import ElectionSpendingService

MV_SQL = """
    CREATE MATERIALIZED VIEW mv_election_spending_summary AS
    SELECT
        cycle,
        COUNT(DISTINCT candidate_id) as candidate_count,
        SUM(inside_receipts) as total_inside_receipts,
        SUM(inside_disbursements) as total_inside_disbursements,
        SUM(outside_support) as total_outside_support,
        SUM(outside_oppose) as total_outside_oppose,
        ROUND(
            SUM(outside_support + outside_oppose) /
            NULLIF(SUM(inside_disbursements), 0),
            2
        ) as global_influence_ratio
    FROM candidate_spending_totals
    GROUP BY cycle;
"""

MV_INDEX_SQL = """
    CREATE UNIQUE INDEX idx_spending_summary_cycle
    ON mv_election_spending_summary (cycle);
"""


@pytest_asyncio.fixture
async def db_with_mv():
    """Full lifecycle fixture for MV integration tests.

    Uses NullPool so connections are never shared across event loops (one per
    pytest-asyncio function scope). Drops the MV and all tables in a single
    connection so there is no ordering race between teardown steps.
    """
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
            text("DROP MATERIALIZED VIEW IF EXISTS mv_election_spending_summary")
        )
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


async def _seed_and_refresh(session, candidates, spending_rows) -> None:
    """Insert candidates and spending rows, then refresh the MV."""
    for c in candidates:
        session.add(c)
    await session.flush()

    for row in spending_rows:
        session.add(row)
    await session.flush()

    await session.execute(
        text("REFRESH MATERIALIZED VIEW mv_election_spending_summary")
    )
    await session.commit()


@pytest.mark.integration
@pytest.mark.asyncio
class TestElectionSpendingServiceIntegration:
    async def test_get_all_spending_returns_seeded_rows(self, db_with_mv):
        """MV has data after seed + refresh; service returns it."""
        await _seed_and_refresh(
            db_with_mv,
            candidates=[Candidate(candidate_id="C001", name="Alice")],
            spending_rows=[
                CandidateSpendingTotals(
                    candidate_id="C001",
                    cycle=2024,
                    inside_receipts=Decimal("100000.00"),
                    inside_disbursements=Decimal("80000.00"),
                    outside_support=Decimal("20000.00"),
                    outside_oppose=Decimal("5000.00"),
                )
            ],
        )

        service = ElectionSpendingService(db=db_with_mv)
        results = await service.get_all_spending()

        assert len(results) == 1
        assert results[0].cycle == 2024

    async def test_get_all_spending_ordered_by_cycle_desc(self, db_with_mv):
        """Multiple cycles are returned newest-first."""
        await _seed_and_refresh(
            db_with_mv,
            candidates=[
                Candidate(candidate_id="C002", name="Bob"),
                Candidate(candidate_id="C003", name="Carol"),
            ],
            spending_rows=[
                CandidateSpendingTotals(
                    candidate_id="C002",
                    cycle=2020,
                    inside_disbursements=Decimal("50000.00"),
                    outside_support=Decimal("10000.00"),
                    outside_oppose=Decimal("0.00"),
                ),
                CandidateSpendingTotals(
                    candidate_id="C003",
                    cycle=2022,
                    inside_disbursements=Decimal("60000.00"),
                    outside_support=Decimal("15000.00"),
                    outside_oppose=Decimal("0.00"),
                ),
            ],
        )

        service = ElectionSpendingService(db=db_with_mv)
        results = await service.get_all_spending()

        assert len(results) == 2
        assert results[0].cycle == 2022
        assert results[1].cycle == 2020

    async def test_get_all_spending_empty_mv_returns_empty_list(self, db_with_mv):
        """No seed data → empty result (not an error)."""
        await db_with_mv.execute(
            text("REFRESH MATERIALIZED VIEW mv_election_spending_summary")
        )
        await db_with_mv.commit()

        service = ElectionSpendingService(db=db_with_mv)
        results = await service.get_all_spending()

        assert results == []

    async def test_get_spending_by_cycle_returns_correct_cycle(self, db_with_mv):
        """Filter returns the right row."""
        await _seed_and_refresh(
            db_with_mv,
            candidates=[
                Candidate(candidate_id="C004", name="Dave"),
                Candidate(candidate_id="C005", name="Eve"),
            ],
            spending_rows=[
                CandidateSpendingTotals(
                    candidate_id="C004",
                    cycle=2020,
                    inside_disbursements=Decimal("40000.00"),
                    outside_support=Decimal("8000.00"),
                    outside_oppose=Decimal("0.00"),
                ),
                CandidateSpendingTotals(
                    candidate_id="C005",
                    cycle=2024,
                    inside_disbursements=Decimal("70000.00"),
                    outside_support=Decimal("25000.00"),
                    outside_oppose=Decimal("0.00"),
                ),
            ],
        )

        service = ElectionSpendingService(db=db_with_mv)
        result = await service.get_spending_by_cycle(2024)

        assert result is not None
        assert result.cycle == 2024

    async def test_get_spending_by_cycle_unknown_cycle_returns_none(self, db_with_mv):
        """Non-existent cycle → None."""
        await db_with_mv.execute(
            text("REFRESH MATERIALIZED VIEW mv_election_spending_summary")
        )
        await db_with_mv.commit()

        service = ElectionSpendingService(db=db_with_mv)
        result = await service.get_spending_by_cycle(9999)

        assert result is None

    async def test_aggregates_are_correct(self, db_with_mv):
        """Seed known values; verify SUM/ROUND in MV matches expected aggregates."""
        await _seed_and_refresh(
            db_with_mv,
            candidates=[
                Candidate(candidate_id="C006", name="Frank"),
                Candidate(candidate_id="C007", name="Grace"),
            ],
            spending_rows=[
                CandidateSpendingTotals(
                    candidate_id="C006",
                    cycle=2024,
                    inside_receipts=Decimal("100000.00"),
                    inside_disbursements=Decimal("80000.00"),
                    outside_support=Decimal("20000.00"),
                    outside_oppose=Decimal("4000.00"),
                ),
                CandidateSpendingTotals(
                    candidate_id="C007",
                    cycle=2024,
                    inside_receipts=Decimal("50000.00"),
                    inside_disbursements=Decimal("40000.00"),
                    outside_support=Decimal("10000.00"),
                    outside_oppose=Decimal("6000.00"),
                ),
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
        """
        Verify that the MV uses NULLIF to prevent division by zero.
        The global_influence_ratio should be None (NULL) if disbursements are 0.
        """
        await _seed_and_refresh(
            db_with_mv,
            candidates=[Candidate(candidate_id="C008", name="Zero Spend")],
            spending_rows=[
                CandidateSpendingTotals(
                    candidate_id="C008",
                    cycle=2024,
                    inside_receipts=Decimal("1000.00"),
                    inside_disbursements=Decimal("0.00"),
                    outside_support=Decimal("500.00"),
                    outside_oppose=Decimal("100.00"),
                )
            ],
        )

        service = ElectionSpendingService(db=db_with_mv)
        result = await service.get_spending_by_cycle(2024)

        assert result is not None
        assert result.total_inside_disbursements == Decimal("0.00")
        # SQL ROUND(SUM(...) / NULLIF(0, 0)) results in NULL -> Python None
        assert result.global_influence_ratio is None
