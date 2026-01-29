import logging

import httpx
from aiolimiter import AsyncLimiter

from civic_lantern.core.config import get_settings
from civic_lantern.services.fec_exceptions import (
    FECAPIError,
    FECAuthenticationError,
    FECNotFoundError,
    FECRateLimitError,
    FECTimeoutError,
    FECValidationError,
)
from civic_lantern.services.http_utils import fec_retry

settings = get_settings()
logger = logging.getLogger(__name__)


class FECClient:
    def __init__(self):
        self.base_url = "https://api.open.fec.gov/v1"
        self.api_key = settings.FEC_API_KEY
        self.client = httpx.AsyncClient(timeout=30.0)
        self.limiter = AsyncLimiter(max_rate=900, time_period=3600)

    @fec_retry
    async def _fetch_page(self, url: str, params: dict) -> dict:
        """Fetch a single page from the API."""
        async with self.limiter:
            try:
                response = await self.client.get(url, params=params)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code

                if status_code == 429:
                    raise FECRateLimitError(
                        "Rate limit exceeded despite limiter. "
                        "Check limiter configuration."
                    ) from e

                elif status_code == 404:
                    raise FECNotFoundError(f"Resource not found: {url}") from e

                elif status_code == 400:
                    raise FECValidationError(f"Invalid parameters: {params}") from e

                elif status_code in (401, 403):
                    raise FECAuthenticationError("Invalid or missing API key") from e

                else:
                    raise FECAPIError(f"HTTP {status_code} error: {e}") from e

            except httpx.TimeoutException as e:
                raise FECTimeoutError(f"Request timeout after 30 seconds: {url}") from e

            except httpx.RequestError as e:
                raise FECAPIError(f"Request failed: {e}") from e

    async def _paginate(
        self,
        url: str,
        base_params: dict,
        max_pages: int | None = None,
    ) -> list[dict]:
        """
        Generic pagination handler for any FEC endpoint.

        Args:
            url: The API endpoint URL
            base_params: Base parameters (without 'page')

        Returns:
            List of all results across all pages
        """
        all_results = []
        page = 1

        while True:
            if max_pages and page >= max_pages:
                break

            logger.info("Fetching page", extra={"page": page, "endpoint": url})

            params = {**base_params, "page": page}
            data = await self._fetch_page(url, params)

            results = data.get("results", [])
            if not results:
                break

            all_results.extend(results)

            pagination = data.get("pagination", {})
            total_pages = pagination.get("pages")

            if total_pages is not None and page >= total_pages:
                break

            page += 1

        return all_results

    async def get_candidates(self, per_page: int = 100, **kwargs) -> list[dict]:
        """Fetch candidates for a cycle."""
        url = f"{self.base_url}/candidates/"
        params = {
            "api_key": self.api_key,
            "per_page": per_page,
        }
        params.update(kwargs)

        candidates = await self._paginate(url, params)
        logger.info(f"✅ Fetched {len(candidates)} candidates")
        return candidates

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self):
        await self.client.aclose()
