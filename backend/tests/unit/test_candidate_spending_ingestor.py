from decimal import Decimal

import pytest

from civic_lantern.jobs.ingestors.spending import SpendingIngestor
from civic_lantern.schemas.spending import CandidateSpendingSchema
from civic_lantern.services.data.spending import CandidateSpendingService

# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
class TestSpendingIngestorFetch:
    """Tests for SpendingIngestor.fetch()."""

    @pytest.fixture
    def ingestor(self, mock_client, mock_session):
        mock_client.get_candidate_totals.return_value = []
        mock_client.get_outside_spending_totals.return_value = []
        return SpendingIngestor(client=mock_client, session=mock_session)

    async def test_fetch_calls_both_endpoints(self, ingestor, mock_client):
        """fetch() calls both inside and outside FEC endpoints concurrently."""
        await ingestor.fetch(cycle=2024)

        mock_client.get_candidate_totals.assert_awaited_once_with(cycle=2024)
        mock_client.get_outside_spending_totals.assert_awaited_once_with(cycle=2024)

    async def test_fetch_returns_structured_dict(self, ingestor, mock_client):
        """fetch() returns dict with cycle, inside, and outside keys."""
        mock_client.get_candidate_totals.return_value = [{"candidate_id": "H1TX00001"}]

        result = await ingestor.fetch(cycle=2024)

        assert result["cycle"] == 2024
        assert result["inside"] == [{"candidate_id": "H1TX00001"}]
        assert result["outside"] == []

    async def test_fetch_default_cycle_is_2024(self, ingestor, mock_client):
        """fetch() defaults to cycle=2024 when not specified."""
        result = await ingestor.fetch()

        assert result["cycle"] == 2024
        mock_client.get_candidate_totals.assert_awaited_once_with(cycle=2024)
        mock_client.get_outside_spending_totals.assert_awaited_once_with(cycle=2024)

    async def test_fetch_passes_explicit_cycle(self, ingestor, mock_client):
        """fetch() passes the provided cycle through to both endpoints."""
        await ingestor.fetch(cycle=2026)

        mock_client.get_candidate_totals.assert_awaited_once_with(cycle=2026)
        mock_client.get_outside_spending_totals.assert_awaited_once_with(cycle=2026)


