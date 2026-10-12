from civic_lantern.jobs.ingestors.candidates import CANDIDATES_INGESTION
from civic_lantern.jobs.ingestors.committees import COMMITTEES_INGESTION
from civic_lantern.jobs.ingestors.inside_totals_by_candidate import (
    INSIDE_TOTALS_INGESTION,
)
from civic_lantern.jobs.ingestors.schedule_e_totals_by_candidate import (
    SCHEDULE_E_TOTALS_INGESTION,
)
from civic_lantern.jobs.pipeline import Ingestion

# Run order: a table's foreign-key parents come first (checked by a test).
INGESTIONS: tuple[Ingestion, ...] = (
    COMMITTEES_INGESTION,
    CANDIDATES_INGESTION,
    INSIDE_TOTALS_INGESTION,
    SCHEDULE_E_TOTALS_INGESTION,
)
INGESTIONS_BY_NAME: dict[str, Ingestion] = {i.entity: i for i in INGESTIONS}

# A cycle is "ready" for the frontend once every per-cycle ingestion succeeded.
PER_CYCLE_INGESTIONS: tuple[Ingestion, ...] = tuple(
    i for i in INGESTIONS if i.per_cycle
)
DATE_WINDOW_INGESTIONS: tuple[Ingestion, ...] = tuple(
    i for i in INGESTIONS if not i.per_cycle
)
SPENDING_INGESTOR_NAMES: list[str] = [i.entity for i in PER_CYCLE_INGESTIONS]
