import asyncio
from collections import defaultdict
from decimal import Decimal
from typing import Any, Dict, List

from pydantic import ValidationError

from civic_lantern.jobs.base_ingestor import BaseIngestor
from civic_lantern.schemas.spending import CandidateSpendingSchema
from civic_lantern.services.data.spending import CandidateSpendingService


class SpendingIngestor(BaseIngestor):
    """
    Ingests spending aggregates (Inside & Outside) for Candidates.
    Merges /candidates/totals and /schedules/schedule_e/totals/by_candidate.
    """

    entity_name = "spending_totals"

    async def fetch(self, cycle: int = 2024, **kwargs: Any) -> Dict[str, Any]:
        """Fetches Inside and Outside totals concurrently."""

        inside_task = self.client.get_candidate_totals(cycle=cycle)
        outside_task = self.client.get_outside_spending_totals(cycle=cycle)

        inside_results, outside_results = await asyncio.gather(
            inside_task, outside_task
        )

        return {
            "cycle": cycle,
            "inside": inside_results,
            "outside": outside_results,
        }

    def transform(self, raw_data: Dict[str, Any]) -> List[CandidateSpendingSchema]:
        """Transforms raw dicts into validated Pydantic schemas, skipping invalid records."""
        merged_stats = self._merge_fec_data(
            raw_data["cycle"], raw_data["inside"], raw_data["outside"]
        )
        results = []
        for stats in merged_stats:
            try:
                results.append(CandidateSpendingSchema(**stats))
            except ValidationError as e:
                self.logger.warning(
                    f"Skipping invalid record for candidate "
                    f"{stats.get('candidate_id')!r}: {e}"
                )
        return results

    def _merge_fec_data(
        self, cycle: int, inside: List[dict], outside: List[dict]
    ) -> List[dict]:
        """Private helper to align disparate FEC rows by candidate_id."""

        merged = defaultdict(
            lambda: {
                "cycle": cycle,
                "inside_receipts": Decimal(0),
                "inside_disbursements": Decimal(0),
                "outside_support": Decimal(0),
                "outside_oppose": Decimal(0),
            }
        )

        # 1. Map Inside Spending
        for item in inside:
            cid = item["candidate_id"]
            merged[cid]["candidate_id"] = cid
            merged[cid]["inside_receipts"] = Decimal(str(item.get("receipts") or 0))
            merged[cid]["inside_disbursements"] = Decimal(
                str(item.get("disbursements") or 0)
            )

        # 2. Map Outside Spending (Handling S/O indicator rows)
        for item in outside:
            cid = item["candidate_id"]
            merged[cid]["candidate_id"] = cid

            indicator = item.get("support_oppose_indicator")
            amount = Decimal(str(item.get("total") or 0))

            if indicator == "S":
                merged[cid]["outside_support"] += amount
            elif indicator == "O":
                merged[cid]["outside_oppose"] += amount

        return list(merged.values())

    def create_service(self) -> CandidateSpendingService:
        return CandidateSpendingService(db=self.session)
