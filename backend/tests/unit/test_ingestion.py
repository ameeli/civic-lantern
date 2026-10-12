import asyncio
import signal
from unittest.mock import AsyncMock, patch

import pytest

from civic_lantern.db.models.ingestion_run import IngestionRunStatus
from civic_lantern.db.session import JobSessionLocal
from civic_lantern.jobs.ingestion import _run_cancellable, ingest, main, run_nightly
from civic_lantern.jobs.manager import RunReport
from civic_lantern.jobs.pipeline import RunOutcome

OK = RunOutcome(
    IngestionRunStatus.SUCCESS,
    {"inserted": 1, "updated": 0, "errors": 0, "failed_ids": []},
)
FAILED = RunOutcome(IngestionRunStatus.FAILED, error="FEC API down")


@pytest.fixture
def wiring():
    """The production FECClient and IngestionManager, mocked at the
    composition root; yields the manager instance the entry points use."""
    with (
        patch("civic_lantern.jobs.ingestion.FECClient", autospec=True) as MockClient,
        patch(
            "civic_lantern.jobs.ingestion.IngestionManager", autospec=True
        ) as MockManager,
    ):
        client = MockClient.return_value.__aenter__.return_value
        yield MockManager, client


@pytest.mark.unit
@pytest.mark.asyncio
class TestIngestEntryPoint:
    """ingest() builds the production manager and delegates to ingest_batch()."""

    async def test_wires_a_live_client_and_the_job_sessions(self, wiring):
        MockManager, client = wiring
        report = RunReport(outcomes={("candidates", None): OK})
        MockManager.return_value.ingest_batch.return_value = report

        result = await ingest(
            start_date="2024-01-01", end_date="2024-06-01", entities=["candidates"]
        )

        assert result is report
        MockManager.assert_called_once_with(client, JobSessionLocal)
        MockManager.return_value.ingest_batch.assert_awaited_once_with(
            ["candidates"], "2024-01-01", "2024-06-01"
        )

    async def test_passes_none_when_no_entities(self, wiring):
        MockManager, _ = wiring
        MockManager.return_value.ingest_batch.return_value = RunReport()

        await ingest(start_date="2024-01-01", end_date="2024-06-01")

        MockManager.return_value.ingest_batch.assert_awaited_once_with(
            None, "2024-01-01", "2024-06-01"
        )


@pytest.mark.unit
@pytest.mark.asyncio
class TestRunNightlyEntryPoint:
    async def test_delegates_to_the_production_manager(self, wiring):
        MockManager, client = wiring
        report = RunReport(outcomes={("committees", None): OK})
        MockManager.return_value.run_nightly.return_value = report

        assert await run_nightly() is report
        MockManager.assert_called_once_with(client, JobSessionLocal)


