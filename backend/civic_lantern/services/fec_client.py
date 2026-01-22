# civic_lantern/services/fec_client.py
import logging

import httpx
from aiolimiter import AsyncLimiter

from civic_lantern.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class FECClient:
    def __init__(self):
        self.base_url = "https://api.open.fec.gov/v1"
        self.api_key = settings.FEC_API_KEY
        self.client = httpx.AsyncClient(timeout=30.0)
        self.limiter = AsyncLimiter(max_rate=900, time_period=3600)

    async def _fetch_page(self, url: str, params: dict) -> dict:
        """Fetch a single page from the API."""
        async with self.limiter:
            try:
                response = await self.client.get(url, params=params)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                # todo: add custom exception classes
                logger.error(f"❌ HTTP error: {e}")
                raise

    async def _paginate(
        # todo: max_pages = 100, temp 3 for manual testing
        self,
        url: str,
        base_params: dict,
        max_pages: int = 3,
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

        while page <= max_pages:
            logger.info(f"Fetching page {page}")

            params = {**base_params, "page": page}
            data = await self._fetch_page(url, params)

            results = data.get("results", [])
            if not results:
                break

            all_results.extend(results)

            pagination = data.get("pagination", {})
            total_pages = pagination.get("pages", 0)

            if page >= total_pages:
                break

            page += 1

        return all_results

    async def get_candidates(self, cycle, per_page: int = 100) -> list[dict]:
        """Fetch candidates for a cycle."""
        url = f"{self.base_url}/candidates/"
        params = {
            "api_key": self.api_key,
            "election_year": cycle,
            "per_page": per_page,
        }

        candidates = await self._paginate(url, params)
        logger.info(f"✅ Fetched {len(candidates)} candidates")
        return candidates

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self):
        await self.client.aclose()
