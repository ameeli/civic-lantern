"""add spending summary mv

Revision ID: 0c95890efc66
Revises: 8dec5034fb0f
Create Date: 2026-03-06 12:08:00.372707

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0c95890efc66"
down_revision: Union[str, Sequence[str], None] = "8dec5034fb0f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("""
        CREATE MATERIALIZED VIEW mv_election_spending_summary AS
        SELECT
            cycle,
            COUNT(DISTINCT candidate_id) as candidate_count,
            SUM(inside_receipts) as total_inside_receipts,
            SUM(inside_disbursements) as total_inside_disbursements,
            SUM(outside_support) as total_outside_support,
            SUM(outside_oppose) as total_outside_oppose,
            ROUND(
                SUM(outside_support + outside_oppose) /
                NULLIF(SUM(inside_disbursements), 0),
                2
            ) as global_influence_ratio
        FROM candidate_spending_totals
        GROUP BY cycle;
    """)

    op.execute("""
        CREATE UNIQUE INDEX idx_spending_summary_cycle
        ON mv_election_spending_summary (cycle);
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_election_spending_summary")
