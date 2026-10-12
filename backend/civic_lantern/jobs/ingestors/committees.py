from civic_lantern.db.models.committee import Committee
from civic_lantern.jobs.pipeline import DateWindow, Ingestion
from civic_lantern.schemas.committee import CommitteeIn
from civic_lantern.services.fec_client import FECEndpoint

COMMITTEES = FECEndpoint(name="committees", path="/committees/", sort=("committee_id",))

COMMITTEES_INGESTION = Ingestion(
    entity="committees",
    scope=DateWindow(min_param="min_first_file_date", max_param="max_first_file_date"),
    endpoint=COMMITTEES,
    schema=CommitteeIn,
    model=Committee,
)
