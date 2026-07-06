from typing import Type

from civic_lantern.jobs.base_ingestor import BaseIngestor
from civic_lantern.jobs.ingestors.candidate_spending import SpendingIngestor
from civic_lantern.jobs.ingestors.candidates import CandidateIngestor
from civic_lantern.jobs.ingestors.committees import CommitteeIngestor
from civic_lantern.jobs.ingestors.inside_totals_by_candidate import (
    InsideTotalsByCandidateIngestor,
)

# Ordered by FK dependencies — parents before children.
# ingest_all() executes these top to bottom.
INGESTOR_REGISTRY: dict[str, Type[BaseIngestor]] = {
    "committees": CommitteeIngestor,
    "candidates": CandidateIngestor,
    "inside_totals_by_candidate": InsideTotalsByCandidateIngestor,
    "candidate_spending": SpendingIngestor,
    # "elections": ElectionIngestor,
    # "schedule_e": ScheduleEIngestor,        # after candidates, committees
    # "election_candidates": ElectionCandidateIngestor,  # last
}
