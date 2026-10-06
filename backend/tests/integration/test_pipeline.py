"""Integration tests for run_ingestion(): real declarations, FEC HTTP mocked
with respx, real test Postgres for rows and `ingestion_runs`."""

import asyncio
from datetime import datetime, timezone

import httpx
import pytest
import respx
from sqlalchemy import select

from civic_lantern.db.models.candidate import Candidate
from civic_lantern.db.models.committee import Committee
from civic_lantern.db.models.ingestion_run import IngestionRun, IngestionRunStatus
from civic_lantern.db.models.inside_totals_by_candidate import InsideTotalsByCandidate
from civic_lantern.db.models.schedule_e_totals_by_candidate import (
    ScheduleETotalsByCandidate,
)
from civic_lantern.jobs.ingestors.committees import COMMITTEES_INGESTION
from civic_lantern.jobs.ingestors.inside_totals_by_candidate import (
    INSIDE_TOTALS_INGESTION,
)
from civic_lantern.jobs.ingestors.schedule_e_totals_by_candidate import (
    SCHEDULE_E_TOTALS_INGESTION,
)
from civic_lantern.jobs.pipeline import FEC_TIMEZONE, InvalidRowError, run_ingestion
from civic_lantern.services.fec_exceptions import PartialFetchError

COMMITTEES_PATH = "/committees/"
SCHEDULE_E_PATH = "/schedules/schedule_e/totals/by_candidate/"
CANDIDATE_TOTALS_PATH = "/candidates/totals/"


def _page(results: list, pages: int = 1) -> httpx.Response:
    return httpx.Response(
        200, json={"results": results, "pagination": {"pages": pages}}
    )


def _mock(client, path, pages):
    """Serve `pages` (a list of row lists, or an httpx.Response) by page number."""

    def respond(request):
        page = pages[int(request.url.params["page"]) - 1]
        return page if isinstance(page, httpx.Response) else _page(page, len(pages))

    return respx.get(f"{client.base_url}{path}").mock(side_effect=respond)


def _ie(candidate_id, indicator="S", total=10):
    return {
        "candidate_id": candidate_id,
        "cycle": 2024,
        "support_oppose_indicator": indicator,
        "total": total,
    }


async def _run_row(session, entity):
    session.expunge_all()
    stmt = select(IngestionRun).where(IngestionRun.ingestor_name == entity)
    return (await session.execute(stmt)).scalar_one_or_none()


async def _count(session, model):
    session.expunge_all()
    return len((await session.execute(select(model))).scalars().all())


async def _seed_candidates(session, *ids):
    for candidate_id in ids:
        session.add(Candidate(candidate_id=candidate_id, name=candidate_id))
    await session.commit()


@pytest.mark.integration
@pytest.mark.asyncio
class TestDateWindowScope:
    @respx.mock
    async def test_first_run_has_no_lower_bound(self, async_db, client, mocker):
        today = datetime(2025, 6, 15, 10, 0, tzinfo=FEC_TIMEZONE)
        mock_dt = mocker.patch("civic_lantern.jobs.pipeline.datetime")
        mock_dt.now.return_value = today
        route = _mock(client, COMMITTEES_PATH, [[{"committee_id": "C1", "name": "A"}]])

        stats = await run_ingestion(COMMITTEES_INGESTION, client, async_db)

        params = route.calls[0].request.url.params
        assert params["max_first_file_date"] == "2025-06-15"
        assert "min_first_file_date" not in params
        assert stats["inserted"] == 1
        run = await _run_row(async_db, "committees")
        assert run.status == IngestionRunStatus.SUCCESS
        assert run.cycle is None
        assert run.last_run_completed_at is not None

    @respx.mock
    async def test_resumes_from_the_watermark_in_eastern_time(self, async_db, client):
        async_db.add(
            IngestionRun(
                ingestor_name="committees",
                cycle=None,
                status=IngestionRunStatus.SUCCESS,
                started_at=datetime(2024, 3, 1, 2, tzinfo=timezone.utc),
                # 03:00 UTC on Mar 1 is still Feb 29 in New York.
                last_run_completed_at=datetime(2024, 3, 1, 3, tzinfo=timezone.utc),
            )
        )
        await async_db.commit()
        route = _mock(client, COMMITTEES_PATH, [[]])

        await run_ingestion(COMMITTEES_INGESTION, client, async_db)

        assert route.calls[0].request.url.params["min_first_file_date"] == "2024-02-29"

    @respx.mock
    async def test_explicit_dates_are_sent_as_is(self, async_db, client):
        route = _mock(client, COMMITTEES_PATH, [[]])

        await run_ingestion(
            COMMITTEES_INGESTION,
            client,
            async_db,
            start_date="2024-01-01",
            end_date="2024-02-01",
        )

        params = route.calls[0].request.url.params
        assert params["min_first_file_date"] == "2024-01-01"
        assert params["max_first_file_date"] == "2024-02-01"


