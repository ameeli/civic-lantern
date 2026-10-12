from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import TextClause

from civic_lantern.db.models.ingestion_run import IngestionRunStatus
from civic_lantern.jobs.ingestors.candidates import CANDIDATES_INGESTION
from civic_lantern.jobs.manager import (
    DATE_WINDOWED_ENTITIES,
    MV_REFRESH_LABEL,
    OVERLAP_TIMEOUT_MINUTES,
    SPENDING_ENTITIES,
    RunReport,
)
from civic_lantern.jobs.pipeline import RunOutcome
from civic_lantern.services.data.base import UpsertStats

STATS: UpsertStats = {"inserted": 1, "updated": 2, "errors": 0, "failed_ids": []}
WROTE = RunOutcome(IngestionRunStatus.SUCCESS, STATS)
EMPTY = RunOutcome(IngestionRunStatus.SUCCESS)


@pytest.fixture
def mock_run():
    with patch(
        "civic_lantern.jobs.manager.run_ingestion",
        new_callable=AsyncMock,
        return_value=WROTE,
    ) as mock:
        yield mock


@pytest.fixture
def mock_refresh(manager):
    with patch.object(manager, "refresh_spending_stats", new_callable=AsyncMock) as m:
        yield m


@pytest.fixture
def guard():
    """The nightly overlap guard, reporting no active run."""
    with patch(
        "civic_lantern.jobs.manager.IngestionRunService", autospec=True
    ) as MockRunService:
        service = MockRunService.return_value
        service.has_active_run = AsyncMock(return_value=False)
        service.reset_stale_runs = AsyncMock()
        yield service


@pytest.mark.unit
@pytest.mark.asyncio
class TestIngest:
    async def test_runs_the_named_declaration_with_the_injected_deps(
        self, manager, mock_run, mock_client, mock_session
    ):
        outcome = await manager.ingest("candidates", start_date="2024-01-01")

        assert outcome is WROTE
        mock_run.assert_awaited_once_with(
            CANDIDATES_INGESTION,
            mock_client,
            mock_session,
            cycle=None,
            start_date="2024-01-01",
            end_date=None,
        )

    async def test_unknown_entity_raises(self, manager):
        with pytest.raises(ValueError, match="Unknown entity: 'nonexistent'"):
            await manager.ingest("nonexistent")

    async def test_a_failed_run_raises(self, manager, mock_run):
        mock_run.side_effect = RuntimeError("FEC API down")

        with pytest.raises(RuntimeError, match="FEC API down"):
            await manager.ingest("candidates")


@pytest.mark.unit
@pytest.mark.asyncio
class TestIngestBatch:
    async def test_runs_in_declaration_order(self, manager, mock_run):
        report = await manager.ingest_batch(["candidates", "committees"])

        ran = [c.args[0].entity for c in mock_run.await_args_list]
        assert ran == ["committees", "candidates"]
        assert list(report.outcomes) == [("committees", None), ("candidates", None)]

    async def test_rejects_unknown_entities_before_running(self, manager, mock_run):
        with pytest.raises(ValueError, match="Unknown entity: 'nope'"):
            await manager.ingest_batch(["candidates", "nope"])

        mock_run.assert_not_awaited()

    async def test_a_failure_is_recorded_and_the_rest_still_run(
        self, manager, mock_run
    ):
        async def run(ingestion, *args, **kwargs):
            if ingestion.entity == "committees":
                raise RuntimeError("FEC API down")
            return WROTE

        mock_run.side_effect = run

        report = await manager.ingest_batch(["committees", "candidates"])

        assert report.outcomes[("committees", None)] == RunOutcome(
            IngestionRunStatus.FAILED, error="FEC API down"
        )
        assert report.outcomes[("candidates", None)] is WROTE
        assert report.failed == ["committees"]

    async def test_records_the_cycle_in_each_key(self, manager, mock_run, mock_refresh):
        report = await manager.ingest_batch(SPENDING_ENTITIES, cycle=2024)

        assert list(report.outcomes) == [(name, 2024) for name in SPENDING_ENTITIES]

    async def test_refreshes_mvs_when_a_spending_run_wrote_rows(
        self, manager, mock_run, mock_refresh
    ):
        await manager.ingest_batch(["inside_totals_by_candidate"], cycle=2024)

        mock_refresh.assert_awaited_once()

    @pytest.mark.parametrize(
        "outcome",
        [EMPTY, RuntimeError("spending fetch failed")],
        ids=["no_rows", "failed"],
    )
    async def test_skips_mv_refresh_when_no_spending_run_wrote_rows(
        self, manager, mock_run, mock_refresh, outcome
    ):
        if isinstance(outcome, Exception):
            mock_run.side_effect = outcome
        else:
            mock_run.return_value = outcome

        await manager.ingest_batch(["inside_totals_by_candidate"], cycle=2024)

        mock_refresh.assert_not_awaited()

    async def test_skips_mv_refresh_for_non_spending_entities(
        self, manager, mock_run, mock_refresh
    ):
        await manager.ingest_batch(["committees"])

        mock_refresh.assert_not_awaited()

    async def test_records_an_mv_refresh_failure(self, manager, mock_run, mock_refresh):
        mock_refresh.side_effect = RuntimeError("lock timeout")

        report = await manager.ingest_batch(["inside_totals_by_candidate"], cycle=2024)

        assert report.outcomes[("inside_totals_by_candidate", 2024)] is WROTE
        assert report.mv_refresh_error == "lock timeout"
        assert report.failed == [MV_REFRESH_LABEL]


