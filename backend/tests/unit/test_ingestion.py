from unittest.mock import AsyncMock, patch

import pytest

from civic_lantern.jobs.ingestion import ingest, main, run_nightly


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
    """Test the main() CLI entrypoint's exit-code behavior."""

    @patch("civic_lantern.jobs.ingestion.configure_logging")
    @patch("civic_lantern.jobs.ingestion.run_nightly", new_callable=AsyncMock)
    def test_main_exits_zero_on_full_success(
        self, mock_run_nightly, mock_configure_logging
    ):
        mock_run_nightly.return_value = {"committees": {"inserted": 1, "errors": 0}}

        main()  # should not raise / should not call sys.exit

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
            main()

        assert exc_info.value.code == 1

    @patch("civic_lantern.jobs.ingestion.configure_logging")
    @patch("civic_lantern.jobs.ingestion.run_nightly", new_callable=AsyncMock)
    def test_main_ignores_skipped_overlap_guard_result(
        self, mock_run_nightly, mock_configure_logging
    ):
        mock_run_nightly.return_value = {"skipped": "overlap_guard"}

        main()  # should not raise