@pytest.mark.integration
@pytest.mark.asyncio
class TestScopeChecks:
    @pytest.mark.parametrize(
        "ingestion, kwargs, message",
        [
            (SCHEDULE_E_TOTALS_INGESTION, {}, "runs per cycle"),
            (COMMITTEES_INGESTION, {"cycle": 2024}, "date window"),
        ],
    )
    async def test_mismatched_scope_fails_before_any_run_is_recorded(
        self, async_db, client, ingestion, kwargs, message
    ):
        with pytest.raises(ValueError, match=message):
            await run_ingestion(ingestion, client, async_db, **kwargs)

        assert await _run_row(async_db, ingestion.entity) is None

    @respx.mock
    async def test_per_cycle_ingestions_ignore_dates(self, async_db, client):
        route = _mock(client, SCHEDULE_E_PATH, [[]])

        await run_ingestion(
            SCHEDULE_E_TOTALS_INGESTION,
            client,
            async_db,
            cycle=2024,
            start_date="2024-01-01",
        )

        params = route.calls[0].request.url.params
        assert params["cycle"] == "2024"
        assert "min_first_file_date" not in params


@pytest.mark.integration
@pytest.mark.asyncio
class TestPartialFetch:
    @respx.mock
    async def test_keep_first_ingestion_writes_partial_rows(
        self, async_db, client, mocker
    ):
        mocker.patch("asyncio.sleep")  # skip fec_retry backoff
        await _seed_candidates(async_db, "P1")
        _mock(client, SCHEDULE_E_PATH, [[_ie("P1")], httpx.Response(503)])

        await run_ingestion(SCHEDULE_E_TOTALS_INGESTION, client, async_db, cycle=2024)

        assert await _count(async_db, ScheduleETotalsByCandidate) == 1
        run = await _run_row(async_db, "schedule_e_totals_by_candidate")
        assert run.status == IngestionRunStatus.PARTIAL_SUCCESS
        assert (
            run.error_message == "1/2 pages failed for schedule E totals by candidate"
        )
        assert run.last_run_completed_at is None

    @respx.mock
    async def test_summing_ingestion_fails_and_writes_nothing(
        self, async_db, client, mocker
    ):
        mocker.patch("asyncio.sleep")
        await _seed_candidates(async_db, "P1")
        row = {"candidate_id": "P1", "cycle": 2022, "receipts": 1, "disbursements": 1}
        _mock(client, CANDIDATE_TOTALS_PATH, [[row], httpx.Response(503)])

        with pytest.raises(PartialFetchError):
            await run_ingestion(INSIDE_TOTALS_INGESTION, client, async_db, cycle=2022)

        assert await _count(async_db, InsideTotalsByCandidate) == 0
        run = await _run_row(async_db, "inside_totals_by_candidate")
        assert run.status == IngestionRunStatus.FAILED
        assert run.error_message.startswith("1/2 pages failed")


