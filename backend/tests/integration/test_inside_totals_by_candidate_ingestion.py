"""End-to-end tests for InsideTotalsByCandidateIngestor.run(): FEC HTTP mocked
with respx, real test Postgres, real client pagination/retry and transform."""

from decimal import Decimal

import httpx
import pytest
import pytest_asyncio
import respx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from civic_lantern.db.models.candidate import Candidate
from civic_lantern.db.models.ingestion_run import IngestionRun, IngestionRunStatus
from civic_lantern.db.models.inside_totals_by_candidate import InsideTotalsByCandidate
from civic_lantern.jobs.ingestors.inside_totals_by_candidate import (
    InsideTotalsByCandidateIngestor,
)
from civic_lantern.services.fec_exceptions import PartialFetchError

CYCLE = 2024
BIDEN = "P80000722"
HARRIS = "P00009423"
TRUMP = "P80001571"
OTHER = "H0CA00001"

# Raw FEC rows: Biden and Harris both carry the shared committee's full total,
# and Trump's lacks his redesignated committee.
TOTALS_PAGE_1 = [
    {"candidate_id": BIDEN, "cycle": CYCLE, "receipts": 1000, "disbursements": 900},
    {"candidate_id": HARRIS, "cycle": CYCLE, "receipts": 1000, "disbursements": 900},
    {"candidate_id": TRUMP, "cycle": CYCLE, "receipts": 100, "disbursements": 90},
]
TOTALS_PAGE_2 = [
    {"candidate_id": OTHER, "cycle": CYCLE, "receipts": 10, "disbursements": 9},
]

# Shared committee's periodic reports, one period either side of the split.
SPLIT_REPORTS = [
    {
        "coverage_start_date": "2024-01-01T00:00:00",
        "coverage_end_date": "2024-06-30T00:00:00",
        "total_receipts_period": 600,
        "total_disbursements_period": 540,
        "most_recent": True,
    },
    {
        "coverage_start_date": "2024-08-01T00:00:00",
        "coverage_end_date": "2024-09-30T00:00:00",
        "total_receipts_period": 400,
        "total_disbursements_period": 360,
        "most_recent": True,
    },
]

# Corrected totals after exclusion, overrides and the split are applied.
EXPECTED = {
    BIDEN: (Decimal("600.00"), Decimal("540.00")),
    HARRIS: (Decimal("400.00"), Decimal("367.00")),  # split 360 + solo committee 7
    TRUMP: (Decimal("150.00"), Decimal("130.00")),  # FEC 100/90 + override 50/40
    OTHER: (Decimal("10.00"), Decimal("9.00")),
}


def _page(results: list, pages: int = 1) -> httpx.Response:
    return httpx.Response(
        200, json={"results": results, "pagination": {"pages": pages}}
    )


CANDIDATE_TOTALS = "/candidates/totals/"
OVERRIDE_TOTALS = "/committee/C00828541/totals/"  # Trump's redesignated committee
HARRIS_SOLO_TOTALS = "/committee/C00694455/totals/"
SPLIT_REPORTS_PATH = "/committee/C00703975/reports/"  # Biden/Harris shared committee


def _mock_fec(client) -> dict:
    """Mock every FEC endpoint the ingestor hits, each with two pages. Set the
    returned state's `failing` to an endpoint path to make its page 2 503."""
    state: dict = {"failing": None}

    def endpoint(path: str, page_1: list, page_2: list) -> None:
        def respond(request: httpx.Request) -> httpx.Response:
            if request.url.params["page"] == "1":
                return _page(page_1, pages=2)
            if state["failing"] == path:
                return httpx.Response(503, json={"error": "Unavailable"})
            return _page(page_2, pages=2)

        respx.get(url__startswith=f"{client.base_url}{path}").mock(side_effect=respond)

    endpoint(CANDIDATE_TOTALS, TOTALS_PAGE_1, TOTALS_PAGE_2)
    endpoint(OVERRIDE_TOTALS, [{"receipts": 50, "disbursements": 40}], [])
    endpoint(HARRIS_SOLO_TOTALS, [{"receipts": 0, "disbursements": 7}], [])
    endpoint(SPLIT_REPORTS_PATH, SPLIT_REPORTS, [])
    return state


async def _stored_totals(session: AsyncSession) -> dict:
    session.expunge_all()
    rows = (await session.execute(select(InsideTotalsByCandidate))).scalars().all()
    return {r.candidate_id: (r.receipts, r.disbursements) for r in rows}


@pytest_asyncio.fixture
async def seeded_candidates(async_db: AsyncSession):
    for candidate_id in (BIDEN, HARRIS, TRUMP, OTHER):
        async_db.add(Candidate(candidate_id=candidate_id, name=candidate_id))
    await async_db.commit()


@pytest.mark.integration
@pytest.mark.asyncio
class TestInsideTotalsIngestionRun:
    @respx.mock
    async def test_clean_run_stores_corrected_totals(
        self, async_db, client, seeded_candidates
    ):
        _mock_fec(client)

        await InsideTotalsByCandidateIngestor(client, async_db).run(cycle=CYCLE)

        assert await _stored_totals(async_db) == EXPECTED

    @pytest.mark.parametrize(
        "failing",
        [CANDIDATE_TOTALS, OVERRIDE_TOTALS, SPLIT_REPORTS_PATH],
        ids=["candidate_totals", "override_totals", "split_reports"],
    )
    @respx.mock
    async def test_partial_fetch_fails_run_and_keeps_corrected_totals(
        self, async_db, client, seeded_candidates, mocker, failing
    ):
        mocker.patch("asyncio.sleep")  # skip fec_retry backoff
        fec = _mock_fec(client)
        await InsideTotalsByCandidateIngestor(client, async_db).run(cycle=CYCLE)

        # Next nightly run: page 2 of one endpoint fails after retries.
        fec["failing"] = failing
        with pytest.raises(PartialFetchError):
            await InsideTotalsByCandidateIngestor(client, async_db).run(cycle=CYCLE)

        assert await _stored_totals(async_db) == EXPECTED
        run = (await async_db.execute(select(IngestionRun))).scalar_one()
        assert run.status == IngestionRunStatus.FAILED
        assert run.error_message.startswith("1/2 pages failed")
        assert run.last_run_completed_at is not None  # cycle stays ready
