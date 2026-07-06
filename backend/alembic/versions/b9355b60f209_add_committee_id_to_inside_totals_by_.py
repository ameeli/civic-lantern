"""add_committee_id_to_inside_totals_by_candidate

Revision ID: b9355b60f209
Revises: 294d25714983
Create Date: 2026-07-06 14:23:17.221861

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b9355b60f209"
down_revision: Union[str, Sequence[str], None] = "294d25714983"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_table("inside_totals_by_candidate")
    op.create_table(
        "inside_totals_by_candidate",
        sa.Column("committee_id", sa.String(), nullable=False),
        sa.Column("candidate_id", sa.String(), nullable=False),
        sa.Column("cycle", sa.Integer(), nullable=False),
        sa.Column("receipts", sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column("disbursements", sa.Numeric(precision=15, scale=2), nullable=True),
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
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.candidate_id"]),
        sa.PrimaryKeyConstraint("committee_id", "candidate_id", "cycle"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("inside_totals_by_candidate")
    op.create_table(
        "inside_totals_by_candidate",
        sa.Column("candidate_id", sa.String(), nullable=False),
        sa.Column("cycle", sa.Integer(), nullable=False),
        sa.Column("receipts", sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column("disbursements", sa.Numeric(precision=15, scale=2), nullable=True),
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
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.candidate_id"]),
        sa.PrimaryKeyConstraint("candidate_id", "cycle"),
    )
