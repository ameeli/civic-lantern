import pytest

from civic_lantern.db.models.candidate import Candidate
from civic_lantern.db.models.candidate_spending import CandidateSpendingTotals
from civic_lantern.main import app
from tests.unit.conftest import scalar_result, scalars_all_result, scalars_first_result

# ---------------------------------------------------------------------------
# Route URL helpers
# ---------------------------------------------------------------------------

SPENDING_LIST_URL = str(app.url_path_for("list_candidate_spending"))
CANDIDATES_URL = str(app.url_path_for("list_candidates"))


def candidate_url(candidate_id: str) -> str:
    return str(app.url_path_for("get_candidate", candidate_id=candidate_id))


def candidate_spending_url(candidate_id: str) -> str:
    return str(app.url_path_for("get_candidate_spending", candidate_id=candidate_id))


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def candidate():
    return Candidate(candidate_id="C001", name="Test Candidate")


@pytest.fixture
def spending(candidate):
    s = CandidateSpendingTotals(candidate_id="C001", cycle=2024)
    s.candidate = candidate
    return s


# ---------------------------------------------------------------------------
# GET /candidates/spending
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
class TestListCandidateSpending:
    async def test_returns_paginated_shape(self, api_client, mock_session, spending):
        mock_session.execute.side_effect = [
            scalar_result(1),
            scalars_all_result([spending]),
        ]
        response = await api_client.get(SPENDING_LIST_URL)
        assert response.status_code == 200
        body = response.json()
        assert set(body) == {"items", "total_count", "limit", "offset"}
        assert body["total_count"] == 1
        assert len(body["items"]) == 1

    async def test_pagination_params_reflected_in_response(
        self, api_client, mock_session
    ):
        mock_session.execute.side_effect = [scalar_result(20), scalars_all_result([])]
        response = await api_client.get(f"{SPENDING_LIST_URL}?limit=10&offset=5")
        body = response.json()
        assert body["limit"] == 10
        assert body["offset"] == 5
        assert body["total_count"] == 20

    @pytest.mark.parametrize("limit", [0, 1001])
    async def test_limit_out_of_range_rejected(self, api_client, mock_session, limit):
        response = await api_client.get(f"{SPENDING_LIST_URL}?limit={limit}")
        assert response.status_code == 422

    async def test_negative_offset_rejected(self, api_client, mock_session):
        response = await api_client.get(f"{SPENDING_LIST_URL}?offset=-1")
        assert response.status_code == 422

    async def test_invalid_sort_by_rejected(self, api_client, mock_session):
        response = await api_client.get(f"{SPENDING_LIST_URL}?sort_by=invalid")
        assert response.status_code == 422

    @pytest.mark.parametrize(
        "sort_by",
        [
            "cycle",
            "inside_receipts",
            "inside_disbursements",
            "outside_support",
            "outside_oppose",
            "outside_total",
            "influence_ratio",
            "vulnerability_factor",
        ],
    )
    async def test_all_sort_by_values_accepted(self, api_client, mock_session, sort_by):
        mock_session.execute.side_effect = [scalar_result(0), scalars_all_result([])]
        response = await api_client.get(f"{SPENDING_LIST_URL}?sort_by={sort_by}")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# GET /candidates/{candidate_id}/spending
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
class TestGetCandidateSpending:
    async def test_returns_spending_list(
        self, api_client, mock_session, candidate, spending
    ):
        mock_session.execute.side_effect = [
            scalars_first_result(candidate),
            scalars_all_result([spending]),
        ]
        response = await api_client.get(candidate_spending_url("C001"))
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        assert len(response.json()) == 1

    async def test_unknown_candidate_returns_404(self, api_client, mock_session):
        mock_session.execute.side_effect = [scalars_first_result(None)]
        response = await api_client.get(candidate_spending_url("UNKNOWN"))
        assert response.status_code == 404

    async def test_candidate_with_no_spending_returns_empty_list(
        self, api_client, mock_session, candidate
    ):
        """Candidate exists but has no spending rows → 200 [], not 404."""
        mock_session.execute.side_effect = [
            scalars_first_result(candidate),
            scalars_all_result([]),
        ]
        response = await api_client.get(candidate_spending_url("C001"))
        assert response.status_code == 200
        assert response.json() == []

    async def test_existence_checked_before_spending_query(
        self, api_client, mock_session
    ):
        """On missing candidate, only one DB call is made (no spending query)."""
        mock_session.execute.side_effect = [scalars_first_result(None)]
        await api_client.get(candidate_spending_url("UNKNOWN"))
        assert mock_session.execute.call_count == 1


# ---------------------------------------------------------------------------
# GET /candidates
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
class TestListCandidates:
    async def test_returns_candidate_list_shape(
        self, api_client, mock_session, candidate
    ):
        mock_session.execute.side_effect = [
            scalar_result(1),
            scalars_all_result([candidate]),
        ]
        response = await api_client.get(CANDIDATES_URL)
        assert response.status_code == 200
        body = response.json()
        assert set(body) == {"items", "total_count", "limit", "offset"}
        assert body["total_count"] == 1

    @pytest.mark.parametrize("state", ["X", "XYZ"])
    async def test_state_must_be_two_chars(self, api_client, mock_session, state):
        response = await api_client.get(f"{CANDIDATES_URL}?state={state}")
        assert response.status_code == 422

    async def test_lowercase_state_accepted(self, api_client, mock_session):
        """Route uppercases state before passing to service — lowercase must not 422."""
        mock_session.execute.side_effect = [scalar_result(0), scalars_all_result([])]
        await api_client.get(f"{CANDIDATES_URL}?state=ca")

        executed_stmt = mock_session.execute.call_args[0][0]
        assert "CA" in str(
            executed_stmt.compile(compile_kwargs={"literal_binds": True})
        )

    async def test_invalid_sort_by_rejected(self, api_client, mock_session):
        response = await api_client.get(f"{CANDIDATES_URL}?sort_by=invalid")
        assert response.status_code == 422

    async def test_invalid_order_rejected(self, api_client, mock_session):
        response = await api_client.get(f"{CANDIDATES_URL}?order=sideways")
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /candidates/{candidate_id}
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
class TestGetCandidate:
    async def test_returns_candidate(self, api_client, mock_session, candidate):
        mock_session.execute.return_value = scalars_first_result(candidate)
        response = await api_client.get(candidate_url("C001"))
        assert response.status_code == 200
        assert response.json()["candidate_id"] == "C001"
        assert response.json()["name"] == "Test Candidate"

    async def test_unknown_candidate_returns_404(self, api_client, mock_session):
        mock_session.execute.return_value = scalars_first_result(None)
        response = await api_client.get(candidate_url("UNKNOWN"))
        assert response.status_code == 404
