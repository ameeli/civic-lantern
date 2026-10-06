import asyncio
from unittest.mock import AsyncMock

import httpx
import pytest
import respx

from civic_lantern.jobs.ingestors.candidates import CANDIDATES
from civic_lantern.jobs.ingestors.committees import COMMITTEES
from civic_lantern.jobs.ingestors.inside_totals_by_candidate import CANDIDATE_TOTALS
from civic_lantern.jobs.ingestors.schedule_e_totals_by_candidate import (
    SCHEDULE_E_TOTALS,
)
from civic_lantern.services.committee_corrections import (
    COMMITTEE_REPORTS,
    COMMITTEE_TOTALS,
)
from civic_lantern.services.fec_client import FECClient, FECEndpoint
from civic_lantern.services.fec_exceptions import (
    FECAuthenticationError,
    FECNetworkError,
    FECNotFoundError,
    FECRateLimitError,
    FECServerError,
    FECTimeoutError,
    FECValidationError,
    PartialFetchError,
)

THINGS = FECEndpoint(name="things", path="/things/", sort=("thing_id",))
COMMITTEE_THINGS = FECEndpoint(
    name="committee things",
    path="/committee/{committee_id}/things/",
    sort=("-cycle", "thing_id"),
    params={"office": ("P", "S")},
    required=("cycle",),
)


def _page(results: list, pages: int = 1) -> httpx.Response:
    return httpx.Response(
        200, json={"results": results, "pagination": {"pages": pages}}
    )


def _url(client: FECClient, path: str) -> str:
    return f"{client.base_url}{path}"


@pytest.mark.unit
class TestFECEndpoint:
    def test_requires_a_sort_key(self):
        with pytest.raises(ValueError, match="needs a sort key"):
            FECEndpoint(name="unsorted", path="/unsorted/", sort=())


@pytest.mark.unit
@pytest.mark.asyncio
class TestFetchAllRequest:
    """fetch_all builds each request from the endpoint description."""

    @respx.mock
    async def test_sends_owned_endpoint_and_caller_params(self, client):
        route = respx.get(_url(client, "/committee/C001/things/")).mock(
            return_value=_page([{"thing_id": 1}])
        )

        rows = await client.fetch_all(
            COMMITTEE_THINGS, committee_id="C001", cycle=2024, min_date="2024-01-01"
        )

        assert rows == [{"thing_id": 1}]
        params = route.calls[0].request.url.params
        assert params["api_key"] == client.api_key
        assert params["per_page"] == "100"
        assert params.get_list("office") == ["P", "S"]
        assert params.get_list("sort") == ["-cycle", "thing_id"]
        assert params["cycle"] == "2024"
        assert params["min_date"] == "2024-01-01"
        assert params["page"] == "1"
        assert "committee_id" not in params

    @pytest.mark.parametrize(
        "kwargs, missing",
        [({"cycle": 2024}, "committee_id"), ({"committee_id": "C001"}, "cycle")],
    )
    @respx.mock
    async def test_missing_path_or_required_param_raises_before_any_request(
        self, client, kwargs, missing
    ):
        route = respx.get(url__startswith=client.base_url)

        with pytest.raises(TypeError, match=missing):
            await client.fetch_all(COMMITTEE_THINGS, **kwargs)

        assert not route.called

    @pytest.mark.parametrize("owned", ["sort", "api_key"])
    async def test_callers_cannot_override_owned_params(self, client, owned):
        with pytest.raises(ValueError, match=owned):
            await client.fetch_all(THINGS, **{owned: "x"})


@pytest.mark.unit
@pytest.mark.asyncio
class TestDeclaredEndpoints:
    """Each ingestor's endpoint description produces the request FEC expects."""

    @pytest.mark.parametrize(
        "endpoint, kwargs, path, expected",
        [
            (CANDIDATES, {}, "/candidates/", {"sort": ["candidate_id"]}),
            (COMMITTEES, {}, "/committees/", {"sort": ["committee_id"]}),
            (
                CANDIDATE_TOTALS,
                {"cycle": 2024},
                "/candidates/totals/",
                {"sort": ["candidate_id"], "election_full": ["false"]},
            ),
            (
                SCHEDULE_E_TOTALS,
                {"cycle": 2024},
                "/schedules/schedule_e/totals/by_candidate/",
                {"sort": ["candidate_id", "support_oppose_indicator"]},
            ),
            (
                COMMITTEE_TOTALS,
                {"committee_id": "C001", "cycle": 2024},
                "/committee/C001/totals/",
                {"sort": ["-cycle"]},
            ),
            (
                COMMITTEE_REPORTS,
                {"committee_id": "C001", "cycle": 2024},
                "/committee/C001/reports/",
                {"sort": ["coverage_start_date", "beginning_image_number"]},
            ),
        ],
        ids=lambda v: v.name if isinstance(v, FECEndpoint) else None,
    )
    @respx.mock
    async def test_every_page_request_matches_endpoint(
        self, client, endpoint, kwargs, path, expected
    ):
        route = respx.get(_url(client, path)).mock(
            return_value=_page([{"id": 1}], pages=3)
        )

        await client.fetch_all(endpoint, **kwargs)

        assert len(route.calls) == 3
        for call in route.calls:
            params = call.request.url.params
            for key, values in expected.items():
                assert params.get_list(key) == values

    @pytest.mark.parametrize("endpoint", [CANDIDATES, CANDIDATE_TOTALS])
    @respx.mock
    async def test_federal_offices_are_requested(self, client, endpoint):
        route = respx.get(url__startswith=client.base_url).mock(return_value=_page([]))

        await client.fetch_all(endpoint, cycle=2024)

        assert route.calls[0].request.url.params.get_list("office") == ["P", "S", "H"]