@pytest.mark.unit
@pytest.mark.asyncio
class TestRefreshSpendingStats:
    async def test_issues_both_refreshes_in_one_injected_session(
        self, manager, mock_session
    ):
        await manager.refresh_spending_stats()

        calls = mock_session.execute.call_args_list
        assert [str(c.args[0]).split()[-1] for c in calls] == [
            "mv_candidate_spending_summary",
            "mv_election_spending_summary",
        ]
        assert all(isinstance(c.args[0], TextClause) for c in calls)
        mock_session.commit.assert_awaited_once()

    async def test_raises_on_failure(self, manager, mock_session):
        mock_session.execute.side_effect = RuntimeError("lock timeout")

        with pytest.raises(RuntimeError, match="lock timeout"):
            await manager.refresh_spending_stats()


@pytest.mark.unit
@pytest.mark.asyncio
class TestRunNightly:
    async def test_skips_when_overlap_guard_active(self, manager, mock_run, guard):
        guard.has_active_run.return_value = True

        report = await manager.run_nightly()

        assert report == RunReport(skipped=True)
        mock_run.assert_not_awaited()
        guard.reset_stale_runs.assert_not_awaited()

    async def test_resets_stale_runs_when_no_active_run(self, manager, mock_run, guard):
        with patch("civic_lantern.jobs.manager.active_cycles", return_value=[]):
            await manager.run_nightly()

        guard.reset_stale_runs.assert_awaited_once_with(OVERLAP_TIMEOUT_MINUTES)

    async def test_runs_date_windowed_once_and_spending_per_active_cycle(
        self, manager, mock_run, mock_refresh, guard
    ):
        with patch(
            "civic_lantern.jobs.manager.active_cycles", return_value=[2024, 2026]
        ):
            report = await manager.run_nightly()

        expected = [
            *((name, None) for name in DATE_WINDOWED_ENTITIES),
            *((name, 2024) for name in SPENDING_ENTITIES),
            *((name, 2026) for name in SPENDING_ENTITIES),
        ]
        ran = [(c.args[0].entity, c.kwargs["cycle"]) for c in mock_run.await_args_list]
        assert ran == expected
        assert list(report.outcomes) == expected

    async def test_refreshes_mvs_once_total_not_once_per_cycle(
        self, manager, mock_run, mock_refresh, guard
    ):
        """The MVs span every cycle — refresh once per run, not per cycle."""
        with patch(
            "civic_lantern.jobs.manager.active_cycles", return_value=[2024, 2026]
        ):
            await manager.run_nightly()

        mock_refresh.assert_awaited_once()

    async def test_records_an_mv_refresh_failure(
        self, manager, mock_run, mock_refresh, guard
    ):
        mock_refresh.side_effect = RuntimeError("lock timeout")

        with patch("civic_lantern.jobs.manager.active_cycles", return_value=[2024]):
            report = await manager.run_nightly()

        assert report.mv_refresh_error == "lock timeout"

    async def test_skips_mv_refresh_when_every_spending_run_fails(
        self, manager, mock_run, mock_refresh, guard
    ):
        mock_run.side_effect = RuntimeError("boom")

        with patch("civic_lantern.jobs.manager.active_cycles", return_value=[2024]):
            report = await manager.run_nightly()

        mock_refresh.assert_not_awaited()
        assert set(report.failed) == {
            *DATE_WINDOWED_ENTITIES,
            *(f"{name}:2024" for name in SPENDING_ENTITIES),
        }


@pytest.mark.unit
class TestRunReport:
    def test_partial_success_is_not_a_failure(self):
        partial = RunOutcome(IngestionRunStatus.PARTIAL_SUCCESS, STATS, "1/2 pages")
        report = RunReport(outcomes={("committees", None): partial})

        assert report.failed == []

    def test_summary_lists_each_run_and_a_failed_refresh(self):
        report = RunReport(
            outcomes={
                ("committees", None): WROTE,
                ("inside_totals_by_candidate", 2024): RunOutcome(
                    IngestionRunStatus.PARTIAL_SUCCESS,
                    {"inserted": 0, "updated": 3, "errors": 1, "failed_ids": ["P1"]},
                    "1 row(s) failed to upsert: ['P1']",
                ),
                ("candidates", None): RunOutcome(
                    IngestionRunStatus.FAILED, error="FEC API down"
                ),
                ("schedule_e_totals_by_candidate", 2026): EMPTY,
            },
            mv_refresh_error="lock timeout",
        )

        assert report.summary().splitlines() == [
            "Ingestion summary:",
            "  committees                           success          "
            "inserted=1 updated=2 errors=0",
            "  inside_totals_by_candidate:2024      partial_success  "
            "inserted=0 updated=3 errors=1  1 row(s) failed to upsert: ['P1']",
            "  candidates                           failed           FEC API down",
            "  schedule_e_totals_by_candidate:2026  success",
            "  refresh_spending_stats               failed           lock timeout",
        ]

    def test_summary_when_skipped_or_empty(self):
        assert RunReport(skipped=True).summary() == (
            "Ingestion skipped: another run is in progress."
        )
        assert RunReport().summary() == "Ingestion summary: nothing ran."
