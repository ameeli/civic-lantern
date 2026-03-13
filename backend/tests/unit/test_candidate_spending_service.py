import operator

import pytest
from sqlalchemy import select
from sqlalchemy.sql import operators
from sqlalchemy.sql.expression import BinaryExpression

from civic_lantern.db.models.candidate_spending import CandidateSpendingTotals
from civic_lantern.services.data.candidate_spending import CandidateSpendingService
from tests.unit.conftest import scalar_result, scalars_all_result


@pytest.fixture
def service(mock_session):
    return CandidateSpendingService(mock_session)


@pytest.fixture
def base_stmt():
    return select(CandidateSpendingTotals)


@pytest.mark.unit
class TestApplySorting:
    def test_outside_total_sorts_by_sum_expression(self, service, base_stmt):
        """outside_total must ORDER BY support+oppose, not either column alone."""
        sorted_stmt = service._apply_sorting(base_stmt, "outside_total", "desc")

        primary_sort = sorted_stmt._order_by_clauses[0]

        assert isinstance(primary_sort.element, BinaryExpression)
        assert primary_sort.element.operator is operator.add

    def test_non_virtual_sort_has_no_expression(self, service, base_stmt):
        """A plain column sort should not produce a + expression in ORDER BY."""
        sorted_stmt = service._apply_sorting(base_stmt, "cycle", "desc")
        order_section = str(sorted_stmt.compile()).split("ORDER BY")[-1]
        assert "+" not in order_section

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
    def test_always_appends_two_tiebreaker_columns(self, service, base_stmt, sort_by):
        """candidate_id and cycle tiebreakers are always the last two ORDER BY clauses."""
        sorted_stmt = service._apply_sorting(base_stmt, sort_by, "desc")
        assert len(sorted_stmt._order_by_clauses) == 3

    def test_desc_direction(self, service, base_stmt):
        sorted_stmt = service._apply_sorting(base_stmt, "cycle", "desc")
        primary_sort = sorted_stmt._order_by_clauses[0]

        assert primary_sort.modifier is operators.desc_op

    def test_asc_direction(self, service, base_stmt):
        sorted_stmt = service._apply_sorting(base_stmt, "cycle", "asc")
        primary_sort = sorted_stmt._order_by_clauses[0]

        assert primary_sort.modifier is operators.asc_op


@pytest.mark.unit
@pytest.mark.asyncio
class TestGetList:
    async def test_returns_expected_keys(self, service, mock_session):
        mock_session.execute.side_effect = [scalar_result(3), scalars_all_result([])]
        result = await service.get_list()
        assert set(result) == {"items", "total_count", "limit", "offset"}

    async def test_total_count_from_count_query_not_items_length(
        self, service, mock_session
    ):
        """total_count must reflect the full dataset, not the current page length."""
        mock_session.execute.side_effect = [scalar_result(99), scalars_all_result([])]
        result = await service.get_list(limit=10, offset=0)
        assert result["total_count"] == 99
        assert len(result["items"]) == 0

    async def test_makes_two_db_calls(self, service, mock_session):
        """One execute for the count, one for the data — never conflated."""
        mock_session.execute.side_effect = [scalar_result(0), scalars_all_result([])]
        await service.get_list()
        assert mock_session.execute.call_count == 2

    async def test_pagination_params_reflected_in_result(self, service, mock_session):
        mock_session.execute.side_effect = [scalar_result(0), scalars_all_result([])]
        result = await service.get_list(limit=25, offset=50)
        assert result["limit"] == 25
        assert result["offset"] == 50
