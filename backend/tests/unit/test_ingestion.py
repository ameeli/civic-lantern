from unittest.mock import patch

import pytest

from civic_lantern.jobs.ingestion import ingest


@pytest.mark.unit
@pytest.mark.asyncio
class TestIngestEntryPoint:
    """Test the top-level ingest() orchestration function."""

    @patch("civic_lantern.jobs.ingestion.IngestionManager", autospec=True)
    async def test_ingest_all_by_default(self, MockManager):
        """Calling ingest() with no entities runs ingest_all."""
        mock_manager = MockManager.return_value.__aenter__.return_value
        mock_manager.ingest_all.return_value = {
            "candidates": {"upserted": 10, "errors": 0}
        }

        results = await ingest(start_date="2024-01-01", end_date="2024-06-01")

        mock_manager.ingest_all.assert_awaited_once_with("2024-01-01", "2024-06-01")
        assert results["candidates"]["upserted"] == 10

    @patch("civic_lantern.jobs.ingestion.IngestionManager", autospec=True)
    async def test_ingest_specific_entities(self, MockManager):
        """Passing entities= runs only those ingestors."""
        mock_manager = MockManager.return_value.__aenter__.return_value
        mock_manager.ingest.return_value = {"upserted": 5, "errors": 0}

        results = await ingest(
            start_date="2024-01-01",
            end_date="2024-06-01",
            entities=["candidates"],
        )

        mock_manager.ingest.assert_awaited_once_with(
            "candidates", "2024-01-01", "2024-06-01"
        )
        assert results["candidates"]["upserted"] == 5

    @patch("civic_lantern.jobs.ingestion.IngestionManager", autospec=True)
    async def test_entity_failure_collected_not_raised(self, MockManager):
        """A failing entity is recorded in results, not raised."""
        mock_manager = MockManager.return_value.__aenter__.return_value
        mock_manager.ingest.side_effect = RuntimeError("FEC down")

        results = await ingest(
            start_date="2024-01-01",
            end_date="2024-06-01",
            entities=["candidates"],
        )

        assert "error" in results["candidates"]
        assert "FEC down" in results["candidates"]["error"]

    @patch("civic_lantern.jobs.ingestion.IngestionManager", autospec=True)
    async def test_multiple_entities_continue_on_failure(self, MockManager):
        """When one entity fails, subsequent entities still run."""
        mock_manager = MockManager.return_value.__aenter__.return_value

        async def side_effect(name, start, end):
            if name == "failing":
                raise RuntimeError("boom")
            return {"upserted": 3, "errors": 0, "failed_ids": []}

        mock_manager.ingest.side_effect = side_effect

        results = await ingest(
            start_date="2024-01-01",
            end_date="2024-06-01",
            entities=["failing", "succeeding"],
        )

        assert "error" in results["failing"]
        assert results["succeeding"]["upserted"] == 3
