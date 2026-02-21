import asyncio
from unittest.mock import ANY, Mock, patch

import httpx
import pytest
import respx

from civic_lantern.services.fec_client import FECClient
from civic_lantern.services.fec_exceptions import (
    FECNetworkError,
    FECNotFoundError,
    FECRateLimitError,
    FECServerError,
    FECTimeoutError,
)


@pytest.mark.unit
@pytest.mark.asyncio
class TestFECClientErrorHandling:
    """Test that HTTP errors map to correct exceptions."""

    async def test_404_raises_not_found_error(self):
        """404 should raise FECNotFoundError (non-retryable)."""
        client = FECClient()

        mock_response = Mock()
        mock_response.status_code = 404

        error = httpx.HTTPStatusError(
            "Not found", request=Mock(), response=mock_response
        )

        with pytest.raises(FECNotFoundError) as exc_info:
            client._raise_fec_error(error, url="test", params={})

        assert exc_info.value.retryable is False

    async def test_500_raises_server_error(self):
        """5xx should raise FECServerError (retryable)."""
        client = FECClient()

        mock_response = Mock()
        mock_response.status_code = 503

        error = httpx.HTTPStatusError(
            "Service unavailable", request=Mock(), response=mock_response
        )

        with pytest.raises(FECServerError) as exc_info:
            client._raise_fec_error(error, url="test", params={})

        assert exc_info.value.retryable is True

    @patch("civic_lantern.services.fec_client.httpx.AsyncClient.get")
    @patch("asyncio.sleep", return_value=None)
    async def test_get_candidates_raises_rate_limit_error(self, _mock_sleep, mock_get):
        """Public method should bubble up the correct custom exception."""
        client = FECClient()

        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Too Many Requests", request=Mock(), response=mock_response
        )
        mock_get.return_value = mock_response

        with pytest.raises(FECRateLimitError):
            await client.get_candidates(election_year=2024)

    @respx.mock
    @patch("asyncio.sleep", return_value=None)
    async def test_fetch_retries_on_500_error(self, _mock_sleep):
        """Client should retry 5xx errors."""
        async with FECClient() as client:
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
    @patch("asyncio.sleep", return_value=None)
    async def test_fetch_gives_up_after_retries(self, _mock_sleep):
        """Should give up after max retries, bypass waiting for backoff."""
        async with FECClient() as client:
            route = respx.get(url__startswith=client.candidate_url).mock(
                return_value=httpx.Response(503, json={"error": "Unavailable"})
            )

            with pytest.raises(FECServerError):
                await client.get_candidates(election_year=2024)

        assert len(route.calls) == 3

    @respx.mock
    @patch("asyncio.sleep", return_value=None)
    async def test_fetch_raises_timeout_error(self, _mock_sleep):
        """httpx.TimeoutException should raise FECTimeoutError (retryable)."""
        async with FECClient() as client:
            respx.get(url__startswith=client.candidate_url).mock(
                side_effect=httpx.TimeoutException("timed out")
            )

            with pytest.raises(FECTimeoutError) as exc_info:
                await client.get_candidates(election_year=2024)

        assert exc_info.value.retryable is True

    @respx.mock
    @patch("asyncio.sleep", return_value=None)
    async def test_fetch_raises_network_error(self, _mock_sleep):
        """httpx.NetworkError should raise FECNetworkError (retryable)."""
        async with FECClient() as client:
            respx.get(url__startswith=client.candidate_url).mock(
                side_effect=httpx.NetworkError("connection refused")
            )

            with pytest.raises(FECNetworkError) as exc_info:
                await client.get_candidates(election_year=2024)

        assert exc_info.value.retryable is True


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

    async def test_paginate_aggregates_successful_pages_only(self, client, mocker):
        """Orchestrator gracefully handles workers that return Exception objects."""
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

        results = await client._paginate("http://test", {})

        assert len(results) == 2
        assert [r["id"] for r in results] == [1, 3]

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
