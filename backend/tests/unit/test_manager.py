from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import TextClause

from civic_lantern.jobs.ingestors.candidates import CANDIDATES_INGESTION
from civic_lantern.jobs.manager import (
    DATE_WINDOWED_ENTITIES,
    MV_REFRESH_RESULT_KEY,
    OVERLAP_TIMEOUT_MINUTES,
    SPENDING_ENTITIES,
    IngestionManager,
)


@pytest.mark.unit
@pytest.mark.asyncio
class TestIngestionManager:
    """Test the IngestionManager routing, lifecycle, and failure handling."""

    @patch("civic_lantern.jobs.manager.run_ingestion", new_callable=AsyncMock)
    @patch("civic_lantern.jobs.manager.JobSessionLocal")
    async def test_ingest_runs_the_named_declaration(
        self, MockSession, mock_run, manager
    ):
        """ingest() looks up the declaration by name and runs it."""
        session = AsyncMock()
        MockSession.return_value.__aenter__.return_value = session
        mock_run.return_value = {"inserted": 1, "updated": 0, "errors": 0}

        result = await manager.ingest("candidates", start_date="2024-01-01")

        assert result == {"inserted": 1, "updated": 0, "errors": 0}
        mock_run.assert_awaited_once_with(
            CANDIDATES_INGESTION,
            manager._client,
            session,
            cycle=None,
            start_date="2024-01-01",
            end_date=None,
        )

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

    @patch("civic_lantern.jobs.manager.run_ingestion", new_callable=AsyncMock)
    @patch("civic_lantern.jobs.manager.JobSessionLocal")
    async def test_ingest_batch_runs_in_declaration_order(
        self, MockSession, mock_run, manager
    ):
        """ingest_batch() runs the requested entities in INGESTIONS order."""
        MockSession.return_value.__aenter__.return_value = AsyncMock()
        mock_run.return_value = None

        results = await manager.ingest_batch(["candidates", "committees"])

        ran = [c.args[0].entity for c in mock_run.await_args_list]
        assert ran == ["committees", "candidates"]
        assert list(results) == ["committees", "candidates"]

    async def test_ingest_batch_rejects_unknown_entities_before_running(self, manager):
        with pytest.raises(ValueError, match="Unknown entity: 'nope'"):
            await manager.ingest_batch(["candidates", "nope"])

    @patch("civic_lantern.jobs.manager.run_ingestion", new_callable=AsyncMock)
    @patch("civic_lantern.jobs.manager.JobSessionLocal")
    async def test_ingest_batch_continues_on_failure(
        self, MockSession, mock_run, manager
    ):
        """A failed entity is recorded but doesn't block subsequent ones."""
        MockSession.return_value.__aenter__.return_value = AsyncMock()

        async def run(ingestion, *args, **kwargs):
            if ingestion.entity == "committees":
                raise RuntimeError("FEC API down")
            return {"inserted": 5, "updated": 0, "errors": 0, "failed_ids": []}

        mock_run.side_effect = run

        results = await manager.ingest_batch(["committees", "candidates"])

        assert results["committees"] == {"error": "FEC API down"}
        assert results["candidates"]["inserted"] == 5

    @patch("civic_lantern.jobs.manager.JobSessionLocal")
    async def test_refresh_spending_stats_uses_text(self, MockSession, manager):
        """refresh_spending_stats() issues two REFRESH statements via text()."""
        mock_session = AsyncMock()
        MockSession.return_value.__aenter__.return_value = mock_session

        await manager.refresh_spending_stats()

        assert mock_session.execute.await_count == 2
        calls = [str(c.args[0]) for c in mock_session.execute.call_args_list]
        assert any("mv_candidate_spending_summary" in c for c in calls)
        assert any("mv_election_spending_summary" in c for c in calls)
        assert all(
            isinstance(c.args[0], TextClause)
            for c in mock_session.execute.call_args_list
        )

    @patch("civic_lantern.jobs.manager.run_ingestion", new_callable=AsyncMock)
    @patch("civic_lantern.jobs.manager.JobSessionLocal")
    async def test_ingest_batch_refreshes_mv_on_spending_success(
        self, MockSession, mock_run, manager
    ):
        """MV refresh is triggered when a spending source ingestor succeeds."""
        MockSession.return_value.__aenter__.return_value = AsyncMock()
        mock_run.return_value = {"inserted": 1}

        with patch.object(
            manager, "refresh_spending_stats", new_callable=AsyncMock
        ) as mock_refresh:
            await manager.ingest_batch(["inside_totals_by_candidate"], cycle=2024)

        mock_refresh.assert_awaited_once()

    @patch("civic_lantern.jobs.manager.JobSessionLocal")
    async def test_refresh_spending_stats_raises_on_failure(self, MockSession, manager):
        """A failed refresh propagates instead of being swallowed."""
        mock_session = AsyncMock()
        mock_session.execute.side_effect = RuntimeError("lock timeout")
        MockSession.return_value.__aenter__.return_value = mock_session

        with pytest.raises(RuntimeError, match="lock timeout"):
            await manager.refresh_spending_stats()

    @patch("civic_lantern.jobs.manager.run_ingestion", new_callable=AsyncMock)
    @patch("civic_lantern.jobs.manager.JobSessionLocal")
    async def test_ingest_batch_records_mv_refresh_failure(
        self, MockSession, mock_run, manager
    ):
        """A failed refresh is recorded as an error result, so the CLI exits 1."""
        MockSession.return_value.__aenter__.return_value = AsyncMock()
        mock_run.return_value = {"inserted": 1}

        with patch.object(
            manager,
            "refresh_spending_stats",
            new_callable=AsyncMock,
            side_effect=RuntimeError("lock timeout"),
        ):
            results = await manager.ingest_batch(
                ["inside_totals_by_candidate"], cycle=2024
            )

        assert results["inside_totals_by_candidate"] == {"inserted": 1}
        assert results[MV_REFRESH_RESULT_KEY] == {"error": "lock timeout"}

    @patch("civic_lantern.jobs.manager.run_ingestion", new_callable=AsyncMock)
    @patch("civic_lantern.jobs.manager.JobSessionLocal")
    async def test_ingest_batch_skips_mv_refresh_on_spending_failure(
        self, MockSession, mock_run, manager
    ):
        """MV refresh is skipped when all spending source ingestors error."""
        MockSession.return_value.__aenter__.return_value = AsyncMock()
        mock_run.side_effect = RuntimeError("spending fetch failed")

        with patch.object(
            manager, "refresh_spending_stats", new_callable=AsyncMock
        ) as mock_refresh:
            await manager.ingest_batch(["inside_totals_by_candidate"], cycle=2024)

        mock_refresh.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.asyncio
