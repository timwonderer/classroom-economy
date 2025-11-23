"""Merge demo_students, hall_pass_models, and production merge heads

This merge migration resolves multiple heads created by parallel work on:
- e7f8g9h0i1j2: merge of production and insurance branches
- c4d5e6f7g8h9: demo_students table introduction
- f5a1e3e4d7c8: hall pass models

Revision ID: m2n3o4p5q6r7
Revises: e7f8g9h0i1j2, c4d5e6f7g8h9, f5a1e3e4d7c8
Create Date: 2025-11-24 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'm2n3o4p5q6r7'
down_revision = ('e7f8g9h0i1j2', 'c4d5e6f7g8h9', 'f5a1e3e4d7c8')
branch_labels = None
depends_on = None


def upgrade():
    # Merge migration; no schema changes required.
    pass


def downgrade():
    # Merge migration; no schema changes required.
    pass
