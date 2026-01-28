"""Fix ghost update updated_at trigger function

Revision ID: ff298162850a
Revises: 21f7883d92fe
Create Date: 2026-01-28 12:37:39.345444

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ff298162850a"
down_revision: Union[str, Sequence[str], None] = "21f7883d92fe"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("""
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS trigger AS $$
        BEGIN
            IF (
                NEW IS DISTINCT FROM OLD
                AND NEW.updated_at = OLD.updated_at
            ) THEN
                NEW.updated_at = NOW();
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("""
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS trigger AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
