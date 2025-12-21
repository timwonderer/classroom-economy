"""add last_name_hash_by_part for fuzzy name matching

Revision ID: e1f2a3b4c5d6
Revises: d8e9f0a1b2c3
Create Date: 2025-11-22 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'e1f2a3b4c5d6'
down_revision = 'd8e9f0a1b2c3'
branch_labels = None
depends_on = None


def upgrade():
    # Add last_name_hash_by_part column to students table
    # Stores JSON array of hashes for each part of the last name
    # Example: "Smith-Jones" → ["hash(smith)", "hash(jones)"]
    op.add_column('students',
        sa.Column('last_name_hash_by_part',
                  postgresql.JSON(astext_type=sa.Text()),
                  nullable=True))

    # Note: Existing students will have NULL values
    # This is OK - backfill can be done on-demand when they claim/update


def downgrade():
    op.drop_column('students', 'last_name_hash_by_part')
