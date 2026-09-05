from unittest.mock import patch

import pytest

from civic_lantern.jobs.ingestors.inside_totals_by_candidate import (
    KNOWN_COMMITTEE_OVERRIDES,
    InsideTotalsByCandidateIngestor,
)
from civic_lantern.services.data.inside_totals_by_candidate import (
    InsideTotalsByCandidateService,
)


@pytest.mark.unit
@pytest.mark.asyncio
class TestInsideTotalsByCandidateIngestor:
    async def test_fetch_calls_get_candidate_totals(self, mock_client, mock_session):
        """fetch() delegates to client.get_candidate_totals with correct cycle."""
        mock_client.get_candidate_totals.return_value = [
            {"candidate_id": "P001", "cycle": 2024}
        ]
        mock_client.get_committee_totals.return_value = []

        ingestor = InsideTotalsByCandidateIngestor(
            client=mock_client, session=mock_session
        )
        result = await ingestor.fetch(cycle=2024)

        mock_client.get_candidate_totals.assert_awaited_once_with(cycle=2024)
        assert {"candidate_id": "P001", "cycle": 2024} in result

    async def test_fetch_merges_known_committee_overrides(
        self, mock_client, mock_session
    ):
        """For a cycle with a known override, fetch() patches in a synthetic
        row from that committee's own totals alongside the normal result."""
        mock_client.get_candidate_totals.return_value = []
        mock_client.get_committee_totals.return_value = [
            {"receipts": 495853270.30, "disbursements": 471501651.83}
        ]

        ingestor = InsideTotalsByCandidateIngestor(
            client=mock_client, session=mock_session
        )
        (candidate_id, cycle), committee_ids = next(
            iter(KNOWN_COMMITTEE_OVERRIDES.items())
        )

        result = await ingestor.fetch(cycle=cycle)

        mock_client.get_committee_totals.assert_awaited_once_with(
            committee_ids[0], cycle=cycle
        )
        assert {
            "candidate_id": candidate_id,
            "cycle": cycle,
            "receipts": 495853270.30,
            "disbursements": 471501651.83,
        } in result

    async def test_fetch_skips_overrides_for_other_cycles(
        self, mock_client, mock_session
    ):
        """A cycle with no known override doesn't call get_committee_totals."""
        mock_client.get_candidate_totals.return_value = []

        ingestor = InsideTotalsByCandidateIngestor(
            client=mock_client, session=mock_session
        )
        result = await ingestor.fetch(cycle=1900)

        mock_client.get_committee_totals.assert_not_awaited()
        assert result == []

    async def test_fetch_without_cycle_raises_type_error(
        self, mock_client, mock_session
    ):
        """fetch() requires an explicit cycle — no more silent default."""
        ingestor = InsideTotalsByCandidateIngestor(
            client=mock_client, session=mock_session
        )

        with pytest.raises(TypeError):
            await ingestor.fetch()

    async def test_fetch_passes_explicit_cycle(self, mock_client, mock_session):
        """fetch() passes the provided cycle through to the client."""
        mock_client.get_candidate_totals.return_value = []

        ingestor = InsideTotalsByCandidateIngestor(
            client=mock_client, session=mock_session
        )
        await ingestor.fetch(cycle=2022)

        mock_client.get_candidate_totals.assert_awaited_once_with(cycle=2022)

    @patch(
        "civic_lantern.jobs.ingestors.inside_totals_by_candidate.transform_inside_totals_by_candidate",
        autospec=True,
    )
    async def test_transform_delegates_to_transformer(
        self, mock_transform, mock_client, mock_session
    ):
        """transform() delegates to transform_inside_totals_by_candidate."""
        raw = [{"candidate_id": "P001", "cycle": 2024, "receipts": 100.0}]
        mock_transform.return_value = ["validated"]

        ingestor = InsideTotalsByCandidateIngestor(
            client=mock_client, session=mock_session
        )
        result = ingestor.transform(raw)

        mock_transform.assert_called_once_with(raw)
        assert result == ["validated"]

    async def test_create_service_returns_correct_type(self, mock_client, mock_session):
        """create_service() returns correct service with the ingestor's session."""
        ingestor = InsideTotalsByCandidateIngestor(
            client=mock_client, session=mock_session
        )
        service = ingestor.create_service()

        assert isinstance(service, InsideTotalsByCandidateService)
        assert service.db is mock_session

    async def test_entity_name(self, mock_client, mock_session):
        """entity_name is 'inside_totals_by_candidate'."""
        ingestor = InsideTotalsByCandidateIngestor(
            client=mock_client, session=mock_session
        )
        assert ingestor.entity_name == "inside_totals_by_candidate"

    async def test_registered_in_registry(self, mock_client, mock_session):
        """InsideTotalsByCandidateIngestor is present in the ingestor registry."""
        from civic_lantern.jobs.ingestors import INGESTOR_REGISTRY

        assert "inside_totals_by_candidate" in INGESTOR_REGISTRY
        assert (
            INGESTOR_REGISTRY["inside_totals_by_candidate"]
            is InsideTotalsByCandidateIngestor
        )
