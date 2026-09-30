import asyncio
import logging
from dataclasses import dataclass, field
from string import Formatter
from typing import Any, Dict, List, Mapping, NoReturn, Tuple

import httpx
from aiolimiter import AsyncLimiter
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
    PartialFetchError,
)
from civic_lantern.services.http_utils import fec_retry

settings = get_settings()
logger = logging.getLogger(__name__)

FEDERAL_OFFICES = ("P", "S", "H")
PER_PAGE = 100


@dataclass(frozen=True, eq=False)
class FECEndpoint:
    """One paginated FEC endpoint, described as data by the module that uses it."""

    name: str
    # Relative to BASE_URL; {placeholders} are filled from fetch_all's params.
    path: str
    # Must order rows uniquely: pages are fetched in parallel, so ties can shift rows.
    sort: Tuple[str, ...]
    params: Mapping[str, Any] = field(default_factory=dict)
    required: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.sort:
            raise ValueError(f"FEC endpoint {self.name!r} needs a sort key")


class FECClient:
    BASE_URL = "https://api.open.fec.gov/v1"

    def __init__(self, show_progress: bool = True):
        self.base_url = self.BASE_URL
        self.show_progress = show_progress
        self.api_key = settings.FEC_API_KEY
        self.client = httpx.AsyncClient(timeout=30.0)
        self.limiter = AsyncLimiter(max_rate=900, time_period=3600)
        # The FEC API has an undocumented per-minute burst limit
        # max_rate=1 allows 60 req/min.
        self.minute_limiter = AsyncLimiter(max_rate=1, time_period=1)

    async def fetch_all(
        self, endpoint: FECEndpoint, **params: Any
    ) -> List[Dict[str, Any]]:
        """Fetch every row of `endpoint` across all pages.

        Params naming a {placeholder} in endpoint.path fill it; the rest are
        query params. The client owns api_key, per_page and sort. Raises
        PartialFetchError, carrying the rows fetched, if pages fail after retries.
        """
        owned = {"api_key", "sort"} & params.keys()
        if owned:
            raise ValueError(f"{sorted(owned)} are set by FECClient, not callers")
        placeholders = {f for _, f, _, _ in Formatter().parse(endpoint.path) if f}
        missing = [k for k in (*placeholders, *endpoint.required) if k not in params]
        if missing:
            raise TypeError(f"FEC endpoint {endpoint.name!r} needs {missing}")

        path = endpoint.path.format(**{k: params.pop(k) for k in placeholders})
        query = {
            "api_key": self.api_key,
            "per_page": PER_PAGE,
            **endpoint.params,
            **params,
            "sort": list(endpoint.sort),
        }
        rows = await self._paginate(f"{self.base_url}{path}", query, endpoint.name)
        logger.info(f"✅ Fetched {len(rows)} {endpoint.name} row(s) from {path}")
        return rows

    @fec_retry
    async def _fetch_page(self, url: str, params: dict) -> dict:
        async with self.minute_limiter, self.limiter:
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

    def _raise_fec_error(
        self, e: httpx.HTTPStatusError, *, url: str, params: dict
    ) -> NoReturn:
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
        self, url: str, base_params: dict, label: str
    ) -> List[Dict[str, Any]]:
        """Fetch page 1, then the remaining pages concurrently."""
        p1_data = await self._fetch_page(url, {**base_params, "page": 1})
        results = p1_data.get("results", [])

        last_page = p1_data.get("pagination", {}).get("pages", 1)

        if not results or last_page <= 1:
            return results

        concurrency_limit = asyncio.Semaphore(10)
        tasks = [
            self._safe_fetch_page(url, base_params, p, concurrency_limit)
            for p in range(2, last_page + 1)
        ]

        if self.show_progress:
            responses = await tqdm_asyncio.gather(
                *tasks, desc=f"Fetching {label}", unit="page"
            )
        else:
            responses = await asyncio.gather(*tasks)

        failed_pages = []
        for i, resp in enumerate(responses):
            if isinstance(resp, Exception):
                failed_pages.append(i + 2)
                continue
            results.extend(resp.get("results", []))

        if failed_pages:
            logger.warning(
                f"Partial results for {label}: "
                f"{len(failed_pages)}/{last_page} pages failed "
                f"(pages {failed_pages}). {len(results)} records returned."
            )
            raise PartialFetchError(
                f"{len(failed_pages)}/{last_page} pages failed for {label}",
                results=results,
                failed_pages=failed_pages,
            )

        return results

    async def _safe_fetch_page(
        self, url: str, params: dict, page: int, sem: asyncio.Semaphore
    ):
        async with sem:
            try:
                return await self._fetch_page(url, {**params, "page": page})
            except Exception as e:
                logger.warning(f"Page {page} failed: {e}")
                return e

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self):
        await self.client.aclose()
