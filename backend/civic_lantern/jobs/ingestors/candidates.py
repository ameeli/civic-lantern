from civic_lantern.db.models.candidate import Candidate
from civic_lantern.jobs.pipeline import DateWindow, Ingestion
from civic_lantern.schemas.candidate import CandidateIn
from civic_lantern.services.fec_client import FEDERAL_OFFICES, FECEndpoint

CANDIDATES = FECEndpoint(
    name="candidates",
    path="/candidates/",
    sort=("candidate_id",),
    params={"office": FEDERAL_OFFICES},
)

CANDIDATES_INGESTION = Ingestion(
    entity="candidates",
    scope=DateWindow(min_param="min_first_file_date", max_param="max_first_file_date"),
    endpoint=CANDIDATES,
    schema=CandidateIn,
    model=Candidate,
)