@pytest.mark.unit
class TestMainEntryPoint:
    """Test the main() CLI entrypoint's exit-code behavior.

    argv=[] is passed explicitly so argparse doesn't try to parse pytest's
    own command-line arguments.
    """

    @patch("civic_lantern.jobs.ingestion.configure_logging")
    @patch("civic_lantern.jobs.ingestion.run_nightly", new_callable=AsyncMock)
    def test_main_exits_zero_on_full_success(
        self, mock_run_nightly, mock_configure_logging
    ):
        mock_run_nightly.return_value = RunReport(outcomes={("committees", None): OK})

        main(argv=[])  # should not raise / should not call sys.exit

        mock_configure_logging.assert_called_once()

    @patch("civic_lantern.jobs.ingestion.configure_logging")
    @patch("civic_lantern.jobs.ingestion.run_nightly", new_callable=AsyncMock)
    def test_main_exits_one_on_any_failure(
        self, mock_run_nightly, mock_configure_logging
    ):
        mock_run_nightly.return_value = RunReport(
            outcomes={("committees", None): OK, ("candidates", None): FAILED}
        )

        with pytest.raises(SystemExit) as exc_info:
            main(argv=[])

        assert exc_info.value.code == 1

    @patch("civic_lantern.jobs.ingestion.configure_logging")
    @patch("civic_lantern.jobs.ingestion.run_nightly", new_callable=AsyncMock)
    def test_main_logs_the_run_summary(
        self, mock_run_nightly, mock_configure_logging, caplog
    ):
        report = RunReport(
            outcomes={("committees", None): OK},
            mv_refresh_error="lock timeout",
        )
        mock_run_nightly.return_value = report

        with caplog.at_level("INFO", logger="civic_lantern.jobs.ingestion"):
            with pytest.raises(SystemExit):
                main(argv=[])

        assert report.summary() in caplog.messages
        assert (
            "Ingestion completed with failures: ['refresh_spending_stats']"
            in caplog.messages
        )

    @patch("civic_lantern.jobs.ingestion.configure_logging")
    @patch("civic_lantern.jobs.ingestion.run_nightly", new_callable=AsyncMock)
    def test_main_ignores_skipped_overlap_guard_result(
        self, mock_run_nightly, mock_configure_logging
    ):
        mock_run_nightly.return_value = RunReport(skipped=True)

        main(argv=[])  # should not raise

    @patch("civic_lantern.jobs.ingestion.configure_logging")
    @patch("civic_lantern.jobs.ingestion.run_nightly", new_callable=AsyncMock)
    def test_main_with_no_args_runs_nightly(
        self, mock_run_nightly, mock_configure_logging
    ):
        """No --entities means the nightly cron trigger's behavior is unchanged."""
        mock_run_nightly.return_value = RunReport()

        main(argv=[])

        mock_run_nightly.assert_awaited_once()

    @patch("civic_lantern.jobs.ingestion.configure_logging")
    @patch("civic_lantern.jobs.ingestion.ingest", new_callable=AsyncMock)
    def test_main_with_entities_runs_scoped_ingest(
        self, mock_ingest, mock_configure_logging
    ):
        """--entities (with an optional --cycle) calls ingest() instead of
        run_nightly(), scoped to just what was asked for."""
        mock_ingest.return_value = RunReport()

        main(argv=["--entities", "inside_totals_by_candidate", "--cycle", "2024"])

        mock_ingest.assert_awaited_once_with(
            entities=["inside_totals_by_candidate"], cycle=2024
        )

    @patch("civic_lantern.jobs.ingestion.configure_logging")
    @patch("civic_lantern.jobs.ingestion.ingest", new_callable=AsyncMock)
    def test_main_with_entities_and_no_cycle(self, mock_ingest, mock_configure_logging):
        """--cycle is optional — omitting it doesn't pass cycle=None through."""
        mock_ingest.return_value = RunReport()

        main(argv=["--entities", "candidates"])

        mock_ingest.assert_awaited_once_with(entities=["candidates"])

    @patch("civic_lantern.jobs.ingestion.configure_logging")
    @patch("civic_lantern.jobs.ingestion.ingest", new_callable=AsyncMock)
    def test_main_with_multiple_entities(self, mock_ingest, mock_configure_logging):
        """Comma-separated --entities splits into a list, trimming whitespace."""
        mock_ingest.return_value = RunReport()

        main(argv=["--entities", "candidates, committees"])

        mock_ingest.assert_awaited_once_with(entities=["candidates", "committees"])

    @patch("civic_lantern.jobs.ingestion.configure_logging")
    @patch("civic_lantern.jobs.ingestion.run_nightly", new_callable=AsyncMock)
    def test_main_exits_cleanly_on_cancellation(
        self, mock_run_nightly, mock_configure_logging
    ):
        """A SIGTERM-triggered cancellation exits with code 1 instead of an
        uncaught CancelledError traceback."""
        mock_run_nightly.side_effect = asyncio.CancelledError()

        with pytest.raises(SystemExit) as exc_info:
            main(argv=[])

        assert exc_info.value.code == 1


@pytest.mark.unit
@pytest.mark.asyncio
class TestRunCancellable:
    """_run_cancellable wires SIGTERM to task cancellation instead of an
    abrupt process kill, so run_ingestion() gets a chance to record a
    CANCELLED status before the process exits."""

    async def test_returns_result_normally(self):
        async def coro():
            return "done"

        assert await _run_cancellable(coro()) == "done"

    async def test_reraises_cancelled_error(self):
        async def coro():
            raise asyncio.CancelledError()

        with pytest.raises(asyncio.CancelledError):
            await _run_cancellable(coro())

    async def test_sigterm_handler_cancels_the_running_task(self, mocker):
        """The callback registered for SIGTERM is the inner task's cancel(),
        so simulating signal delivery actually cancels the in-flight coroutine
        rather than being a no-op."""
        loop = asyncio.get_running_loop()
        registered = {}
        mocker.patch.object(
            loop,
            "add_signal_handler",
            side_effect=lambda sig, cb: registered.__setitem__(sig, cb),
        )
        mocker.patch.object(loop, "remove_signal_handler")

        async def coro():
            await asyncio.sleep(10)

        outer_task = asyncio.ensure_future(_run_cancellable(coro()))
        await asyncio.sleep(0)  # let _run_cancellable register the handler
        assert signal.SIGTERM in registered

        registered[signal.SIGTERM]()  # simulate the OS delivering SIGTERM

        with pytest.raises(asyncio.CancelledError):
            await outer_task
