"""add_mv_candidate_spending_summary

Revision ID: 42cbb893c751
Revises: e18c8bee33d0
Create Date: 2026-07-08 15:10:14.132951

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "42cbb893c751"
down_revision: Union[str, Sequence[str], None] = "e18c8bee33d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("""
        CREATE MATERIALIZED VIEW mv_candidate_spending_summary AS
        WITH inside AS (
            SELECT candidate_id, cycle,
                SUM(receipts)      AS inside_receipts,
                SUM(disbursements) AS inside_disbursements
            FROM inside_totals_by_candidate
            GROUP BY candidate_id, cycle
        ),
        outside AS (
            SELECT candidate_id, cycle,
                SUM(CASE WHEN support_oppose_indicator = 'S' THEN total ELSE 0 END) AS outside_support,
                SUM(CASE WHEN support_oppose_indicator = 'O' THEN total ELSE 0 END) AS outside_oppose
            FROM schedule_e_totals_by_candidate
            GROUP BY candidate_id, cycle
        ),
        all_pairs AS (
            SELECT candidate_id, cycle FROM inside
            UNION
            SELECT candidate_id, cycle FROM outside
        )
        SELECT
            ap.candidate_id,
            ap.cycle,
            COALESCE(i.inside_receipts, 0)      AS inside_receipts,
            COALESCE(i.inside_disbursements, 0) AS inside_disbursements,
            COALESCE(o.outside_support, 0)      AS outside_support,
            COALESCE(o.outside_oppose, 0)       AS outside_oppose,
            ROUND(
                (COALESCE(o.outside_support, 0) + COALESCE(o.outside_oppose, 0)) /
                NULLIF(COALESCE(i.inside_disbursements, 0), 0), 2
            ) AS influence_ratio,
            ROUND(
                COALESCE(o.outside_oppose, 0) /
                NULLIF(COALESCE(i.inside_disbursements, 0), 0), 2
            ) AS vulnerability_factor
        FROM all_pairs ap
        LEFT JOIN inside i  ON ap.candidate_id = i.candidate_id AND ap.cycle = i.cycle
        LEFT JOIN outside o ON ap.candidate_id = o.candidate_id AND ap.cycle = o.cycle;
    """)

    op.execute("""
        CREATE UNIQUE INDEX idx_mv_candidate_spending_summary_pk
        ON mv_candidate_spending_summary (candidate_id, cycle);
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_candidate_spending_summary")
