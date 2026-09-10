from datetime import date, datetime
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
    # Harris's solo committee ("KAMALA HARRIS FOR THE PEOPLE"), separate
    # from the C00703975 committee she shares with Biden (see
    # KNOWN_COMMITTEE_SPLITS below). Her entire raw /candidates/totals/ row
    # for 2024 is excluded by _exclude_split_candidates (it's the shared
    # committee's duplicated total), so this committee's own activity must
    # be patched back in here or it silently disappears. Verified via
    # /committee/C00694455/totals/: $0 receipts / $69,741.02 disbursements
    # for cycle 2024.
    ("P00009423", 2024): ["C00694455"],
}

# FEC's /candidates/totals/ attributes a committee's FULL cycle total to
# EVERY candidate_id it has ever been linked to in that cycle (its
# candidate_ids array keeps historical entries) — when a committee is
# redesignated from one candidate to another mid-cycle, both candidates get
# the entire amount, double-counting it.
#
# This is a manual, per-committee stopgap for known cases. Each entry's
# `before_candidate_id`/`after_candidate_id` rows are excluded from the raw
# /candidates/totals/ fetch (see _exclude_split_candidates) and replaced
# with per-period totals computed from the committee's own /reports/
# endpoint, apportioned at `split_date` (see _fetch_splits). Supports
# exactly one split date per committee/cycle between two candidates — not a
# generalized N-way split — since that's the only known case today.
KNOWN_COMMITTEE_SPLITS: Dict[tuple, Dict[str, Any]] = {
    ("C00703975", 2024): {
        "before_candidate_id": "P80000722",  # Joseph Biden
        "after_candidate_id": "P00009423",  # Kamala Harris
        # First day attributed to after_candidate_id. Committee was
        # registered as "Biden for President", redesignated "Harris for
        # President" the day Biden withdrew and endorsed Harris, per FEC
        # Statement of Organization amendment (file_number 1805326)
        # timestamped 2024-07-21 — the best available authoritative signal
        # for an effective date (FEC has no structured "effective date"
        # field for redesignations). Renamed again post-election to
        # "Fight for the People PAC"; irrelevant here since only the
        # 2024-cycle activity is attributed.
        "split_date": date(2024, 7, 21),
    },
}


class CommitteeSplitDataError(RuntimeError):
    """Raised when a KNOWN_COMMITTEE_SPLITS entry's committee doesn't return
    usable report data for a cycle (e.g. zero reports, or none flagged
    most_recent). Raised rather than silently falling back to zero-value
    rows, which would look like valid data and could clobber good
    historical rows on a re-run."""


class InsideTotalsByCandidateIngestor(BaseIngestor):
    """Ingests candidate inside spending totals from /candidates/totals/."""

    entity_name = "inside_totals_by_candidate"

    async def fetch(self, cycle: int, **kwargs: Any) -> List[Dict[str, Any]]:
        """Fetch inside spending totals for all candidates in the given cycle."""
        raw = await self.client.get_candidate_totals(cycle=cycle, **kwargs)
        raw = self._exclude_split_candidates(raw, cycle)
        raw.extend(await self._fetch_overrides(cycle))
        raw.extend(await self._fetch_splits(cycle))
        return raw

    def _exclude_split_candidates(
        self, raw: List[Dict[str, Any]], cycle: int
    ) -> List[Dict[str, Any]]:
        """Strip FEC's own (duplicated) rows for candidates covered by
        KNOWN_COMMITTEE_SPLITS in this cycle, so _fetch_splits's computed
        rows are the only source of truth for those candidate_ids."""
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
        """Patch in per-candidate totals for committees redesignated mid-cycle
        between two candidates, which FEC's own totals endpoint
        double-counts. See KNOWN_COMMITTEE_SPLITS.

        Fetches each configured committee's periodic /reports/, keeps only
        the most_recent version of each coverage period, buckets whole
        periods before/after split_date, and prorates the one period that
        straddles split_date by calendar day count. Emits two synthetic
        rows shaped like /candidates/totals/ output, one per candidate, so
        the existing transform's per-(candidate_id, cycle) summation picks
        them up exactly like _fetch_overrides's rows.
        """
        rows: List[Dict[str, Any]] = []
        for (committee_id, split_cycle), split in KNOWN_COMMITTEE_SPLITS.items():
            if split_cycle != cycle:
                continue

            reports = await self.client.get_committee_reports(
                committee_id, cycle=cycle
            )
            authoritative = [r for r in reports if r.get("most_recent")]
            if not authoritative:
                raise CommitteeSplitDataError(
                    f"No most_recent reports returned for split committee "
                    f"{committee_id} cycle {cycle}; refusing to guess totals."
                )

            # Defensive dedupe: keep first most_recent row per coverage
            # period, warn if FEC ever marks more than one as most_recent
            # for the same period (shouldn't happen, but don't silently
            # double-sum if it does).
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
