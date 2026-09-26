from datetime import date, datetime
from typing import Any, Dict, List

from civic_lantern.jobs.base_ingestor import BaseIngestor
from civic_lantern.services.data.inside_totals_by_candidate import (
    InsideTotalsByCandidateService,
)
from civic_lantern.utils.transformers import transform_inside_totals_by_candidate

# Committees /candidates/totals/ drops once redesignated after a campaign. Stopgap
# until committees resolve via /candidate/{id}/committees/history/; then remove.
KNOWN_COMMITTEE_OVERRIDES: Dict[tuple, List[str]] = {
    # Trump's 2024 committee, now the "NEVER SURRENDER, INC." Leadership PAC:
    # $495,853,270.30 receipts / $471,501,651.83 disbursements.
    ("P80001571", 2024): ["C00828541"],
    # Harris's solo committee; the split below excludes her raw row, so add it
    # back here: $0 receipts / $69,741.02 disbursements.
    ("P00009423", 2024): ["C00694455"],
}

# Committees redesignated mid-cycle, whose full total FEC gives both candidates.
# Their raw rows are replaced by /reports/ totals split at split_date (one split).
KNOWN_COMMITTEE_SPLITS: Dict[tuple, Dict[str, Any]] = {
    ("C00703975", 2024): {
        "before_candidate_id": "P80000722",  # Joseph Biden
        "after_candidate_id": "P00009423",  # Kamala Harris
        # First Harris day: redesignation per FEC Statement of Organization
        # amendment file_number 1805326 (FEC has no effective-date field).
        "split_date": date(2024, 7, 21),
    },
}


class CommitteeSplitDataError(RuntimeError):
    """A split committee returned no most_recent reports; raised rather than
    writing zero rows over good data."""


class InsideTotalsByCandidateIngestor(BaseIngestor):
    """Ingests candidate inside spending totals from /candidates/totals/."""

    entity_name = "inside_totals_by_candidate"

    # Rows sum several FEC calls, so a partial fetch would write wrong totals.
    accepts_partial_fetch = False

    # Narrower than the base **kwargs; IngestionManager always passes `cycle`.
    async def fetch(  # type: ignore[override]
        self, cycle: int, **kwargs: Any
    ) -> List[Dict[str, Any]]:
        """Fetch inside spending totals for all candidates in the given cycle."""
        raw = await self.client.get_candidate_totals(cycle=cycle, **kwargs)
        raw = self._exclude_split_candidates(raw, cycle)
        raw.extend(await self._fetch_overrides(cycle))
        raw.extend(await self._fetch_splits(cycle))
        return raw

    def _exclude_split_candidates(
        self, raw: List[Dict[str, Any]], cycle: int
    ) -> List[Dict[str, Any]]:
        """Drop FEC's duplicated split-candidate rows; _fetch_splits replaces them."""
        excluded_ids = {
            candidate_id
            for (_, split_cycle), split in KNOWN_COMMITTEE_SPLITS.items()
            if split_cycle == cycle
            for candidate_id in (
                split["before_candidate_id"],
                split["after_candidate_id"],
            )
        }
        if not excluded_ids:
            return raw

        filtered = [r for r in raw if r.get("candidate_id") not in excluded_ids]
        dropped = len(raw) - len(filtered)
        if dropped:
            self.logger.info(
                f"Excluded {dropped} raw row(s) for split-committee candidates "
                f"{sorted(excluded_ids)} in cycle {cycle}; replaced with "
                f"computed per-period splits."
            )
        return filtered

    async def _fetch_splits(self, cycle: int) -> List[Dict[str, Any]]:
        """One row per split candidate from most_recent /reports/, bucketed at
        split_date with the straddling period prorated by day."""
        rows: List[Dict[str, Any]] = []
        for (committee_id, split_cycle), split in KNOWN_COMMITTEE_SPLITS.items():
            if split_cycle != cycle:
                continue

            reports = await self.client.get_committee_reports(committee_id, cycle=cycle)
            authoritative = [r for r in reports if r.get("most_recent")]
            if not authoritative:
                raise CommitteeSplitDataError(
                    f"No most_recent reports returned for split committee "
                    f"{committee_id} cycle {cycle}; refusing to guess totals."
                )

            # Keep the first most_recent report per period so none is summed twice.
            by_period: Dict[tuple, Dict[str, Any]] = {}
            for r in authoritative:
                key = (r.get("coverage_start_date"), r.get("coverage_end_date"))
                if key in by_period:
                    self.logger.warning(
                        f"Multiple most_recent reports for {committee_id} "
                        f"period {key}; keeping first, ignoring rest."
                    )
                    continue
                by_period[key] = r

            split_date = split["split_date"]
            before_totals = {"receipts": 0.0, "disbursements": 0.0}
            after_totals = {"receipts": 0.0, "disbursements": 0.0}
            straddling_count = 0

            for (start_raw, end_raw), report in by_period.items():
                start = datetime.fromisoformat(start_raw).date()
                end = datetime.fromisoformat(end_raw).date()
                receipts = float(report.get("total_receipts_period") or 0)
                disbursements = float(report.get("total_disbursements_period") or 0)

                if end < split_date:
                    before_totals["receipts"] += receipts
                    before_totals["disbursements"] += disbursements
                elif start >= split_date:
                    after_totals["receipts"] += receipts
                    after_totals["disbursements"] += disbursements
                else:
                    straddling_count += 1
                    total_days = (end - start).days + 1
                    before_days = (split_date - start).days
                    after_days = total_days - before_days
                    before_share = before_days / total_days
                    after_share = after_days / total_days

                    before_totals["receipts"] += receipts * before_share
                    before_totals["disbursements"] += disbursements * before_share
                    after_totals["receipts"] += receipts * after_share
                    after_totals["disbursements"] += disbursements * after_share

            if straddling_count > 1:
                self.logger.warning(
                    f"{straddling_count} straddling reports for {committee_id} "
                    f"split at {split_date}; expected at most 1."
                )

            rows.append(
                {
                    "candidate_id": split["before_candidate_id"],
                    "cycle": cycle,
                    "receipts": before_totals["receipts"],
                    "disbursements": before_totals["disbursements"],
                }
            )
            rows.append(
                {
                    "candidate_id": split["after_candidate_id"],
                    "cycle": cycle,
                    "receipts": after_totals["receipts"],
                    "disbursements": after_totals["disbursements"],
                }
            )
        return rows

    async def _fetch_overrides(self, cycle: int) -> List[Dict[str, Any]]:
        """Rows shaped like /candidates/totals/ for KNOWN_COMMITTEE_OVERRIDES,
        which the transform sums with FEC's own row for that candidate."""
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
