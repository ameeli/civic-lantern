from unittest.mock import AsyncMock, patch

import pytest

from civic_lantern.jobs.manager import IngestionManager


@pytest.mark.unit
@pytest.mark.asyncio
class TestIngestionManager:
    """Test the IngestionManager routing, lifecycle, and failure handling."""

    @patch("civic_lantern.jobs.manager.AsyncSessionLocal")
    async def test_ingest_routes_to_correct_ingestor(self, MockSession):
        """ingest() looks up the entity in the registry and runs it."""
        mock_run = AsyncMock(return_value={"upserted": 1, "errors": 0})

        class StubIngestor:
            def __init__(self, **kwargs):
                pass

            run = mock_run

        mock_session = AsyncMock()
        MockSession.return_value.__aenter__.return_value = mock_session

        manager = IngestionManager()
        manager._client = AsyncMock()

        registry = {"alpha": StubIngestor}
        with patch(
            "civic_lantern.jobs.manager.INGESTOR_REGISTRY",
            new=registry,
        ):
            result = await manager.ingest("alpha", start_date="2024-01-01")

        assert result == {"upserted": 1, "errors": 0}
        mock_run.assert_awaited_once()

    async def test_ingest_unknown_entity_raises(self):
        """ingest() raises ValueError for unregistered entity names."""
        manager = IngestionManager()
        manager._client = AsyncMock()

        with pytest.raises(ValueError, match="Unknown entity: 'nonexistent'"):
            await manager.ingest("nonexistent")

    @patch("civic_lantern.jobs.manager.FECClient")
    async def test_context_manager_creates_and_closes_client(self, MockFECClient):
        """Entering creates FECClient; exiting closes it."""
        mock_client = AsyncMock()
        MockFECClient.return_value = mock_client

        async with IngestionManager() as manager:
            assert manager._client is mock_client
            mock_client.__aenter__.assert_awaited_once()

        mock_client.__aexit__.assert_awaited_once()

    @patch("civic_lantern.jobs.manager.AsyncSessionLocal")
    async def test_ingest_batch_runs_in_order(self, MockSession):
        """ingest_batch() runs all ingestors in registry order."""
        call_order = []

        class FakeIngestorA:
            def __init__(self, **kwargs):
                pass

            async def run(self, *args, **kwargs):
                call_order.append("a")
                return {"upserted": 1, "errors": 0}

        class FakeIngestorB:
            def __init__(self, **kwargs):
                pass

            async def run(self, *args, **kwargs):
                call_order.append("b")
                return {"upserted": 2, "errors": 0}

        mock_session = AsyncMock()
        MockSession.return_value.__aenter__.return_value = mock_session

        manager = IngestionManager()
        manager._client = AsyncMock()

        registry = {"entity_a": FakeIngestorA, "entity_b": FakeIngestorB}
        with patch("civic_lantern.jobs.manager.INGESTOR_REGISTRY", new=registry):
            results = await manager.ingest_batch()

        assert call_order == ["a", "b"]
        assert "entity_a" in results
        assert "entity_b" in results

    @patch("civic_lantern.jobs.manager.AsyncSessionLocal")
    async def test_ingest_batch_continues_on_failure(self, MockSession):
        """A failed entity is recorded but doesn't block subsequent ones."""

        class FailingIngestor:
            def __init__(self, **kwargs):
                pass

            async def run(self, *args, **kwargs):
                raise RuntimeError("FEC API down")

        class SucceedingIngestor:
            def __init__(self, **kwargs):
                pass

            async def run(self, *args, **kwargs):
                return {"upserted": 5, "errors": 0, "failed_ids": []}

        mock_session = AsyncMock()
        MockSession.return_value.__aenter__.return_value = mock_session

        manager = IngestionManager()
        manager._client = AsyncMock()

        registry = {"failing": FailingIngestor, "succeeding": SucceedingIngestor}
        with patch("civic_lantern.jobs.manager.INGESTOR_REGISTRY", new=registry):
            results = await manager.ingest_batch()

        assert "error" in results["failing"]
        assert results["succeeding"]["upserted"] == 5
