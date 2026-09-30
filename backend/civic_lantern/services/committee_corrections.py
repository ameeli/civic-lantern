"""Corrections for committees FEC's /candidates/totals/ misattributes.

fetch_inputs() gets the committee totals and reports the corrections need;
apply() is pure and turns raw /candidates/totals/ rows into corrected rows.
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Sequence

from civic_lantern.services.fec_client import FECClient

logger = logging.getLogger(__name__)

Row = Dict[str, Any]


@dataclass(frozen=True)
class CommitteeOverride:
    """A committee /candidates/totals/ drops once redesignated after a campaign;
    its own totals are added to the candidate's."""

    candidate_id: str
    cycle: int
    committee_id: str


@dataclass(frozen=True)
class CommitteeSplit:
    """A committee redesignated mid-cycle, whose full total FEC gives both
    candidates; it is apportioned between them at split_date instead."""

    committee_id: str
    cycle: int
    before_candidate_id: str
    after_candidate_id: str
    split_date: date  # first day attributed to after_candidate_id


# Stopgap until committees resolve via /candidate/{id}/committees/history/.
KNOWN_COMMITTEE_OVERRIDES: tuple[CommitteeOverride, ...] = (
    # Trump's 2024 committee, now the "NEVER SURRENDER, INC." Leadership PAC:
    # $495,853,270.30 receipts / $471,501,651.83 disbursements.
    CommitteeOverride("P80001571", 2024, "C00828541"),
    # Harris's solo committee; the split below excludes her raw row, so add it
    # back here: $0 receipts / $69,741.02 disbursements.
    CommitteeOverride("P00009423", 2024, "C00694455"),
)

KNOWN_COMMITTEE_SPLITS: tuple[CommitteeSplit, ...] = (
    # Biden -> Harris. split_date per FEC Statement of Organization amendment
    # file_number 1805326 (FEC has no effective-date field).
    CommitteeSplit("C00703975", 2024, "P80000722", "P00009423", date(2024, 7, 21)),
)


class CommitteeSplitDataError(RuntimeError):
    """A split committee returned no most_recent reports; raised rather than
    writing zero rows over good data."""


@dataclass(frozen=True)
class CorrectionInputs:
    """FEC rows the corrections need, keyed by committee_id."""

    committee_totals: Dict[str, List[Row]] = field(default_factory=dict)
    committee_reports: Dict[str, List[Row]] = field(default_factory=dict)


class CommitteeCorrections:
    """Applies committee overrides and splits to raw /candidates/totals/ rows."""

    def __init__(
        self,
        overrides: Sequence[CommitteeOverride] = KNOWN_COMMITTEE_OVERRIDES,
        splits: Sequence[CommitteeSplit] = KNOWN_COMMITTEE_SPLITS,
    ) -> None:
        self.overrides = tuple(overrides)
        self.splits = tuple(splits)

    async def fetch_inputs(self, client: FECClient, cycle: int) -> CorrectionInputs:
        """Fetch totals for this cycle's override committees and reports for
        its split committees."""
        inputs = CorrectionInputs()
        for override in self._overrides_for(cycle):
            inputs.committee_totals[override.committee_id] = (
                await client.get_committee_totals(override.committee_id, cycle=cycle)
            )
        for split in self._splits_for(cycle):
            inputs.committee_reports[split.committee_id] = (
                await client.get_committee_reports(split.committee_id, cycle=cycle)
            )
        return inputs

    def apply(
        self, raw_totals: List[Row], cycle: int, inputs: CorrectionInputs
    ) -> List[Row]:
        """Return corrected rows shaped like /candidates/totals/ output, for the
        transform to sum per (candidate_id, cycle). Doesn't mutate raw_totals.

        Raises CommitteeSplitDataError if a split committee has no usable reports.
        """
        rows = self._exclude_split_candidates(raw_totals, cycle)
        rows.extend(self._override_rows(cycle, inputs))
        for split in self._splits_for(cycle):
            reports = inputs.committee_reports.get(split.committee_id, [])
            rows.extend(_split_rows(split, reports))
        return rows

    def _overrides_for(self, cycle: int) -> List[CommitteeOverride]:
        return [o for o in self.overrides if o.cycle == cycle]

    def _splits_for(self, cycle: int) -> List[CommitteeSplit]:
        return [s for s in self.splits if s.cycle == cycle]

    def _exclude_split_candidates(self, raw: List[Row], cycle: int) -> List[Row]:
        """Drop FEC's duplicated rows for split candidates; the split replaces them."""
        excluded_ids = {
            candidate_id
            for split in self._splits_for(cycle)
            for candidate_id in (split.before_candidate_id, split.after_candidate_id)
        }
        filtered = [r for r in raw if r.get("candidate_id") not in excluded_ids]
        dropped = len(raw) - len(filtered)
        if dropped:
            logger.info(
                f"Excluded {dropped} raw row(s) for split-committee candidates "
                f"{sorted(excluded_ids)} in cycle {cycle}; replaced with "
                f"computed per-period splits."
            )
        return filtered

    def _override_rows(self, cycle: int, inputs: CorrectionInputs) -> List[Row]:
        return [
            {
                "candidate_id": override.candidate_id,
                "cycle": cycle,
                "receipts": total.get("receipts"),
                "disbursements": total.get("disbursements"),
            }
            for override in self._overrides_for(cycle)
            for total in inputs.committee_totals.get(override.committee_id, [])
        ]


def _split_rows(split: CommitteeSplit, reports: List[Row]) -> List[Row]:
    """One row per split candidate from most_recent reports, bucketed at
    split_date with the straddling period prorated by day."""
    authoritative = [r for r in reports if r.get("most_recent")]
    if not authoritative:
        raise CommitteeSplitDataError(
            f"No most_recent reports returned for split committee "
            f"{split.committee_id} cycle {split.cycle}; refusing to guess totals."
        )

    # Keep the first most_recent report per period so none is summed twice.
    by_period: Dict[tuple, Row] = {}
    for r in authoritative:
        key = (r.get("coverage_start_date"), r.get("coverage_end_date"))
        if key in by_period:
            logger.warning(
                f"Multiple most_recent reports for {split.committee_id} "
                f"period {key}; keeping first, ignoring rest."
            )
            continue
        by_period[key] = r

    before = {"receipts": 0.0, "disbursements": 0.0}
    after = {"receipts": 0.0, "disbursements": 0.0}
    straddling_count = 0

    for (start_raw, end_raw), report in by_period.items():
        start = datetime.fromisoformat(start_raw).date()
        end = datetime.fromisoformat(end_raw).date()
        amounts = {
            "receipts": float(report.get("total_receipts_period") or 0),
            "disbursements": float(report.get("total_disbursements_period") or 0),
        }

        if end < split.split_date:
            before_share, after_share = 1.0, 0.0
        elif start >= split.split_date:
            before_share, after_share = 0.0, 1.0
        else:
            straddling_count += 1
            total_days = (end - start).days + 1
            before_days = (split.split_date - start).days
            before_share = before_days / total_days
            after_share = (total_days - before_days) / total_days

        for name, amount in amounts.items():
            before[name] += amount * before_share
            after[name] += amount * after_share

    if straddling_count > 1:
        logger.warning(
            f"{straddling_count} straddling reports for {split.committee_id} "
            f"split at {split.split_date}; expected at most 1."
        )

    return [
        {"candidate_id": split.before_candidate_id, "cycle": split.cycle, **before},
        {"candidate_id": split.after_candidate_id, "cycle": split.cycle, **after},
    ]
