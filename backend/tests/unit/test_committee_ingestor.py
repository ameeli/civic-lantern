from unittest.mock import patch

import pytest

from civic_lantern.jobs.ingestors.committees import CommitteeIngestor
from civic_lantern.services.data.committee import CommitteeService


@pytest.mark.unit
@pytest.mark.asyncio
class TestCommitteeIngestor:
    """Test CommitteeIngestor wiring to client, transformer, and service."""

    async def test_fetch_calls_get_committees(self, mock_client, mock_session):
        """fetch() delegates to client.get_committees with correct FEC params."""
        mock_client.get_committees.return_value = [{"committee_id": "C001"}]

        ingestor = CommitteeIngestor(client=mock_client, session=mock_session)
        result = await ingestor.fetch("2024-01-01", "2024-06-01", committee_type="O")

        mock_client.get_committees.assert_awaited_once_with(
            min_first_file_date="2024-01-01",
            max_first_file_date="2024-06-01",
            committee_type="O",
        )
        assert result == [{"committee_id": "C001"}]

    async def test_fetch_without_dates_omits_date_params(self, mock_client, mock_session):
        """fetch() without dates passes no date filters to get_committees."""
        mock_client.get_committees.return_value = []

        ingestor = CommitteeIngestor(client=mock_client, session=mock_session)
        await ingestor.fetch()

        mock_client.get_committees.assert_awaited_once_with()

    @patch(
        "civic_lantern.jobs.ingestors.committees.transform_committees", autospec=True
    )
    async def test_transform_delegates_to_transform_committees(
        self, mock_transform, mock_client, mock_session
    ):
        """transform() calls the transform_committees utility."""
        raw = [{"committee_id": "C001", "name": "TEST PAC", "committee_type": "O"}]
        mock_transform.return_value = ["validated"]

        ingestor = CommitteeIngestor(client=mock_client, session=mock_session)
        result = ingestor.transform(raw)

        mock_transform.assert_called_once_with(raw)
        assert result == ["validated"]

    async def test_create_service_returns_committee_service(
        self, mock_client, mock_session
    ):
        """create_service() returns a CommitteeService with the ingestor's session."""
        ingestor = CommitteeIngestor(client=mock_client, session=mock_session)

        service = ingestor.create_service()

        assert isinstance(service, CommitteeService)
        assert service.db is mock_session

    async def test_entity_name(self, mock_client, mock_session):
        """entity_name is 'committees'."""
        ingestor = CommitteeIngestor(client=mock_client, session=mock_session)
        assert ingestor.entity_name == "committees"
