from civic_lantern.db.models.inside_totals_by_candidate import InsideTotalsByCandidate
from civic_lantern.jobs.pipeline import Ingestion, PerCycle
from civic_lantern.schemas.inside_totals_by_candidate import InsideTotalsByCandidateIn
from civic_lantern.services.committee_corrections import CommitteeCorrections
from civic_lantern.services.fec_client import FEDERAL_OFFICES, FECEndpoint

CANDIDATE_TOTALS = FECEndpoint(
    name="candidate totals",
    path="/candidates/totals/",
    sort=("candidate_id",),
    params={"election_full": "false", "office": FEDERAL_OFFICES},
    required=("cycle",),
)

INSIDE_TOTALS_INGESTION = Ingestion(
    entity="inside_totals_by_candidate",
    scope=PerCycle(),
    endpoint=CANDIDATE_TOTALS,
    schema=InsideTotalsByCandidateIn,
    model=InsideTotalsByCandidate,
    corrections=CommitteeCorrections(),
    # Correction rows are added alongside FEC's own row for the same candidate.
    sum_duplicates=("receipts", "disbursements"),
)