# ---------------------------------------------------------------------------
# _merge_fec_data
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMergeFecData:
    """Unit tests for SpendingIngestor._merge_fec_data()."""

    @pytest.fixture
    def ingestor(self, mock_client, mock_session):
        return SpendingIngestor(client=mock_client, session=mock_session)

    def test_inside_only_candidate(self, ingestor):
        """Candidate with only inside data gets zero outside values."""
        inside = [
            {
                "candidate_id": "H1TX00001",
                "receipts": "1000.00",
                "disbursements": "800.00",
            }
        ]

        result = ingestor._merge_fec_data(2024, inside, [])

        assert len(result) == 1
        row = result[0]
        assert row["candidate_id"] == "H1TX00001"
        assert row["inside_receipts"] == Decimal("1000.00")
        assert row["inside_disbursements"] == Decimal("800.00")
        assert row["outside_support"] == Decimal(0)
        assert row["outside_oppose"] == Decimal(0)

    def test_outside_only_candidate(self, ingestor):
        """Candidate appearing only in outside data gets zero inside values."""
        outside = [
            {
                "candidate_id": "H1TX00001",
                "support_oppose_indicator": "S",
                "total": "5000.00",
            },
        ]

        result = ingestor._merge_fec_data(2024, [], outside)

        assert len(result) == 1
        row = result[0]
        assert row["outside_support"] == Decimal("5000.00")
        assert row["inside_receipts"] == Decimal(0)
        assert row["inside_disbursements"] == Decimal(0)

    def test_support_and_oppose_split_correctly(self, ingestor):
        """S and O indicators map to separate outside_support and outside_oppose fields."""
        outside = [
            {
                "candidate_id": "H1TX00001",
                "support_oppose_indicator": "S",
                "total": "3000.00",
            },
            {
                "candidate_id": "H1TX00001",
                "support_oppose_indicator": "O",
                "total": "1500.00",
            },
        ]

        result = ingestor._merge_fec_data(2024, [], outside)

        row = result[0]
        assert row["outside_support"] == Decimal("3000.00")
        assert row["outside_oppose"] == Decimal("1500.00")

    def test_accumulates_multiple_outside_rows(self, ingestor):
        """Multiple S rows for the same candidate are summed, not overwritten."""
        outside = [
            {
                "candidate_id": "H1TX00001",
                "support_oppose_indicator": "S",
                "total": "1000.00",
            },
            {
                "candidate_id": "H1TX00001",
                "support_oppose_indicator": "S",
                "total": "2000.00",
            },
        ]

        result = ingestor._merge_fec_data(2024, [], outside)

        assert result[0]["outside_support"] == Decimal("3000.00")

    def test_unknown_indicator_is_ignored(self, ingestor):
        """Outside rows with unrecognised indicator don't modify any outside field."""
        outside = [
            {
                "candidate_id": "H1TX00001",
                "support_oppose_indicator": "X",
                "total": "999.00",
            },
        ]

        result = ingestor._merge_fec_data(2024, [], outside)

        assert result[0]["outside_support"] == Decimal(0)
        assert result[0]["outside_oppose"] == Decimal(0)

    def test_null_amounts_default_to_zero(self, ingestor):
        """None receipts/disbursements/total are treated as zero without crashing."""
        inside = [
            {"candidate_id": "H1TX00001", "receipts": None, "disbursements": None}
        ]
        outside = [
            {
                "candidate_id": "H1TX00001",
                "support_oppose_indicator": "S",
                "total": None,
            },
        ]

        result = ingestor._merge_fec_data(2024, inside, outside)

        row = result[0]
        assert row["inside_receipts"] == Decimal(0)
        assert row["inside_disbursements"] == Decimal(0)
        assert row["outside_support"] == Decimal(0)

    def test_cycle_is_set_on_every_row(self, ingestor):
        """The cycle value is attached to every merged row."""
        inside = [
            {"candidate_id": "H1TX00001", "receipts": "100", "disbursements": "100"}
        ]

        result = ingestor._merge_fec_data(2026, inside, [])

        assert result[0]["cycle"] == 2026

    def test_multiple_candidates_produce_separate_rows(self, ingestor):
        """Rows from different candidates are not merged together."""
        inside = [
            {"candidate_id": "H1TX00001", "receipts": "100", "disbursements": "80"},
            {"candidate_id": "S1TX00002", "receipts": "200", "disbursements": "150"},
        ]

        result = ingestor._merge_fec_data(2024, inside, [])

        ids = {r["candidate_id"] for r in result}
        assert ids == {"H1TX00001", "S1TX00002"}

    def test_empty_inputs_return_empty(self, ingestor):
        """Both empty inside and outside yields an empty result."""
        assert ingestor._merge_fec_data(2024, [], []) == []

    def test_inside_and_outside_merged_for_same_candidate(self, ingestor):
        """A candidate present in both endpoints produces one fully-merged row."""
        inside = [
            {"candidate_id": "H1TX00001", "receipts": "500", "disbursements": "400"}
        ]
        outside = [
            {
                "candidate_id": "H1TX00001",
                "support_oppose_indicator": "S",
                "total": "200",
            },
            {
                "candidate_id": "H1TX00001",
                "support_oppose_indicator": "O",
                "total": "100",
            },
        ]

        result = ingestor._merge_fec_data(2024, inside, outside)

        assert len(result) == 1
        row = result[0]
        assert row["inside_receipts"] == Decimal("500")
        assert row["inside_disbursements"] == Decimal("400")
        assert row["outside_support"] == Decimal("200")
        assert row["outside_oppose"] == Decimal("100")