@pytest.mark.unit
@pytest.mark.asyncio
class TestFetchAllErrors:
    """HTTP failures map to FEC exceptions; retryable ones are retried 3 times."""

    @pytest.mark.parametrize(
        "status, error, retried",
        [
            (400, FECValidationError, False),
            (401, FECAuthenticationError, False),
            (404, FECNotFoundError, False),
            (429, FECRateLimitError, True),
            (503, FECServerError, True),
        ],
    )
    @respx.mock
    async def test_status_maps_to_exception(
        self, client, mocker, status, error, retried
    ):
        mocker.patch("asyncio.sleep")  # skip fec_retry backoff
        route = respx.get(_url(client, "/things/")).mock(
            return_value=httpx.Response(status, json={"error": "nope"})
        )

        with pytest.raises(error) as exc_info:
            await client.fetch_all(THINGS)

        assert exc_info.value.retryable is retried
        assert len(route.calls) == (3 if retried else 1)

    @respx.mock
    async def test_recovers_after_a_retried_server_error(self, client, mocker):
        mocker.patch("asyncio.sleep")
        route = respx.get(_url(client, "/things/")).mock(
            side_effect=[httpx.Response(500), _page([{"thing_id": 1}])]
        )

        assert await client.fetch_all(THINGS) == [{"thing_id": 1}]
        assert len(route.calls) == 2

    @pytest.mark.parametrize(
        "raised, error",
        [
            (httpx.TimeoutException("timed out"), FECTimeoutError),
            (httpx.NetworkError("connection refused"), FECNetworkError),
        ],
    )
    @respx.mock
    async def test_transport_failures_map_to_retryable_errors(
        self, client, mocker, raised, error
    ):
        mocker.patch("asyncio.sleep")
        respx.get(_url(client, "/things/")).mock(side_effect=raised)

        with pytest.raises(error) as exc_info:
            await client.fetch_all(THINGS)

        assert exc_info.value.retryable is True


@pytest.mark.unit
@pytest.mark.asyncio
class TestFetchAllPagination:
    @respx.mock
    async def test_combines_all_pages_in_page_order(self, client):
        def respond(request):
            page = int(request.url.params["page"])
            return _page([{"page": page}], pages=3)

        respx.get(_url(client, "/things/")).mock(side_effect=respond)

        rows = await client.fetch_all(THINGS)

        assert rows == [{"page": 1}, {"page": 2}, {"page": 3}]

    @respx.mock
    async def test_failed_pages_raise_partial_fetch_error_with_fetched_rows(
        self, client, mocker
    ):
        mocker.patch("asyncio.sleep")

        def respond(request):
            page = int(request.url.params["page"])
            if page == 2:
                return httpx.Response(503)
            return _page([{"page": page}], pages=3)

        respx.get(_url(client, "/things/")).mock(side_effect=respond)

        with pytest.raises(PartialFetchError, match="1/3 pages failed for things") as e:
            await client.fetch_all(THINGS)

        assert e.value.results == [{"page": 1}, {"page": 3}]
        assert e.value.failed_pages == [2]

    @pytest.mark.parametrize(
        "first_page",
        [_page([{"page": 1}], pages=1), _page([], pages=5)],
        ids=["single_page", "empty_first_page"],
    )
    @respx.mock
    async def test_stops_after_page_one_when_nothing_more(self, client, first_page):
        route = respx.get(_url(client, "/things/")).mock(return_value=first_page)

        await client.fetch_all(THINGS)

        assert len(route.calls) == 1

    @respx.mock
    async def test_fetches_at_most_ten_pages_at_once(self, client):
        in_flight = peak = 0

        async def respond(request):
            nonlocal in_flight, peak
            in_flight += 1
            peak = max(peak, in_flight)
            await asyncio.sleep(0.01)
            in_flight -= 1
            return _page([{"id": 1}], pages=30)

        respx.get(_url(client, "/things/")).mock(side_effect=respond)

        rows = await client.fetch_all(THINGS)

        assert len(rows) == 30
        assert peak == 10

    @respx.mock
    async def test_progress_bar_mode_returns_the_same_rows(self, client):
        client.show_progress = True
        respx.get(_url(client, "/things/")).mock(
            side_effect=lambda r: _page([{"page": r.url.params["page"]}], pages=2)
        )

        assert await client.fetch_all(THINGS) == [{"page": "1"}, {"page": "2"}]


@pytest.mark.unit
@pytest.mark.asyncio
class TestFECClientRateLimiting:
    @respx.mock
    async def test_both_limiters_acquired_per_request(self, client):
        respx.get(_url(client, "/things/")).mock(return_value=_page([{"id": 1}]))
        client.limiter = AsyncMock()
        client.minute_limiter = AsyncMock()

        await client.fetch_all(THINGS)

        client.limiter.__aenter__.assert_awaited_once()
        client.minute_limiter.__aenter__.assert_awaited_once()
