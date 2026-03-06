from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import TextClause

from civic_lantern.jobs.manager import IngestionManager


@pytest.mark.unit
@pytest.mark.asyncio
class TestIngestionManager:
    """Test the IngestionManager routing, lifecycle, and failure handling."""

    @patch("civic_lantern.jobs.manager.AsyncSessionLocal")
    async def test_ingest_routes_to_correct_ingestor(self, MockSession, manager):
        """ingest() looks up the entity in the registry and runs it."""
        mock_run = AsyncMock(return_value={"inserted": 1, "updated": 0, "errors": 0})

        class StubIngestor:
            def __init__(self, **kwargs):
                pass

            run = mock_run

        MockSession.return_value.__aenter__.return_value = AsyncMock()

        registry = {"alpha": StubIngestor}
        with patch(
            "civic_lantern.jobs.manager.INGESTOR_REGISTRY",
            new=registry,
        ):
            result = await manager.ingest("alpha", start_date="2024-01-01")

        assert result == {"inserted": 1, "updated": 0, "errors": 0}
        mock_run.assert_awaited_once()

    async def test_ingest_unknown_entity_raises(self, manager):
        """ingest() raises ValueError for unregistered entity names."""
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
    async def test_ingest_batch_runs_in_order(self, MockSession, manager):
        """ingest_batch() runs all ingestors in registry order."""
        call_order = []

        class FakeIngestorA:
            def __init__(self, **kwargs):
                pass

            async def run(self, *args, **kwargs):
                call_order.append("a")
                return {"inserted": 1, "updated": 0, "errors": 0}

        class FakeIngestorB:
            def __init__(self, **kwargs):
                pass

            async def run(self, *args, **kwargs):
                call_order.append("b")
                return {"inserted": 2, "updated": 0, "errors": 0}

        MockSession.return_value.__aenter__.return_value = AsyncMock()

        registry = {"entity_a": FakeIngestorA, "entity_b": FakeIngestorB}
        with patch("civic_lantern.jobs.manager.INGESTOR_REGISTRY", new=registry):
            results = await manager.ingest_batch()

        assert call_order == ["a", "b"]
        assert "entity_a" in results
        assert "entity_b" in results

    @patch("civic_lantern.jobs.manager.AsyncSessionLocal")
    async def test_ingest_batch_continues_on_failure(self, MockSession, manager):
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
                return {"inserted": 5, "updated": 0, "errors": 0, "failed_ids": []}

        MockSession.return_value.__aenter__.return_value = AsyncMock()

        registry = {"failing": FailingIngestor, "succeeding": SucceedingIngestor}
        with patch("civic_lantern.jobs.manager.INGESTOR_REGISTRY", new=registry):
            results = await manager.ingest_batch()

        assert "error" in results["failing"]
        assert results["succeeding"]["inserted"] == 5

    @patch("civic_lantern.jobs.manager.AsyncSessionLocal")
    async def test_refresh_spending_stats_uses_text(self, MockSession, manager):
        """refresh_spending_stats() wraps the SQL string in text()."""
        mock_session = AsyncMock()
        MockSession.return_value.__aenter__.return_value = mock_session

        await manager.refresh_spending_stats()

        mock_session.execute.assert_awaited_once()
        call_arg = mock_session.execute.call_args[0][0]
        assert isinstance(call_arg, TextClause)
        assert "mv_election_spending_summary" in str(call_arg)

    @patch("civic_lantern.jobs.manager.AsyncSessionLocal")
    async def test_ingest_batch_refreshes_mv_on_spending_success(
        self, MockSession, manager
    ):
        """MV refresh is triggered when spending_totals ingestion succeeds."""
        mock_ingestor = MagicMock()
        mock_ingestor.return_value.run = AsyncMock(return_value={"inserted": 1})
        registry = {"spending_totals": mock_ingestor}

        with patch("civic_lantern.jobs.manager.INGESTOR_REGISTRY", new=registry):
            with patch.object(
                manager, "refresh_spending_stats", new_callable=AsyncMock
            ) as mock_refresh:
                await manager.ingest_batch()

        mock_refresh.assert_awaited_once()

    @patch("civic_lantern.jobs.manager.AsyncSessionLocal")
    async def test_ingest_batch_skips_mv_refresh_on_spending_failure(
        self, MockSession, manager
    ):
        """MV refresh is skipped when spending_totals ingestion errors."""

        class FailingSpendingIngestor:
            def __init__(self, **kwargs):
                pass

            async def run(self, *args, **kwargs):
                raise RuntimeError("spending fetch failed")

        MockSession.return_value.__aenter__.return_value = AsyncMock()

        registry = {"spending_totals": FailingSpendingIngestor}
        with patch("civic_lantern.jobs.manager.INGESTOR_REGISTRY", new=registry):
            with patch.object(
                manager, "refresh_spending_stats", new_callable=AsyncMock
            ) as mock_refresh:
                await manager.ingest_batch()

        mock_refresh.assert_not_awaited()
