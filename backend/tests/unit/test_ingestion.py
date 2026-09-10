import asyncio
import signal
from unittest.mock import AsyncMock, patch

import pytest

from civic_lantern.jobs.ingestion import _run_cancellable, ingest, main, run_nightly


@pytest.mark.unit
@pytest.mark.asyncio
class TestIngestEntryPoint:
    """Test the top-level ingest() entry point delegates to IngestionManager."""

    @patch("civic_lantern.jobs.ingestion.IngestionManager", autospec=True)
    async def test_ingest_delegates_to_ingest_batch(self, MockManager):
        """ingest() passes all args through to manager.ingest_batch()."""
        mock_manager = MockManager.return_value.__aenter__.return_value
        mock_manager.ingest_batch.return_value = {
            "candidates": {"inserted": 8, "updated": 2, "errors": 0}
        }

        results = await ingest(
            start_date="2024-01-01",
            end_date="2024-06-01",
            entities=["candidates"],
        )

        mock_manager.ingest_batch.assert_awaited_once_with(
            ["candidates"], "2024-01-01", "2024-06-01"
        )
        assert (
            results["candidates"]["inserted"] + results["candidates"]["updated"] == 10
        )

    @patch("civic_lantern.jobs.ingestion.IngestionManager", autospec=True)
    async def test_ingest_passes_none_when_no_entities(self, MockManager):
        """Calling ingest() with no entities passes None to ingest_batch."""
        mock_manager = MockManager.return_value.__aenter__.return_value
        mock_manager.ingest_batch.return_value = {}

        await ingest(start_date="2024-01-01", end_date="2024-06-01")

        mock_manager.ingest_batch.assert_awaited_once_with(
            None, "2024-01-01", "2024-06-01"
        )


@pytest.mark.unit
@pytest.mark.asyncio
class TestRunNightlyEntryPoint:
    """Test the run_nightly() wrapper delegates to IngestionManager.run_nightly()."""

    @patch("civic_lantern.jobs.ingestion.IngestionManager", autospec=True)
    async def test_run_nightly_delegates_to_manager(self, MockManager):
        mock_manager = MockManager.return_value.__aenter__.return_value
        mock_manager.run_nightly.return_value = {
            "committees": {"inserted": 1, "updated": 0, "errors": 0}
        }

        result = await run_nightly()

        mock_manager.run_nightly.assert_awaited_once()
        assert result["committees"]["inserted"] == 1


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
        mock_run_nightly.return_value = {"committees": {"inserted": 1, "errors": 0}}

        main(argv=[])  # should not raise / should not call sys.exit

        mock_configure_logging.assert_called_once()

    @patch("civic_lantern.jobs.ingestion.configure_logging")
    @patch("civic_lantern.jobs.ingestion.run_nightly", new_callable=AsyncMock)
    def test_main_exits_one_on_any_failure(
        self, mock_run_nightly, mock_configure_logging
    ):
        mock_run_nightly.return_value = {
            "committees": {"inserted": 1, "errors": 0},
            "candidates": {"error": "FEC API down"},
        }

        with pytest.raises(SystemExit) as exc_info:
            main(argv=[])

        assert exc_info.value.code == 1

    @patch("civic_lantern.jobs.ingestion.configure_logging")
    @patch("civic_lantern.jobs.ingestion.run_nightly", new_callable=AsyncMock)
    def test_main_ignores_skipped_overlap_guard_result(
        self, mock_run_nightly, mock_configure_logging
    ):
        mock_run_nightly.return_value = {"skipped": "overlap_guard"}

        main(argv=[])  # should not raise

    @patch("civic_lantern.jobs.ingestion.configure_logging")
    @patch("civic_lantern.jobs.ingestion.run_nightly", new_callable=AsyncMock)
    def test_main_with_no_args_runs_nightly(
        self, mock_run_nightly, mock_configure_logging
    ):
        """No --entities means the nightly cron trigger's behavior is unchanged."""
        mock_run_nightly.return_value = {}

        main(argv=[])

        mock_run_nightly.assert_awaited_once()

    @patch("civic_lantern.jobs.ingestion.configure_logging")
    @patch("civic_lantern.jobs.ingestion.ingest", new_callable=AsyncMock)
    def test_main_with_entities_runs_scoped_ingest(
        self, mock_ingest, mock_configure_logging
    ):
        """--entities (with an optional --cycle) calls ingest() instead of
        run_nightly(), scoped to just what was asked for."""
        mock_ingest.return_value = {"inside_totals_by_candidate": {"errors": 0}}

        main(argv=["--entities", "inside_totals_by_candidate", "--cycle", "2024"])

        mock_ingest.assert_awaited_once_with(
            entities=["inside_totals_by_candidate"], cycle=2024
        )

    @patch("civic_lantern.jobs.ingestion.configure_logging")
    @patch("civic_lantern.jobs.ingestion.ingest", new_callable=AsyncMock)
    def test_main_with_entities_and_no_cycle(self, mock_ingest, mock_configure_logging):
        """--cycle is optional — omitting it doesn't pass cycle=None through."""
        mock_ingest.return_value = {}

        main(argv=["--entities", "candidates"])

        mock_ingest.assert_awaited_once_with(entities=["candidates"])

    @patch("civic_lantern.jobs.ingestion.configure_logging")
    @patch("civic_lantern.jobs.ingestion.ingest", new_callable=AsyncMock)
    def test_main_with_multiple_entities(self, mock_ingest, mock_configure_logging):
        """Comma-separated --entities splits into a list, trimming whitespace."""
        mock_ingest.return_value = {}

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
    abrupt process kill, so BaseIngestor.run() gets a chance to record a
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
