import pytest
from sqlalchemy.sql import operators

from civic_lantern.db.models.election_spending import MvElectionSpendingSummary
from civic_lantern.services.data.election_spending import ElectionSpendingService
from tests.unit.conftest import scalars_all_result, scalars_first_result


@pytest.fixture
def service(mock_session):
    return ElectionSpendingService(mock_session)


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
class TestGetAllSpending:
    async def test_returns_rows_from_db(self, service, mock_session, spending_obj):
        mock_session.execute.return_value = scalars_all_result([spending_obj])
        result = await service.get_all_spending()
        assert result == [spending_obj]

    async def test_empty_table_returns_empty_list(self, service, mock_session):
        mock_session.execute.return_value = scalars_all_result([])
        result = await service.get_all_spending()
        assert result == []

    async def test_makes_one_db_call(self, service, mock_session):
        mock_session.execute.return_value = scalars_all_result([])
        await service.get_all_spending()
        assert mock_session.execute.call_count == 1

    async def test_orders_by_cycle_descending(self, service, mock_session):
        """Query must sort newest cycle first."""
        mock_session.execute.return_value = scalars_all_result([])
        await service.get_all_spending()

        stmt = mock_session.execute.call_args[0][0]
        order_clause = stmt._order_by_clauses[0]
        assert order_clause.modifier is operators.desc_op
        assert order_clause.element.key == "cycle"


@pytest.mark.unit
@pytest.mark.asyncio
class TestGetSpendingByCycle:
    async def test_returns_row_when_found(self, service, mock_session, spending_obj):
        mock_session.execute.return_value = scalars_first_result(spending_obj)
        result = await service.get_spending_by_cycle(2024)
        assert result is spending_obj

    async def test_returns_none_when_not_found(self, service, mock_session):
        mock_session.execute.return_value = scalars_first_result(None)
        result = await service.get_spending_by_cycle(2024)
        assert result is None

    async def test_makes_one_db_call(self, service, mock_session):
        mock_session.execute.return_value = scalars_first_result(None)
        await service.get_spending_by_cycle(2024)
        assert mock_session.execute.call_count == 1

    async def test_filters_by_cycle(self, service, mock_session):
        """Query must filter on the cycle primary key, not fetch all rows."""
        mock_session.execute.return_value = scalars_first_result(None)
        await service.get_spending_by_cycle(2022)

        stmt = mock_session.execute.call_args[0][0]
        compiled = str(stmt.compile())
        assert "WHERE mv_election_spending_summary.cycle = :cycle_1" in compiled
