"""Allow explicit class-universe destruction of append-only history rows."""

from alembic import op
import sqlalchemy as sa


revision = "db2c3d4e5f6a"
down_revision = "da1b2c3d4e5f"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(sa.text("""
        CREATE OR REPLACE FUNCTION prevent_immutable_delete()
        RETURNS TRIGGER AS $$
        BEGIN
            IF current_setting('cth.class_universe_destroying', true) = 'on' THEN
                RETURN OLD;
            END IF;
            RAISE EXCEPTION 'This table is immutable. Deletions are not permitted. These are permanent historical records.';
        END;
        $$ LANGUAGE plpgsql;
    """))


def downgrade():
    raise NotImplementedError("Immutable history policy evolution is append-only")
