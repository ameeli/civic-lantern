import logging
from typing import Any, Dict, List, Optional

import httpx
from aiolimiter import AsyncLimiter
from tqdm import tqdm
from tqdm.asyncio import tqdm_asyncio

from civic_lantern.core.config import get_settings
from civic_lantern.services.fec_exceptions import (
    FECAPIError,
    FECAuthenticationError,
    FECNetworkError,
    FECNotFoundError,
    FECProtocolError,
    FECRateLimitError,
    FECServerError,
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
        async with self.limiter:
            try:
                response = await self.client.get(url, params=params)
                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as e:
                self._raise_fec_error(e, url=url, params=params)

            except httpx.TimeoutException as e:
                raise FECTimeoutError(f"Request timeout after 30 seconds: {url}") from e

            except httpx.NetworkError as e:
                raise FECNetworkError("Network connectivity failed") from e

            except httpx.ProtocolError as e:
                raise FECProtocolError(f"Protocol error: {e}") from e

            except httpx.RequestError as e:
                raise FECAPIError(f"Request failed: {e}") from e

    def _raise_fec_error(self, e: httpx.HTTPStatusError, *, url: str, params: dict):
        response = e.response
        status = response.status_code

        if status == 429:
            raise FECRateLimitError("Rate limit exceeded", status_code=status) from e
        elif status == 404:
            raise FECNotFoundError(
                f"Resource not found: {url}", status_code=status, response=response
            ) from e
        elif status == 400:
            raise FECValidationError(
                f"Invalid parameters: {params}", status_code=status, response=response
            ) from e
        elif status in (401, 403):
            raise FECAuthenticationError(
                "Invalid or missing API key", status_code=status, response=response
            ) from e
        elif status >= 500:
            raise FECServerError(
                f"Server error {status}", status_code=status, response=response
            ) from e
        else:
            raise FECAPIError(
                f"HTTP {status} error", status_code=status, response=response
            ) from e

    async def _paginate(
        self, url: str, base_params: dict, max_pages: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Parallel pagination with a real-time progress bar."""
        p1_data = await self._fetch_page(url, {**base_params, "page": 1})
        results = p1_data.get("results", [])

        total_pages = p1_data.get("pagination", {}).get("pages", 1)
        last_page = min(total_pages, max_pages) if max_pages else total_pages

        if not results or last_page <= 1:
            return results

        async def safe_fetch(page_num: int):
            """Wrapper that catches exceptions per task."""
            try:
                return await self._fetch_page(url, {**base_params, "page": page_num})
            except Exception as e:
                return e

        tasks = [safe_fetch(p) for p in range(2, last_page + 1)]

        endpoint_name = url.rstrip("/").split("?")[0].split("/")[-1] or "data"
        responses = await tqdm_asyncio.gather(
            *tasks,
            desc=f"Fetching {endpoint_name}",
            unit="page",
        )

        for i, resp in enumerate(responses):
            if isinstance(resp, Exception):
                tqdm.write(f"❌ Page {i + 2} failed: {resp}")
                continue
            results.extend(resp.get("results", []))

        return results

    async def get_candidates(self, per_page: int = 100, **kwargs) -> list[dict]:
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
