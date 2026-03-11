from typing import Type

from civic_lantern.jobs.base_ingestor import BaseIngestor
from civic_lantern.jobs.ingestors.candidate_spending import SpendingIngestor
from civic_lantern.jobs.ingestors.candidates import CandidateIngestor

# Ordered by FK dependencies — parents before children.
# ingest_all() executes these top to bottom.
INGESTOR_REGISTRY: dict[str, Type[BaseIngestor]] = {
    "candidates": CandidateIngestor,
    "candidate_spending": SpendingIngestor,
    # "committees": CommitteeIngestor,
    # "elections": ElectionIngestor,
    # "schedule_e": ScheduleEIngestor,        # after candidates, committees
    # "election_candidates": ElectionCandidateIngestor,  # last
}
