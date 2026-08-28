from unittest.mock import AsyncMock, patch

import pytest

from civic_lantern.jobs.ingestors.candidates import CandidateIngestor
from civic_lantern.services.data.candidate import CandidateService


@pytest.mark.unit
@pytest.mark.asyncio
class TestCandidateIngestor:
    """Test CandidateIngestor wiring to client, transformer, and service."""

    async def test_fetch_calls_get_candidates(self, mock_client, mock_session):
        """fetch() delegates to client.get_candidates with correct FEC params."""
        mock_client.get_candidates.return_value = [{"candidate_id": "C001"}]

        ingestor = CandidateIngestor(client=mock_client, session=mock_session)
        result = await ingestor.fetch("2024-01-01", "2024-06-01", election_year=2024)

        mock_client.get_candidates.assert_awaited_once_with(
            min_first_file_date="2024-01-01",
            max_first_file_date="2024-06-01",
            election_year=2024,
        )
        assert result == [{"candidate_id": "C001"}]

    @patch("civic_lantern.jobs.base_ingestor.IngestionRunService", autospec=True)
    async def test_fetch_without_dates_and_no_watermark_omits_min_date(
        self, MockRunService, mock_client, mock_session
    ):
        """No prior run → full historical pull, no min_first_file_date filter."""
        MockRunService.return_value.get_watermark = AsyncMock(return_value=None)
        mock_client.get_candidates.return_value = []

        ingestor = CandidateIngestor(client=mock_client, session=mock_session)
        await ingestor.fetch()

        _, kwargs = mock_client.get_candidates.call_args
        assert "min_first_file_date" not in kwargs
        assert "max_first_file_date" in kwargs

    @patch(
        "civic_lantern.jobs.ingestors.candidates.transform_candidates", autospec=True
    )
    async def test_transform_delegates_to_transform_candidates(
        self, mock_transform, mock_client, mock_session
    ):
        """transform() calls the transform_candidates utility."""
        raw = [{"candidate_id": "C001", "name": "SMITH, JOHN"}]
        mock_transform.return_value = ["validated"]

        ingestor = CandidateIngestor(client=mock_client, session=mock_session)
        result = ingestor.transform(raw)

        mock_transform.assert_called_once_with(raw)
        assert result == ["validated"]

    async def test_create_service_returns_candidate_service(
        self, mock_client, mock_session
    ):
        """create_service() returns a CandidateService with the ingestor's session."""
        ingestor = CandidateIngestor(client=mock_client, session=mock_session)

        service = ingestor.create_service()

        assert isinstance(service, CandidateService)
        assert service.db is mock_session

    async def test_entity_name(self, mock_client, mock_session):
        """entity_name is 'candidates'."""
        ingestor = CandidateIngestor(client=mock_client, session=mock_session)
        assert ingestor.entity_name == "candidates"
