import pytest

from civic_lantern.core.cycles import current_cycle_ceiling
from civic_lantern.db.models.mv_election_spending_summary import (
    MvElectionSpendingSummary,
)
from civic_lantern.main import app
from tests.unit.conftest import scalars_all_result, scalars_first_result

ELECTION_SPENDING_URL = str(app.url_path_for("get_election_spending"))
READY_CYCLES_URL = str(app.url_path_for("get_ready_election_cycles"))


def election_spending_by_cycle_url(cycle: int) -> str:
    return str(app.url_path_for("get_election_spending_by_cycle", cycle=cycle))


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


@pytest.mark.unit
@pytest.mark.asyncio
class TestGetReadyElectionCycles:
    async def test_returns_ready_cycles_newest_first(self, api_client, mock_session):
        mock_session.execute.return_value = scalars_all_result([2026, 2024])

        response = await api_client.get(READY_CYCLES_URL)

        assert response.status_code == 200
        assert response.json() == [2026, 2024]

    async def test_empty_when_no_ready_cycles(self, api_client, mock_session):
        mock_session.execute.return_value = scalars_all_result([])

        response = await api_client.get(READY_CYCLES_URL)

        assert response.status_code == 200
        assert response.json() == []

    async def test_not_shadowed_by_cycle_path_param(self, api_client, mock_session):
        """/cycles must not be captured by the /{cycle} route (no 422)."""
        mock_session.execute.return_value = scalars_all_result([2024])

        response = await api_client.get(READY_CYCLES_URL)

        assert response.status_code == 200
        assert isinstance(response.json(), list)


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
        url = election_spending_by_cycle_url(current_cycle_ceiling() + 2)
        response = await api_client.get(url)
        assert response.status_code == 422

    async def test_max_cycle_is_recomputed_per_request_not_frozen_at_import(
        self, api_client, mock_session, mocker, spending_obj
    ):
        """A newly-active cycle isn't permanently rejected by a long-running
        process that started in an earlier year."""
        mocker.patch(
            "civic_lantern.api.routers.election_spending.current_cycle_ceiling",
            return_value=2028,
        )
        mock_session.execute.return_value = scalars_first_result(spending_obj)

        response = await api_client.get(election_spending_by_cycle_url(2028))

        assert response.status_code == 200
