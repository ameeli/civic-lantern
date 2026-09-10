from enum import Enum

from sqlalchemy import Column, DateTime, Index, Integer, String, Text
from sqlalchemy import Enum as SQLEnum

from civic_lantern.db.models.base import Base, enum_values_callable
from civic_lantern.db.models.mixins import TimestampMixin


class IngestionRunStatus(str, Enum):
    """Status of a single ingestor run, tracked per (ingestor_name, cycle)."""

    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class IngestionRun(Base, TimestampMixin):
    """Tracks the latest ingestion attempt per (ingestor_name, cycle).

    `cycle` is null for date-windowed ingestors (candidates, committees), which
    resume from `last_run_completed_at` as a watermark. It is set for the two
    cycle-scoped spending ingestors, where a successful row also marks that
    cycle as "ready" for the frontend.

    PARTIAL_SUCCESS means the ingestor still upserted whatever data it
    managed to fetch/write cleanly (a few bad pages or rows don't block the
    rest of a large pull) but `last_run_completed_at` is deliberately left
    untouched — so a date-windowed ingestor resumes over the same gap next
    run instead of silently skipping past it, and a cycle-scoped ingestor
    isn't reported as "ready" on incomplete data.

    Rendered as VARCHAR + CHECK (native_enum=False) rather than a native
    Postgres enum: this status is internal bookkeeping expected to grow new
    values (e.g. "skipped"), and native enums require an ALTER TYPE migration
    per new value — a deliberate deviation from this codebase's convention of
    native enums for FEC-defined coding schemes.
    """

    __tablename__ = "ingestion_runs"
    __table_args__ = (
        Index(
            "uq_ingestion_runs_name_cycle",
            "ingestor_name",
            "cycle",
            unique=True,
            postgresql_where=Column("cycle").isnot(None),
        ),
        Index(
            "uq_ingestion_runs_name_null_cycle",
            "ingestor_name",
            unique=True,
            postgresql_where=Column("cycle").is_(None),
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    ingestor_name = Column(String, nullable=False)
    cycle = Column(Integer, nullable=True)
    status = Column(
        SQLEnum(
            IngestionRunStatus,
            name="ingestion_run_status_enum",
            values_callable=enum_values_callable,
            native_enum=False,
            length=32,
        ),
        nullable=False,
    )
    started_at = Column(DateTime(timezone=True), nullable=False)
    last_run_completed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<IngestionRun(ingestor_name='{self.ingestor_name}', "
            f"cycle={self.cycle}, status={self.status})>"
        )