# ---------------------------------------------------------------------------
# Transform
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
class TestSpendingIngestorTransform:
    """Tests for SpendingIngestor.transform()."""

    @pytest.fixture
    def ingestor(self, mock_client, mock_session):
        return SpendingIngestor(client=mock_client, session=mock_session)

    async def test_transform_returns_validated_schemas(self, ingestor):
        """transform() returns a list of CandidateSpendingSchema instances."""
        raw = {
            "cycle": 2024,
            "inside": [
                {
                    "candidate_id": "H1TX00001",
                    "receipts": "1000",
                    "disbursements": "800",
                }
            ],
            "outside": [],
        }

        result = ingestor.transform(raw)

        assert len(result) == 1
        assert isinstance(result[0], CandidateSpendingSchema)
        assert result[0].candidate_id == "H1TX00001"
        assert result[0].cycle == 2024

    async def test_transform_skips_invalid_records(self, ingestor, mocker):
        """Records that fail Pydantic validation are skipped and a warning is logged."""
        mocker.patch.object(
            ingestor,
            "_merge_fec_data",
            return_value=[
                {
                    "candidate_id": "H1TX00001",
                    "cycle": 2024,
                    "inside_receipts": Decimal("100"),
                    "inside_disbursements": Decimal("80"),
                    "outside_support": Decimal(0),
                    "outside_oppose": Decimal(0),
                },
                {"cycle": 2024},  # missing required candidate_id
            ],
        )
        mock_logger = mocker.patch.object(ingestor, "logger")

        result = ingestor.transform({"cycle": 2024, "inside": [], "outside": []})

        assert len(result) == 1
        assert result[0].candidate_id == "H1TX00001"

        logged_msg = mock_logger.warning.call_args[0][0]
        assert "Skipping invalid record" in logged_msg

    async def test_transform_empty_data_returns_empty(self, ingestor):
        """Empty inside and outside produces an empty result list."""
        result = ingestor.transform({"cycle": 2024, "inside": [], "outside": []})

        assert result == []

    async def test_transform_computed_fields_are_populated(self, ingestor):
        """influence_ratio and vulnerability_factor are computed on transformed schemas."""
        raw = {
            "cycle": 2024,
            "inside": [
                {
                    "candidate_id": "H1TX00001",
                    "receipts": "1000",
                    "disbursements": "100",
                }
            ],
            "outside": [
                {
                    "candidate_id": "H1TX00001",
                    "support_oppose_indicator": "S",
                    "total": "100",
                },
                {
                    "candidate_id": "H1TX00001",
                    "support_oppose_indicator": "O",
                    "total": "100",
                },
            ],
        }

        result = ingestor.transform(raw)

        schema = result[0]
        assert schema.influence_ratio == Decimal("2.00")
        assert schema.vulnerability_factor == Decimal("1.00")


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
class TestSpendingIngestorWiring:
    """Tests for entity name, service creation, and registry presence."""

    @pytest.fixture
    def ingestor(self, mock_client, mock_session):
        return SpendingIngestor(client=mock_client, session=mock_session)

    async def test_entity_name(self, ingestor):
        """entity_name is 'spending_totals'."""
        assert ingestor.entity_name == "spending_totals"

    async def test_create_service_returns_spending_service(
        self, ingestor, mock_session
    ):
        """create_service() returns a CandidateSpendingService bound to the session."""
        service = ingestor.create_service()

        assert isinstance(service, CandidateSpendingService)
        assert service.db is mock_session

    async def test_create_service_index_elements(self, ingestor):
        """CandidateSpendingService uses (candidate_id, cycle) as the conflict target."""
        service = ingestor.create_service()

        assert service.index_elements == ["candidate_id", "cycle"]

    async def test_spending_totals_registered_in_registry(self, ingestor):
        """spending_totals is present in the ingestor registry."""
        from civic_lantern.jobs.ingestors import INGESTOR_REGISTRY

        assert "spending_totals" in INGESTOR_REGISTRY
        assert INGESTOR_REGISTRY["spending_totals"] is SpendingIngestor
