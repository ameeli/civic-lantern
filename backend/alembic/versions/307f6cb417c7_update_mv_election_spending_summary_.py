"""update_mv_election_spending_summary_source

Revision ID: 307f6cb417c7
Revises: 42cbb893c751
Create Date: 2026-07-08 15:19:54.254789

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "307f6cb417c7"
down_revision: Union[str, Sequence[str], None] = "42cbb893c751"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_election_spending_summary")

    op.execute("""
        CREATE MATERIALIZED VIEW mv_election_spending_summary AS
        SELECT
            cycle,
            COUNT(DISTINCT candidate_id)           AS candidate_count,
            SUM(inside_receipts)                   AS total_inside_receipts,
            SUM(inside_disbursements)              AS total_inside_disbursements,
            SUM(outside_support)                   AS total_outside_support,
            SUM(outside_oppose)                    AS total_outside_oppose,
            ROUND(
                SUM(outside_support + outside_oppose) /
                NULLIF(SUM(inside_disbursements), 0), 2
            ) AS global_influence_ratio
        FROM mv_candidate_spending_summary
        GROUP BY cycle;
    """)

    op.execute("""
        CREATE UNIQUE INDEX idx_spending_summary_cycle
        ON mv_election_spending_summary (cycle);
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_election_spending_summary")

    op.execute("""
        CREATE MATERIALIZED VIEW mv_election_spending_summary AS
        SELECT
            cycle,
            COUNT(DISTINCT candidate_id)           AS candidate_count,
            SUM(inside_receipts)                   AS total_inside_receipts,
            SUM(inside_disbursements)              AS total_inside_disbursements,
            SUM(outside_support)                   AS total_outside_support,
            SUM(outside_oppose)                    AS total_outside_oppose,
            ROUND(
                SUM(outside_support + outside_oppose) /
                NULLIF(SUM(inside_disbursements), 0), 2
            ) AS global_influence_ratio
        FROM candidate_spending_totals
        GROUP BY cycle;
    """)

    op.execute("""
        CREATE UNIQUE INDEX idx_spending_summary_cycle
        ON mv_election_spending_summary (cycle);
    """)
