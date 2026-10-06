from civic_lantern.db.models.schedule_e_totals_by_candidate import (
    ScheduleETotalsByCandidate,
)
from civic_lantern.jobs.pipeline import Ingestion, PerCycle
from civic_lantern.schemas.schedule_e_totals_by_candidate import (
    ScheduleETotalsByCandidateIn,
)
from civic_lantern.services.fec_client import FEDERAL_OFFICES, FECEndpoint

SCHEDULE_E_TOTALS = FECEndpoint(
    name="schedule E totals by candidate",
    path="/schedules/schedule_e/totals/by_candidate/",
    # Rows are unique per (candidate_id, support_oppose_indicator) in a cycle.
    sort=("candidate_id", "support_oppose_indicator"),
    params={"office": FEDERAL_OFFICES},
    required=("cycle",),
)

SCHEDULE_E_TOTALS_INGESTION = Ingestion(
    entity="schedule_e_totals_by_candidate",
    scope=PerCycle(),
    endpoint=SCHEDULE_E_TOTALS,
    schema=ScheduleETotalsByCandidateIn,
    model=ScheduleETotalsByCandidate,
)
