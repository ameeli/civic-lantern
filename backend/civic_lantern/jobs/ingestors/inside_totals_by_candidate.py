from typing import Any, Dict, List

from civic_lantern.jobs.base_ingestor import BaseIngestor
from civic_lantern.services.data.inside_totals_by_candidate import (
    InsideTotalsByCandidateService,
)
from civic_lantern.utils.transformers import transform_inside_totals_by_candidate

# FEC's /candidates/totals/ only aggregates committees CURRENTLY designated
# as a candidate's authorized/principal committee. When a committee is
# redesignated after a campaign ends (e.g. converted to a leadership PAC),
# its historical activity silently drops out of the candidate's totals even
# though it was legitimately raised/spent as that candidate's committee at
# the time.
#
# This is a manual, per-candidate stopgap for known cases, pending a general
# fix that resolves a candidate's committees by historical linkage (see
# /candidate/{id}/committees/history/) instead of current designation.
# Remove each entry once that fix ships.
KNOWN_COMMITTEE_OVERRIDES: Dict[tuple, List[str]] = {
    # Trump's principal 2024 campaign committee was renamed "NEVER
    # SURRENDER, INC." and redesignated a Leadership PAC after the
    # election. Verified via /committee/C00828541/totals/: $495,853,270.30
    # receipts / $471,501,651.83 disbursements for cycle 2024, absent from
    # /candidates/P80001571/totals/.
    ("P80001571", 2024): ["C00828541"],
}


class InsideTotalsByCandidateIngestor(BaseIngestor):
    """Ingests candidate inside spending totals from /candidates/totals/."""

    entity_name = "inside_totals_by_candidate"

    async def fetch(self, cycle: int, **kwargs: Any) -> List[Dict[str, Any]]:
        """Fetch inside spending totals for all candidates in the given cycle."""
        raw = await self.client.get_candidate_totals(cycle=cycle, **kwargs)
        raw.extend(await self._fetch_overrides(cycle))
        return raw

    async def _fetch_overrides(self, cycle: int) -> List[Dict[str, Any]]:
        """Patch in committees FEC's candidate-totals endpoint has dropped
        after a post-campaign redesignation. See KNOWN_COMMITTEE_OVERRIDES.

        Synthesizes rows shaped like /candidates/totals/ output (just
        candidate_id/cycle/receipts/disbursements) so the existing
        transform's per-(candidate_id, cycle) accumulation picks them up
        and sums them alongside whatever FEC's own endpoint still returns.
        """
        rows: List[Dict[str, Any]] = []
        for (
            candidate_id,
            override_cycle,
        ), committee_ids in KNOWN_COMMITTEE_OVERRIDES.items():
            if override_cycle != cycle:
                continue
            for committee_id in committee_ids:
                totals = await self.client.get_committee_totals(
                    committee_id, cycle=cycle
                )
                for total in totals:
                    rows.append(
                        {
                            "candidate_id": candidate_id,
                            "cycle": cycle,
                            "receipts": total.get("receipts"),
                            "disbursements": total.get("disbursements"),
                        }
                    )
        return rows

    def transform(self, raw_data: List[Dict[str, Any]]) -> list:
        """Accumulate and validate raw candidate totals through schema."""
        return transform_inside_totals_by_candidate(raw_data)

    def create_service(self) -> InsideTotalsByCandidateService:
        """Return an InsideTotalsByCandidateService wired to the current DB session."""
        return InsideTotalsByCandidateService(db=self.session)
