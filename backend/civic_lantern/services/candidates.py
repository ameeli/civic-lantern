import asyncio

from civic_lantern.services.fec_client import FECClient


async def ingest_candidates(cycle: int = 2024):
    """Import candidates from FEC API."""
    client = FECClient()

    try:
        fec_results = await client.get_candidates(cycle=cycle)
        print(f"Retrieved {len(fec_results)} candidates")
        print(fec_results[len(fec_results) // 2])

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(ingest_candidates())
