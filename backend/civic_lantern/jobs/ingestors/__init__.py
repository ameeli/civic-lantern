from typing import Type

from civic_lantern.jobs.base_ingestor import BaseIngestor
from civic_lantern.jobs.ingestors.candidates import CandidateIngestor
from civic_lantern.jobs.ingestors.spending import SpendingIngestor

# Ordered by FK dependencies — parents before children.
# ingest_all() executes these top to bottom.
INGESTOR_REGISTRY: dict[str, Type[BaseIngestor]] = {
    "candidates": CandidateIngestor,
    "spending_totals": SpendingIngestor,
    # "committees": CommitteeIngestor,
    # "elections": ElectionIngestor,
    # "schedule_e": ScheduleEIngestor,        # after candidates, committees
    # "election_candidates": ElectionCandidateIngestor,  # last
}
