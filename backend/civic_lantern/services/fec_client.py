# civic_lantern/services/fec_client.py
import httpx

from civic_lantern.core.config import get_settings

settings = get_settings()


class FECClient:
    def __init__(self):
        self.base_url = "https://api.open.fec.gov/v1"
        self.api_key = settings.FEC_API_KEY
        self.client = httpx.AsyncClient(timeout=30.0)

    async def get_candidates(self, cycle, per_page: int = 100):
        """Fetch candidates for a cycle."""
        url = f"{self.base_url}/candidates/"
        all_results = []
        page = 1

        while True:
            params = {
                "api_key": self.api_key,
                "election_year": cycle,
                "per_page": per_page,
                "page": page,
            }

            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            results = data.get("results", [])
            all_results.extend(results)

            pagination = data.get("pagination", {})
            print(pagination)

            if page >= 5:
                break
            # if page >= pagination.get("pages", 0):
            #     break
            page += 1

        return all_results

    async def close(self):
        await self.client.aclose()
