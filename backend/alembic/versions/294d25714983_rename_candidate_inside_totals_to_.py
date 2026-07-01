"""rename_candidate_inside_totals_to_inside_totals_by_candidate

Revision ID: 294d25714983
Revises: 7e94b5f9c9c7
Create Date: 2026-06-30 12:11:32.707132

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "294d25714983"
down_revision: Union[str, Sequence[str], None] = "7e94b5f9c9c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.rename_table("candidate_inside_totals", "inside_totals_by_candidate")


def downgrade() -> None:
    """Downgrade schema."""
    op.rename_table("inside_totals_by_candidate", "candidate_inside_totals")
