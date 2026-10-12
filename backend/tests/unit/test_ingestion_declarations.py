import pytest

from civic_lantern.db.models.candidate import Candidate
from civic_lantern.db.models.committee import Committee
from civic_lantern.db.models.inside_totals_by_candidate import InsideTotalsByCandidate
from civic_lantern.db.models.schedule_e_totals_by_candidate import (
    ScheduleETotalsByCandidate,
)
from civic_lantern.jobs.ingestors import (
    INGESTIONS,
    INGESTIONS_BY_NAME,
    PER_CYCLE_INGESTIONS,
    SPENDING_INGESTOR_NAMES,
)
from civic_lantern.jobs.ingestors.candidates import CANDIDATES
from civic_lantern.jobs.ingestors.committees import COMMITTEES
from civic_lantern.jobs.ingestors.inside_totals_by_candidate import CANDIDATE_TOTALS
from civic_lantern.jobs.ingestors.schedule_e_totals_by_candidate import (
    SCHEDULE_E_TOTALS,
)
from civic_lantern.jobs.pipeline import DateWindow, PerCycle


@pytest.mark.unit
class TestIngestionDeclarations:
    @pytest.mark.parametrize(
        "entity, endpoint, scope, model, accepts_partial",
        [
            ("committees", COMMITTEES, DateWindow, Committee, True),
            ("candidates", CANDIDATES, DateWindow, Candidate, True),
            (
                "inside_totals_by_candidate",
                CANDIDATE_TOTALS,
                PerCycle,
                InsideTotalsByCandidate,
                False,
            ),
            (
                "schedule_e_totals_by_candidate",
                SCHEDULE_E_TOTALS,
                PerCycle,
                ScheduleETotalsByCandidate,
                True,
            ),
        ],
    )
    def test_declaration(self, entity, endpoint, scope, model, accepts_partial):
        ingestion = INGESTIONS_BY_NAME[entity]

        assert ingestion.endpoint is endpoint
        assert isinstance(ingestion.scope, scope)
        assert ingestion.model is model
        assert ingestion.accepts_partial_fetch is accepts_partial

    def test_entity_names_are_unique(self):
        assert len(INGESTIONS_BY_NAME) == len(INGESTIONS)

    def test_per_cycle_ingestions_decide_readiness(self):
        assert [i.entity for i in PER_CYCLE_INGESTIONS] == SPENDING_INGESTOR_NAMES
        assert SPENDING_INGESTOR_NAMES == [
            "inside_totals_by_candidate",
            "schedule_e_totals_by_candidate",
        ]

    def test_foreign_key_parents_run_first(self):
        position = {i.model.__tablename__: n for n, i in enumerate(INGESTIONS)}
        for ingestion in INGESTIONS:
            table = ingestion.model.__table__
            for fk in table.foreign_keys:
                parent = fk.column.table.name
                if parent in position and parent != table.name:
                    assert (
                        position[parent] < position[table.name]
                    ), f"{table.name} runs before its parent {parent}"
