from unittest.mock import patch

import pytest

from civic_lantern.jobs.ingestors.schedule_e_totals_by_candidate import (
    ScheduleETotalsByCandidateIngestor,
)
from civic_lantern.services.data.schedule_e_totals_by_candidate import (
    ScheduleETotalsByCandidateService,
)


@pytest.mark.unit
@pytest.mark.asyncio
class TestScheduleETotalsByCandidateIngestor:
    async def test_fetch_calls_get_outside_spending_totals(
        self, mock_client, mock_session
    ):
        """fetch() delegates to client.get_outside_spending_totals with correct cycle."""
        mock_client.get_outside_spending_totals.return_value = [
            {
                "candidate_id": "P001",
                "cycle": 2024,
                "support_oppose_indicator": "S",
                "total": 1000.0,
            }
        ]

        ingestor = ScheduleETotalsByCandidateIngestor(
            client=mock_client, session=mock_session
        )
        result = await ingestor.fetch(cycle=2024)

        mock_client.get_outside_spending_totals.assert_awaited_once_with(cycle=2024)
        assert len(result) == 1

    async def test_fetch_strips_date_kwargs(self, mock_client, mock_session):
        """fetch() removes start_date/end_date before passing kwargs to client."""
        mock_client.get_outside_spending_totals.return_value = []

        ingestor = ScheduleETotalsByCandidateIngestor(
            client=mock_client, session=mock_session
        )
        await ingestor.fetch(cycle=2024, start_date="2024-01-01", end_date="2024-12-31")

        mock_client.get_outside_spending_totals.assert_awaited_once_with(cycle=2024)

    async def test_fetch_default_cycle_is_2024(self, mock_client, mock_session):
        mock_client.get_outside_spending_totals.return_value = []

        ingestor = ScheduleETotalsByCandidateIngestor(
            client=mock_client, session=mock_session
        )
        await ingestor.fetch()

        mock_client.get_outside_spending_totals.assert_awaited_once_with(cycle=2024)

    @patch(
        "civic_lantern.jobs.ingestors.schedule_e_totals_by_candidate"
        ".transform_schedule_e_totals_by_candidate",
        autospec=True,
    )
    async def test_transform_delegates_to_transformer(
        self, mock_transform, mock_client, mock_session
    ):
        raw = [{"candidate_id": "P001", "cycle": 2024}]
        mock_transform.return_value = ["validated"]

        ingestor = ScheduleETotalsByCandidateIngestor(
            client=mock_client, session=mock_session
        )
        result = ingestor.transform(raw)

        mock_transform.assert_called_once_with(raw)
        assert result == ["validated"]

    async def test_create_service_returns_correct_type(self, mock_client, mock_session):
        ingestor = ScheduleETotalsByCandidateIngestor(
            client=mock_client, session=mock_session
        )
        service = ingestor.create_service()

        assert isinstance(service, ScheduleETotalsByCandidateService)
        assert service.db is mock_session

    async def test_entity_name(self, mock_client, mock_session):
        ingestor = ScheduleETotalsByCandidateIngestor(
            client=mock_client, session=mock_session
        )
        assert ingestor.entity_name == "schedule_e_totals_by_candidate"

    async def test_registered_in_registry(self, mock_client, mock_session):
        from civic_lantern.jobs.ingestors import INGESTOR_REGISTRY

        assert "schedule_e_totals_by_candidate" in INGESTOR_REGISTRY
        assert (
            INGESTOR_REGISTRY["schedule_e_totals_by_candidate"]
            is ScheduleETotalsByCandidateIngestor
        )
