from unittest.mock import patch

import pytest

from civic_lantern.jobs.ingestion import ingest


@pytest.mark.unit
@pytest.mark.asyncio
class TestIngestEntryPoint:
    """Test the top-level ingest() entry point delegates to IngestionManager."""

    @patch("civic_lantern.jobs.ingestion.IngestionManager", autospec=True)
    async def test_ingest_delegates_to_ingest_batch(self, MockManager):
        """ingest() passes all args through to manager.ingest_batch()."""
        mock_manager = MockManager.return_value.__aenter__.return_value
        mock_manager.ingest_batch.return_value = {
            "candidates": {"upserted": 10, "errors": 0}
        }

        results = await ingest(
            start_date="2024-01-01",
            end_date="2024-06-01",
            entities=["candidates"],
        )

        mock_manager.ingest_batch.assert_awaited_once_with(
            ["candidates"], "2024-01-01", "2024-06-01"
        )
        assert results["candidates"]["upserted"] == 10

    @patch("civic_lantern.jobs.ingestion.IngestionManager", autospec=True)
    async def test_ingest_passes_none_when_no_entities(self, MockManager):
        """Calling ingest() with no entities passes None to ingest_batch."""
        mock_manager = MockManager.return_value.__aenter__.return_value
        mock_manager.ingest_batch.return_value = {}

        await ingest(start_date="2024-01-01", end_date="2024-06-01")

        mock_manager.ingest_batch.assert_awaited_once_with(
            None, "2024-01-01", "2024-06-01"
        )
