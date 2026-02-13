from unittest.mock import Mock, patch

import httpx
import pytest

from civic_lantern.services.fec_client import FECClient
from civic_lantern.services.fec_exceptions import (
    FECNotFoundError,
    FECRateLimitError,
    FECServerError,
)


@pytest.mark.asyncio
class TestFECClientErrorHandling:
    """Test that HTTP errors map to correct exceptions."""

    @pytest.mark.integration
    @patch("civic_lantern.services.fec_client.httpx.AsyncClient.get")
    async def test_get_candidates_raises_rate_limit_error(self, mock_get):
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

    @pytest.mark.integration
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

    @pytest.mark.integration
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
