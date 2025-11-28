"""Merge feature settings and insurance tiers heads

This merge migration consolidates two parallel development branches:
- 309f41417005: Merge insurance tiers and marketing badge branches
- z2a3b4c5d6e7: Add FeatureSettings and TeacherOnboarding models

Revision ID: f9fbd037a0f1
Revises: 309f41417005, z2a3b4c5d6e7
Create Date: 2025-11-28

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f9fbd037a0f1'
down_revision = ('309f41417005', 'z2a3b4c5d6e7')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
