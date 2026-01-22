import asyncio

from civic_lantern.services.fec_client import FECClient


async def ingest_candidates(cycle: int = 2024):
    """Import candidates from FEC API."""
    async with FECClient() as client:
        candidates = await client.get_candidates(cycle=cycle)
        print(f"Retrieved {len(candidates)} candidates")
        print(candidates[len(candidates) // 2])


if __name__ == "__main__":
    asyncio.run(ingest_candidates())
