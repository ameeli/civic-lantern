import pytest

from civic_lantern.api.routers.election_spending import _MAX_CYCLE
from civic_lantern.db.models.election_spending import MvElectionSpendingSummary
from civic_lantern.main import app
from tests.unit.conftest import scalars_all_result, scalars_first_result

# ---------------------------------------------------------------------------
# Route URL helpers
# ---------------------------------------------------------------------------

ELECTION_SPENDING_URL = str(app.url_path_for("get_election_spending"))


def election_spending_by_cycle_url(cycle: int) -> str:
    return str(app.url_path_for("get_election_spending_by_cycle", cycle=cycle))


# ---------------------------------------------------------------------------
# Shared data
# ---------------------------------------------------------------------------

@pytest.fixture
def spending_obj():
    return MvElectionSpendingSummary(
        cycle=2024,
        candidate_count=5,
        total_inside_receipts=None,
        total_inside_disbursements=None,
        total_outside_support=None,
        total_outside_oppose=None,
        global_influence_ratio=None,
    )


# ---------------------------------------------------------------------------
# GET /elections/spending
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
class TestGetElectionSpending:
    async def test_returns_list_of_rows(self, api_client, mock_session, spending_obj):
        mock_session.execute.return_value = scalars_all_result([spending_obj])
        response = await api_client.get(ELECTION_SPENDING_URL)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert data[0]["cycle"] == 2024

    async def test_empty_result_returns_empty_list(self, api_client, mock_session):
        mock_session.execute.return_value = scalars_all_result([])
        response = await api_client.get(ELECTION_SPENDING_URL)
        assert response.status_code == 200
        assert response.json() == []


# ---------------------------------------------------------------------------
# GET /elections/spending/{cycle}
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
class TestGetElectionSpendingByCycle:
    async def test_returns_matching_row(self, api_client, mock_session, spending_obj):
        mock_session.execute.return_value = scalars_first_result(spending_obj)
        response = await api_client.get(election_spending_by_cycle_url(2024))
        assert response.status_code == 200
        assert response.json()["cycle"] == 2024

    async def test_odd_cycle_returns_422(self, api_client, mock_session):
        response = await api_client.get(election_spending_by_cycle_url(2023))
        assert response.status_code == 422
        assert "even" in response.json()["detail"].lower()

    async def test_no_data_for_cycle_returns_404(self, api_client, mock_session):
        mock_session.execute.return_value = scalars_first_result(None)
        response = await api_client.get(election_spending_by_cycle_url(2024))
        assert response.status_code == 404

    async def test_cycle_below_minimum_returns_422(self, api_client, mock_session):
        response = await api_client.get(election_spending_by_cycle_url(1978))
        assert response.status_code == 422

    async def test_cycle_above_max_returns_422(self, api_client, mock_session):
        response = await api_client.get(election_spending_by_cycle_url(_MAX_CYCLE + 2))
        assert response.status_code == 422

