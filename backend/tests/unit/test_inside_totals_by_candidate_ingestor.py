from unittest.mock import patch

import pytest

from civic_lantern.jobs.ingestors.inside_totals_by_candidate import (
    CANDIDATE_TOTALS,
    InsideTotalsByCandidateIngestor,
)
from civic_lantern.services.committee_corrections import (
    COMMITTEE_TOTALS,
    CommitteeCorrections,
    CommitteeOverride,
)
from civic_lantern.services.data.inside_totals_by_candidate import (
    InsideTotalsByCandidateService,
)


def _ingestor(mock_client, mock_session, corrections=None):
    ingestor = InsideTotalsByCandidateIngestor(client=mock_client, session=mock_session)
    ingestor.corrections = corrections or CommitteeCorrections(overrides=(), splits=())
    return ingestor


@pytest.mark.unit
@pytest.mark.asyncio
class TestInsideTotalsByCandidateIngestor:
    async def test_fetch_requests_candidate_totals_endpoint(
        self, mock_client, mock_session
    ):
        """fetch() requests the candidate totals endpoint for the cycle."""
        mock_client.fetch_all.return_value = [{"candidate_id": "P001", "cycle": 2022}]

        result = await _ingestor(mock_client, mock_session).fetch(cycle=2022)

        mock_client.fetch_all.assert_awaited_once_with(CANDIDATE_TOTALS, cycle=2022)
        assert result == [{"candidate_id": "P001", "cycle": 2022}]

    async def test_fetch_applies_committee_corrections(self, mock_client, mock_session):
        """fetch() returns FEC's rows with the cycle's corrections applied."""
        responses = {
            CANDIDATE_TOTALS: [
                {"candidate_id": "P001", "cycle": 2024, "receipts": 100}
            ],
            COMMITTEE_TOTALS: [{"receipts": 50}],
        }
        mock_client.fetch_all.side_effect = lambda endpoint, **_: responses[endpoint]
        corrections = CommitteeCorrections(
            overrides=(CommitteeOverride("P001", 2024, "C001"),), splits=()
        )

        result = await _ingestor(mock_client, mock_session, corrections).fetch(
            cycle=2024
        )

        mock_client.fetch_all.assert_any_await(
            COMMITTEE_TOTALS, committee_id="C001", cycle=2024
        )
        assert result == [
            {"candidate_id": "P001", "cycle": 2024, "receipts": 100},
            {
                "candidate_id": "P001",
                "cycle": 2024,
                "receipts": 50,
                "disbursements": None,
            },
        ]

    async def test_uses_known_corrections_by_default(self, mock_client, mock_session):
        ingestor = InsideTotalsByCandidateIngestor(
            client=mock_client, session=mock_session
        )

        assert ingestor.corrections.overrides and ingestor.corrections.splits

    async def test_fetch_without_cycle_raises_type_error(
        self, mock_client, mock_session
    ):
        """fetch() requires an explicit cycle — no more silent default."""
        with pytest.raises(TypeError):
            await _ingestor(mock_client, mock_session).fetch()

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