@pytest.mark.integration
@pytest.mark.asyncio
class TestRunOutcomes:
    @respx.mock
    async def test_bad_amount_in_a_summing_ingestion_fails_the_run(
        self, async_db, client
    ):
        await _seed_candidates(async_db, "P1")
        rows = [
            {"candidate_id": "P1", "cycle": 2022, "receipts": 5, "disbursements": 5},
            {"candidate_id": "P1", "cycle": 2022, "receipts": "abc"},
        ]
        _mock(client, CANDIDATE_TOTALS_PATH, [rows])

        with pytest.raises(InvalidRowError):
            await run_ingestion(INSIDE_TOTALS_INGESTION, client, async_db, cycle=2022)

        assert await _count(async_db, InsideTotalsByCandidate) == 0
        run = await _run_row(async_db, "inside_totals_by_candidate")
        assert run.status == IngestionRunStatus.FAILED

    @respx.mock
    async def test_upsert_errors_give_partial_success_with_a_key_preview(
        self, async_db, client
    ):
        # No candidates seeded, so every row violates the candidates foreign key.
        rows = [_ie(f"P{i:02d}") for i in range(25)]
        _mock(client, SCHEDULE_E_PATH, [rows])

        stats = await run_ingestion(
            SCHEDULE_E_TOTALS_INGESTION, client, async_db, cycle=2024
        )

        assert stats["errors"] == 25
        run = await _run_row(async_db, "schedule_e_totals_by_candidate")
        assert run.status == IngestionRunStatus.PARTIAL_SUCCESS
        assert run.error_message.startswith(
            "25 row(s) failed to upsert: [('P00', 2024, 'S'), ('P01', 2024, 'S'),"
        )
        assert run.error_message.endswith("(+5 more)")

    @respx.mock
    async def test_empty_result_is_a_success_returning_none(self, async_db, client):
        _mock(client, SCHEDULE_E_PATH, [[]])

        result = await run_ingestion(
            SCHEDULE_E_TOTALS_INGESTION, client, async_db, cycle=2024
        )

        assert result is None
        run = await _run_row(async_db, "schedule_e_totals_by_candidate")
        assert run.status == IngestionRunStatus.SUCCESS
        assert run.last_run_completed_at is not None

    @respx.mock
    async def test_fetch_error_fails_the_run_and_reraises(self, async_db, client):
        _mock(client, COMMITTEES_PATH, [httpx.Response(404)])

        with pytest.raises(Exception, match="Resource not found"):
            await run_ingestion(COMMITTEES_INGESTION, client, async_db)

        run = await _run_row(async_db, "committees")
        assert run.status == IngestionRunStatus.FAILED
        assert run.error_message.startswith("Resource not found")

    @respx.mock
    async def test_cancellation_is_recorded_and_reraised(self, async_db, client):
        in_flight = asyncio.Event()

        async def hang(request):
            in_flight.set()
            await asyncio.sleep(3600)

        respx.get(f"{client.base_url}{COMMITTEES_PATH}").mock(side_effect=hang)
        task = asyncio.create_task(
            run_ingestion(COMMITTEES_INGESTION, client, async_db)
        )
        await in_flight.wait()
        task.cancel()  # what the CLI's SIGTERM handler does

        with pytest.raises(asyncio.CancelledError):
            await task

        run = await _run_row(async_db, "committees")
        assert run.status == IngestionRunStatus.CANCELLED

    @respx.mock
    async def test_duplicate_keys_keep_the_first_row(self, async_db, client):
        rows = [
            {"committee_id": "C1", "name": "First"},
            {"committee_id": "C1", "name": "Second"},
        ]
        _mock(client, COMMITTEES_PATH, [rows])

        stats = await run_ingestion(COMMITTEES_INGESTION, client, async_db)

        assert stats["inserted"] == 1
        async_db.expunge_all()
        stored = await async_db.get(Committee, "C1")
        assert stored.name == "First"
