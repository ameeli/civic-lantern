"""drop_candidate_spending_totals

Revision ID: 4fe052547c61
Revises: 307f6cb417c7
Create Date: 2026-07-10 14:17:10.191163

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4fe052547c61"
down_revision: Union[str, Sequence[str], None] = "307f6cb417c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_table("candidate_spending_totals")


def downgrade() -> None:
    """Downgrade schema."""
    op.create_table(
        "candidate_spending_totals",
        sa.Column("candidate_id", sa.String(), nullable=False),
        sa.Column("cycle", sa.Integer(), nullable=False),
        sa.Column("inside_receipts", sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column(
            "inside_disbursements", sa.Numeric(precision=15, scale=2), nullable=True
        ),
        sa.Column("outside_support", sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column("outside_oppose", sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column("influence_ratio", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column(
            "vulnerability_factor", sa.Numeric(precision=10, scale=2), nullable=True
        ),
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
