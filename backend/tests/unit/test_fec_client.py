import asyncio
from unittest.mock import ANY, AsyncMock, Mock

import httpx
import pytest
import respx

from civic_lantern.services.fec_exceptions import (
    FECNetworkError,
    FECNotFoundError,
    FECRateLimitError,
    FECServerError,
    FECTimeoutError,
    PartialFetchError,
)


@pytest.mark.unit
@pytest.mark.asyncio
class TestFECClientErrorHandling:
    """Test that HTTP errors map to correct exceptions."""

    async def test_404_raises_not_found_error(self, client):
        """404 should raise FECNotFoundError (non-retryable)."""
        mock_response = Mock()
        mock_response.status_code = 404

        error = httpx.HTTPStatusError(
            "Not found", request=Mock(), response=mock_response
        )

        with pytest.raises(FECNotFoundError) as exc_info:
            client._raise_fec_error(error, url="test", params={})

        assert exc_info.value.retryable is False

    async def test_500_raises_server_error(self, client):
        """5xx should raise FECServerError (retryable)."""
        mock_response = Mock()
        mock_response.status_code = 503

        error = httpx.HTTPStatusError(
            "Service unavailable", request=Mock(), response=mock_response
        )

        with pytest.raises(FECServerError) as exc_info:
            client._raise_fec_error(error, url="test", params={})

        assert exc_info.value.retryable is True

    async def test_get_candidates_raises_rate_limit_error(self, client, mocker):
        """429 is retried — the minute_limiter's window is only 1s wide, so
        fec_retry's 2s-minimum backoff gives it time to reset — but still
        raises FECRateLimitError if it never recovers."""
        mocker.patch("asyncio.sleep")
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Too Many Requests", request=Mock(), response=mock_response
        )
        mock_get = mocker.patch(
            "civic_lantern.services.fec_client.httpx.AsyncClient.get",
            return_value=mock_response,
        )

        with pytest.raises(FECRateLimitError):
            await client.get_candidates(election_year=2024)

        assert mock_get.call_count == 3

    @respx.mock
    async def test_fetch_retries_on_500_error(self, client, mocker):
        """Client should retry 5xx errors."""
        mocker.patch("asyncio.sleep")
        route = respx.get(url__startswith=client.candidate_url).mock(
            side_effect=[
                httpx.Response(500, json={"error": "Server error"}),
                httpx.Response(
                    200,
                    json={
                        "results": [{"candidate_id": "C001", "name": "Test"}],
                        "pagination": {"pages": 1},
                    },
                ),
            ]
        )

        results = await client.get_candidates(election_year=2024)

        assert len(route.calls) == 2
        assert len(results) == 1

    @respx.mock
    async def test_fetch_gives_up_after_retries(self, client, mocker):
        """Should give up after max retries, bypass waiting for backoff."""
        mocker.patch("asyncio.sleep")
        route = respx.get(url__startswith=client.candidate_url).mock(
            return_value=httpx.Response(503, json={"error": "Unavailable"})
        )

        with pytest.raises(FECServerError):
            await client.get_candidates(election_year=2024)

        assert len(route.calls) == 3

    @respx.mock
    async def test_fetch_raises_timeout_error(self, client, mocker):
        """httpx.TimeoutException should raise FECTimeoutError (retryable)."""
        mocker.patch("asyncio.sleep")
        respx.get(url__startswith=client.candidate_url).mock(
            side_effect=httpx.TimeoutException("timed out")
        )

        with pytest.raises(FECTimeoutError) as exc_info:
            await client.get_candidates(election_year=2024)

        assert exc_info.value.retryable is True

    @respx.mock
    async def test_fetch_raises_network_error(self, client, mocker):
        """httpx.NetworkError should raise FECNetworkError (retryable)."""
        mocker.patch("asyncio.sleep")
        respx.get(url__startswith=client.candidate_url).mock(
            side_effect=httpx.NetworkError("connection refused")
        )

        with pytest.raises(FECNetworkError) as exc_info:
            await client.get_candidates(election_year=2024)

        assert exc_info.value.retryable is True


@pytest.mark.unit
@pytest.mark.asyncio
class TestFECClientRequiresExplicitCycle:
    """Spending-totals endpoints no longer silently default to cycle=2024."""

    async def test_get_candidate_totals_without_cycle_raises(self, client):
        with pytest.raises(TypeError):
            await client.get_candidate_totals()

    async def test_get_candidate_schedule_e_totals_without_cycle_raises(self, client):
        with pytest.raises(TypeError):
            await client.get_candidate_schedule_e_totals()

    async def test_get_committee_reports_without_cycle_raises(self, client):
        with pytest.raises(TypeError):
            await client.get_committee_reports("C00703975")