class TestRunNightly:
    """Test the nightly routine: overlap guard, then per-cycle spending loop."""

    @patch("civic_lantern.jobs.manager.JobSessionLocal")
    @patch("civic_lantern.jobs.manager.IngestionRunService", autospec=True)
    async def test_skips_when_overlap_guard_active(
        self, MockRunService, MockSession, manager
    ):
        MockSession.return_value.__aenter__.return_value = AsyncMock()
        MockRunService.return_value.has_active_run = AsyncMock(return_value=True)
        MockRunService.return_value.reset_stale_runs = AsyncMock()

        with patch.object(
            manager, "ingest_batch", new_callable=AsyncMock
        ) as mock_ingest_batch:
            result = await manager.run_nightly()

        assert result == {"skipped": "overlap_guard"}
        mock_ingest_batch.assert_not_awaited()
        MockRunService.return_value.reset_stale_runs.assert_not_awaited()

    @patch("civic_lantern.jobs.manager.JobSessionLocal")
    @patch("civic_lantern.jobs.manager.IngestionRunService", autospec=True)
    async def test_resets_stale_runs_when_no_active_run(
        self, MockRunService, MockSession, manager
    ):
        MockSession.return_value.__aenter__.return_value = AsyncMock()
        MockRunService.return_value.has_active_run = AsyncMock(return_value=False)
        MockRunService.return_value.reset_stale_runs = AsyncMock()

        with patch.object(
            manager, "ingest_batch", new_callable=AsyncMock, return_value={}
        ):
            with patch("civic_lantern.jobs.manager.active_cycles", return_value=[]):
                await manager.run_nightly()

        MockRunService.return_value.reset_stale_runs.assert_awaited_once_with(
            OVERLAP_TIMEOUT_MINUTES
        )

    @patch("civic_lantern.jobs.manager.JobSessionLocal")
    @patch("civic_lantern.jobs.manager.IngestionRunService", autospec=True)
    async def test_runs_date_windowed_once_and_spending_per_active_cycle(
        self, MockRunService, MockSession, manager
    ):
        MockSession.return_value.__aenter__.return_value = AsyncMock()
        MockRunService.return_value.has_active_run = AsyncMock(return_value=False)
        MockRunService.return_value.reset_stale_runs = AsyncMock()

        calls = []

        async def fake_ingest_batch(entities, *args, **kwargs):
            calls.append((entities, kwargs.get("cycle")))
            return {name: {"inserted": 1} for name in entities}

        with patch.object(manager, "ingest_batch", side_effect=fake_ingest_batch):
            with patch(
                "civic_lantern.jobs.manager.active_cycles", return_value=[2024, 2026]
            ):
                result = await manager.run_nightly()

        assert calls[0] == (DATE_WINDOWED_ENTITIES, None)
        assert calls[1] == (SPENDING_ENTITIES, 2024)
        assert calls[2] == (SPENDING_ENTITIES, 2026)

        assert "committees" in result
        assert "inside_totals_by_candidate:2024" in result
        assert "schedule_e_totals_by_candidate:2026" in result

    @patch("civic_lantern.jobs.manager.JobSessionLocal")
    @patch("civic_lantern.jobs.manager.IngestionRunService", autospec=True)
    async def test_refreshes_mv_once_total_not_once_per_cycle(
        self, MockRunService, MockSession, manager
    ):
        """The MVs span every cycle — refresh once per run, not per cycle."""
        MockSession.return_value.__aenter__.return_value = AsyncMock()
        MockRunService.return_value.has_active_run = AsyncMock(return_value=False)
        MockRunService.return_value.reset_stale_runs = AsyncMock()

        async def fake_ingest_batch(entities, *args, **kwargs):
            return {name: {"inserted": 1} for name in entities}

        with patch.object(manager, "ingest_batch", side_effect=fake_ingest_batch):
            with patch(
                "civic_lantern.jobs.manager.active_cycles", return_value=[2024, 2026]
            ):
                with patch.object(
                    manager, "refresh_spending_stats", new_callable=AsyncMock
                ) as mock_refresh:
                    await manager.run_nightly()

        mock_refresh.assert_awaited_once()

    @patch("civic_lantern.jobs.manager.JobSessionLocal")
    @patch("civic_lantern.jobs.manager.IngestionRunService", autospec=True)
    async def test_run_nightly_records_mv_refresh_failure(
        self, MockRunService, MockSession, manager
    ):
        """A failed nightly refresh is recorded as an error, so the CLI exits 1."""
        MockSession.return_value.__aenter__.return_value = AsyncMock()
        MockRunService.return_value.has_active_run = AsyncMock(return_value=False)
        MockRunService.return_value.reset_stale_runs = AsyncMock()

        async def fake_ingest_batch(entities, *args, **kwargs):
            return {name: {"inserted": 1} for name in entities}

        with patch.object(manager, "ingest_batch", side_effect=fake_ingest_batch):
            with patch("civic_lantern.jobs.manager.active_cycles", return_value=[2024]):
                with patch.object(
                    manager,
                    "refresh_spending_stats",
                    new_callable=AsyncMock,
                    side_effect=RuntimeError("lock timeout"),
                ):
                    results = await manager.run_nightly()

        assert results[MV_REFRESH_RESULT_KEY] == {"error": "lock timeout"}

    @patch("civic_lantern.jobs.manager.JobSessionLocal")
    @patch("civic_lantern.jobs.manager.IngestionRunService", autospec=True)
    async def test_skips_mv_refresh_when_no_active_cycles_succeed(
        self, MockRunService, MockSession, manager
    ):
        MockSession.return_value.__aenter__.return_value = AsyncMock()
        MockRunService.return_value.has_active_run = AsyncMock(return_value=False)
        MockRunService.return_value.reset_stale_runs = AsyncMock()

        async def fake_ingest_batch(entities, *args, **kwargs):
            return {name: {"error": "boom"} for name in entities}

        with patch.object(manager, "ingest_batch", side_effect=fake_ingest_batch):
            with patch("civic_lantern.jobs.manager.active_cycles", return_value=[2024]):
                with patch.object(
                    manager, "refresh_spending_stats", new_callable=AsyncMock
                ) as mock_refresh:
                    await manager.run_nightly()

        mock_refresh.assert_not_awaited()
