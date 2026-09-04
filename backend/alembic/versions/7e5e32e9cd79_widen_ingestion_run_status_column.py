"""widen ingestion run status column

Revision ID: 7e5e32e9cd79
Revises: 02d6f5ea74b4
Create Date: 2026-09-04 16:01:27.472561

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7e5e32e9cd79"
down_revision: Union[str, Sequence[str], None] = "02d6f5ea74b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Widen status to fit new values (e.g. 'partial_success', 15 chars)."""
    op.alter_column(
        "ingestion_runs",
        "status",
        type_=sa.String(length=32),
        existing_type=sa.String(length=11),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Narrow status back to its original size."""
    op.alter_column(
        "ingestion_runs",
        "status",
        type_=sa.String(length=11),
        existing_type=sa.String(length=32),
        existing_nullable=False,
    )