@pytest.mark.unit
@pytest.mark.asyncio
class TestFECClientGetCommitteeReports:
    """get_committee_reports fetches a committee's periodic filed reports."""

    @respx.mock
    async def test_calls_correct_url_and_params(self, client):
        url = client.committee_reports_url_tpl.format(committee_id="C00703975")
        route = respx.get(url__startswith=url).mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "coverage_start_date": "2024-07-01",
                            "coverage_end_date": "2024-07-31",
                            "total_receipts_period": 204488910.82,
                            "total_disbursements_period": 80718189.89,
                            "most_recent": True,
                        }
                    ],
                    "pagination": {"pages": 1},
                },
            )
        )

        results = await client.get_committee_reports("C00703975", cycle=2024)

        assert len(route.calls) == 1
        request_params = route.calls[0].request.url.params
        assert request_params["cycle"] == "2024"
        assert request_params["sort"] == "coverage_start_date"
        assert len(results) == 1
        assert results[0]["total_receipts_period"] == 204488910.82

    @respx.mock
    async def test_returns_raw_rows_including_superseded_amendments(self, client):
        """Filtering by most_recent is the caller's job, not the client's."""
        url = client.committee_reports_url_tpl.format(committee_id="C00703975")
        respx.get(url__startswith=url).mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "coverage_start_date": "2024-07-01",
                            "coverage_end_date": "2024-07-31",
                            "total_receipts_period": 100.0,
                            "most_recent": False,
                        },
                        {
                            "coverage_start_date": "2024-07-01",
                            "coverage_end_date": "2024-07-31",
                            "total_receipts_period": 204488910.82,
                            "most_recent": True,
                        },
                    ],
                    "pagination": {"pages": 1},
                },
            )
        )

        results = await client.get_committee_reports("C00703975", cycle=2024)

        assert len(results) == 2
        assert {r["most_recent"] for r in results} == {True, False}


@pytest.mark.unit
@pytest.mark.asyncio
class TestFECClientRateLimiting:
    """Test that both rate limiters are acquired on every request."""

    @respx.mock
    async def test_both_limiters_acquired_per_request(self, client):
        """Every _fetch_page call must acquire both the hourly and minute limiter."""
        respx.get(url__startswith=client.candidate_url).mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [{"candidate_id": "C001"}],
                    "pagination": {"pages": 1},
                },
            )
        )
        mock_hourly = AsyncMock()
        mock_minute = AsyncMock()
        client.limiter = mock_hourly
        client.minute_limiter = mock_minute

        await client.get_candidates(election_year=2024)

        mock_hourly.__aenter__.assert_awaited_once()
        mock_minute.__aenter__.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.asyncio
class TestFECClientPagination:
    """Test parallel pagination and concurrency control."""

    async def test_safe_fetch_page_respects_semaphore(self, client, mocker):
        """Ensure the worker actually uses the provided semaphore."""
        sem = asyncio.Semaphore(1)
        mock_fetch = mocker.patch.object(client, "_fetch_page", autospec=True)
        mock_fetch.return_value = {"results": []}

        spy_acquire = mocker.spy(sem, "acquire")

        await client._safe_fetch_page("http://test", {}, 1, sem)

        assert spy_acquire.called
        mock_fetch.assert_awaited_once()

    async def test_safe_fetch_page_captures_exception(self, client, mocker):
        """Worker should return an Exception object instead of raising it."""
        sem = asyncio.Semaphore(5)
        mocker.patch.object(
            client, "_fetch_page", side_effect=FECServerError("Boom"), autospec=True
        )

        result = await client._safe_fetch_page("http://test", {}, 1, sem)

        assert isinstance(result, FECServerError)
        assert str(result) == "Boom"

    async def test_paginate_coordinates_multiple_workers(self, client, mocker):
        """Orchestrator should split work between page 1 and the parallel workers."""
        mock_fetch = mocker.patch.object(client, "_fetch_page", autospec=True)
        mock_fetch.return_value = {"results": [{"id": 1}], "pagination": {"pages": 3}}

        mock_safe_fetch = mocker.patch.object(client, "_safe_fetch_page", autospec=True)
        mock_safe_fetch.side_effect = [
            {"results": [{"id": 2}]},
            {"results": [{"id": 3}]},
        ]

        results = await client._paginate("http://test", {})

        assert len(results) == 3
        assert mock_fetch.call_count == 1
        assert mock_safe_fetch.call_count == 2

        mock_safe_fetch.assert_any_call(ANY, ANY, 2, ANY)
        mock_safe_fetch.assert_any_call(ANY, ANY, 3, ANY)

    async def test_paginate_raises_partial_fetch_error_on_failed_pages(
        self, client, mocker
    ):
        """A worker returning an Exception object doesn't get silently
        dropped as a clean result — the orchestrator raises PartialFetchError
        carrying whatever pages did succeed, so callers can't mistake this
        for a complete fetch."""
        mocker.patch.object(
            client,
            "_fetch_page",
            return_value={"results": [{"id": 1}], "pagination": {"pages": 3}},
        )

        async def mock_safe_fetch(url, params, page, sem):
            if page == 2:
                return FECServerError("Fail", status_code=500, response=mocker.Mock())
            return {"results": [{"id": 3}]}

        mocker.patch.object(
            client,
            "_safe_fetch_page",
            side_effect=mock_safe_fetch,
        )

        with pytest.raises(PartialFetchError) as exc_info:
            await client._paginate("http://test", {})

        assert [r["id"] for r in exc_info.value.results] == [1, 3]
        assert exc_info.value.failed_pages == [2]

    async def test_paginate_short_circuits_on_single_page(self, client, mocker):
        """Should not trigger workers or gather if only one page exists."""
        mocker.patch.object(
            client,
            "_fetch_page",
            return_value={"results": [{"id": 1}], "pagination": {"pages": 1}},
        )
        spy_safe = mocker.spy(client, "_safe_fetch_page")

        results = await client._paginate("http://test", {})

        assert len(results) == 1
        spy_safe.assert_not_called()

    async def test_paginate_short_circuits_on_empty_first_page(self, client, mocker):
        """Should return empty list immediately when first page has no results,
        even if the API reports multiple pages."""
        mocker.patch.object(
            client,
            "_fetch_page",
            return_value={"results": [], "pagination": {"pages": 5}},
        )
        spy_safe = mocker.spy(client, "_safe_fetch_page")

        results = await client._paginate("http://test", {})

        assert results == []
        spy_safe.assert_not_called()
