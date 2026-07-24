"""bootstrap migration for v2 squash baseline

Revision ID: 0001
Revises: None
Create Date: 2026-04-30

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


# ============================================================================
# IDEMPOTENCY HELPERS (REQUIRED)
# ============================================================================

def table_exists(table_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def column_exists(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        columns = [col["name"] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def index_exists(table_name, index_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        indexes = [idx["name"] for idx in inspector.get_indexes(table_name)]
        return index_name in indexes
    except Exception:
        return False


def foreign_key_exists(table_name, fk_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        fks = [fk["name"] for fk in inspector.get_foreign_keys(table_name)]
        return fk_name in fks
    except Exception:
        return False


def constraint_exists(table_name, constraint_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        constraints = [c["name"] for c in inspector.get_unique_constraints(table_name)]
        return constraint_name in constraints
    except Exception:
        return False


def get_foreign_keys_by_column(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return [
            fk for fk in inspector.get_foreign_keys(table_name)
            if column_name in fk["constrained_columns"]
        ]
    except Exception:
        return []


def _create_tables_if_missing(metadata, bind):
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())
    # Avoid metadata.sorted_tables here because the bootstrap metadata contains
    # intentional FK cycles that produce noisy SAWarnings during test setup.
    target_tables = [table for table in metadata.tables.values() if table.name not in existing]
    if target_tables:
        metadata.create_all(bind=bind, tables=target_tables, checkfirst=True)


def upgrade():
    bind = op.get_bind()

    # Section A: legacy/transitional tables
    import app.models as legacy_models
    _create_tables_if_missing(legacy_models.db.Model.metadata, bind)

    # Section B: canonical DOM-CORE-002 tables now live in the active ORM layer.
    from app import models as canonical_models
    _create_tables_if_missing(canonical_models.db.Model.metadata, bind)


def downgrade():
    # Bootstrap migration is intentionally non-destructive.
    pass
