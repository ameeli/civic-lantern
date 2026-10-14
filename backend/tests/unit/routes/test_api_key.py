import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from civic_lantern.api.deps import get_db
from civic_lantern.core.config import get_settings
from civic_lantern.main import app
from tests.unit.conftest import scalars_all_result

READY_CYCLES_URL = str(app.url_path_for("get_ready_election_cycles"))


@pytest_asyncio.fixture
async def client_with_keys(mock_session):
    """Client with no default auth header; call it with the API_KEYS setting to use."""
    clients = []

    async def _override_db():
        yield mock_session

    async def make(api_keys: str | None) -> AsyncClient:
        settings = get_settings().model_copy(update={"API_KEYS": api_keys})
        app.dependency_overrides[get_settings] = lambda: settings
        app.dependency_overrides[get_db] = _override_db
        client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
        clients.append(client)
        return client

    yield make
    for client in clients:
        await client.aclose()
    app.dependency_overrides.clear()


def bearer(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


@pytest.mark.unit
@pytest.mark.asyncio
class TestApiKey:
    async def test_health_needs_no_key(self, client_with_keys):
        client = await client_with_keys("key-one")
        response = await client.get("/health")
        assert response.status_code == 200

    @pytest.mark.parametrize(
        "headers",
        [
            {},
            bearer("wrong-key"),
            bearer("key-on"),  # a prefix of a real key
            {"Authorization": "Basic key-one"},
            {"Authorization": "key-one"},
        ],
    )
    async def test_rejects_missing_or_wrong_key(self, client_with_keys, headers):
        client = await client_with_keys("key-one,key-two")
        response = await client.get(READY_CYCLES_URL, headers=headers)
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"

    @pytest.mark.parametrize("key", ["key-one", "key-two"])
    async def test_accepts_every_configured_key(
        self, client_with_keys, mock_session, key
    ):
        # Two keys are configured only mid-rotation; both must work then.
        mock_session.execute.return_value = scalars_all_result([])
        client = await client_with_keys(" key-one , key-two ")
        response = await client.get(READY_CYCLES_URL, headers=bearer(key))
        assert response.status_code == 200

    @pytest.mark.parametrize("api_keys", [None, "", " , "])
    async def test_fails_closed_when_no_key_is_configured(
        self, client_with_keys, api_keys
    ):
        client = await client_with_keys(api_keys)
        response = await client.get(READY_CYCLES_URL, headers=bearer(""))
        assert response.status_code == 500
        assert response.json()["detail"] == "API_KEYS is not configured"

    async def test_every_api_route_requires_the_key(self, client_with_keys):
        # Guards against a future router being mounted without the dependency.
        client = await client_with_keys("key-one")
        # The OpenAPI schema lists every mounted endpoint, however it's nested.
        api_paths = [p for p in app.openapi()["paths"] if p.startswith("/api/")]
        assert len(api_paths) >= 6
        for template in api_paths:
            path = template.replace("{cycle}", "2024").replace(
                "{candidate_id}", "H0XX00000"
            )
            response = await client.get(path)
            assert response.status_code == 401, template
