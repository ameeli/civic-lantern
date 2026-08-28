"""add_ingestion_runs

Revision ID: 02d6f5ea74b4
Revises: 4fe052547c61
Create Date: 2026-08-28 14:36:33.405375

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "02d6f5ea74b4"
down_revision: Union[str, Sequence[str], None] = "4fe052547c61"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ingestor_name", sa.String(), nullable=False),
        sa.Column("cycle", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "in_progress",
                "success",
                "failed",
                name="ingestion_run_status_enum",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_run_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_ingestion_runs_name_cycle",
        "ingestion_runs",
        ["ingestor_name", "cycle"],
        unique=True,
        postgresql_where=sa.text("cycle IS NOT NULL"),
    )
    op.create_index(
        "uq_ingestion_runs_name_null_cycle",
        "ingestion_runs",
        ["ingestor_name"],
        unique=True,
        postgresql_where=sa.text("cycle IS NULL"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "uq_ingestion_runs_name_null_cycle",
        table_name="ingestion_runs",
        postgresql_where=sa.text("cycle IS NULL"),
    )
    op.drop_index(
        "uq_ingestion_runs_name_cycle",
        table_name="ingestion_runs",
        postgresql_where=sa.text("cycle IS NOT NULL"),
    )
    op.drop_table("ingestion_runs")
