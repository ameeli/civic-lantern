from unittest.mock import AsyncMock, patch

import pytest

from civic_lantern.jobs.ingestors.candidates import CandidateIngestor
from civic_lantern.services.data.candidate import CandidateService


@pytest.mark.unit
@pytest.mark.asyncio
class TestCandidateIngestor:
    """Test CandidateIngestor wiring to client, transformer, and service."""

    async def test_fetch_calls_get_candidates(self):
        """fetch() delegates to client.get_candidates with correct FEC params."""
        mock_client = AsyncMock()
        mock_client.get_candidates.return_value = [{"candidate_id": "C001"}]

        ingestor = CandidateIngestor(client=mock_client, session=AsyncMock())
        result = await ingestor.fetch(
            "2024-01-01", "2024-06-01", election_year=2024
        )

        mock_client.get_candidates.assert_awaited_once_with(
            min_first_file_date="2024-01-01",
            max_first_file_date="2024-06-01",
            election_year=2024,
        )
        assert result == [{"candidate_id": "C001"}]

    @patch(
        "civic_lantern.jobs.ingestors.candidates.transform_candidates", autospec=True
    )
    async def test_transform_delegates_to_transform_candidates(self, mock_transform):
        """transform() calls the transform_candidates utility."""
        raw = [{"candidate_id": "C001", "name": "SMITH, JOHN"}]
        mock_transform.return_value = ["validated"]

        ingestor = CandidateIngestor(client=AsyncMock(), session=AsyncMock())
        result = ingestor.transform(raw)

        mock_transform.assert_called_once_with(raw)
        assert result == ["validated"]

    async def test_create_service_returns_candidate_service(self):
        """create_service() returns a CandidateService with the ingestor's session."""
        mock_session = AsyncMock()
        ingestor = CandidateIngestor(client=AsyncMock(), session=mock_session)

        service = ingestor.create_service()

        assert isinstance(service, CandidateService)
        assert service.db is mock_session

    async def test_entity_name(self):
        """entity_name is 'candidates'."""
        ingestor = CandidateIngestor(client=AsyncMock(), session=AsyncMock())
        assert ingestor.entity_name == "candidates"
