from unittest.mock import Mock, patch

import httpx
import pytest
import respx

from civic_lantern.services.fec_client import FECClient
from civic_lantern.services.fec_exceptions import (
    FECNotFoundError,
    FECRateLimitError,
    FECServerError,
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
