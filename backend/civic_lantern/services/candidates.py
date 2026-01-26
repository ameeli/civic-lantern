import asyncio

from civic_lantern.services.fec_client import FECClient
from civic_lantern.utils.transformers import transform_candidates


async def ingest_candidates(cycle: int = 2024):
    """Import candidates from FEC API."""
    async with FECClient() as client:
        raw_candidates = await client.get_candidates(cycle=cycle)
        transformed_candidates = transform_candidates(raw_candidates)
        print(f"Transformed {len(transformed_candidates)} transformed_candidates")
        print(transformed_candidates[len(transformed_candidates) // 2])


if __name__ == "__main__":
    asyncio.run(ingest_candidates())
