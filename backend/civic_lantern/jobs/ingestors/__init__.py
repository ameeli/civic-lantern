from typing import Type

from civic_lantern.jobs.base_ingestor import BaseIngestor
from civic_lantern.jobs.ingestors.candidates import CandidateIngestor
from civic_lantern.jobs.ingestors.committees import CommitteeIngestor
from civic_lantern.jobs.ingestors.inside_totals_by_candidate import (
    InsideTotalsByCandidateIngestor,
)
from civic_lantern.jobs.ingestors.schedule_e_totals_by_candidate import (
    ScheduleETotalsByCandidateIngestor,
)

# Ordered by FK dependencies — parents before children.
# ingest_all() executes these top to bottom.
INGESTOR_REGISTRY: dict[str, Type[BaseIngestor]] = {
    "committees": CommitteeIngestor,
    "candidates": CandidateIngestor,
    "inside_totals_by_candidate": InsideTotalsByCandidateIngestor,
    "schedule_e_totals_by_candidate": ScheduleETotalsByCandidateIngestor,
}

# Canonical list of cycle-scoped spending ingestors — a cycle only counts as
# "ready" (for the frontend cycle selector) once every one of these has
# succeeded for it. Single source of truth for both the nightly manager's
# per-cycle loop and the readiness endpoint.
SPENDING_INGESTOR_NAMES: list[str] = [
    "inside_totals_by_candidate",
    "schedule_e_totals_by_candidate",
]
