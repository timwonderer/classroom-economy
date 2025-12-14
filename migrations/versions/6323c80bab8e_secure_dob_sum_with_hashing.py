"""Secure dob_sum with hashing

Revision ID: 6323c80bab8e
Revises: a7b8c9d0e1f2
Create Date: 2025-12-14 21:44:54.163673

"""
from alembic import op
import sqlalchemy as sa
import secrets
import hmac
import hashlib
import os

# revision identifiers, used by Alembic.
revision = '6323c80bab8e'
down_revision = 'a7b8c9d0e1f2'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Add new columns
    with op.batch_alter_table('admins', schema=None) as batch_op:
        batch_op.add_column(sa.Column('dob_sum_hash', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('salt', sa.LargeBinary(length=16), nullable=True))

    with op.batch_alter_table('recovery_requests', schema=None) as batch_op:
        batch_op.add_column(sa.Column('dob_sum_hash', sa.String(length=64), nullable=True))

    # 2. Data Migration
    # Get connection
    bind = op.get_bind()

    # Migrate Admins
    # We use reflection to get the table definition as it exists in DB
    # Note: We must ensure we can access 'dob_sum' which still exists
    try:
        admins_table = sa.Table('admins', sa.MetaData(), autoload_with=bind)

        # Select id and dob_sum
        # Check if dob_sum exists in the table columns
        if 'dob_sum' in admins_table.c:
            results = bind.execute(sa.select(admins_table.c.id, admins_table.c.dob_sum)).fetchall()

            pepper_str = os.environ.get('PEPPER_KEY')
            if pepper_str:
                pepper = pepper_str.encode()

                for admin_id, dob_sum_val in results:
                    if dob_sum_val:
                        salt = secrets.token_bytes(16)
                        # Hash: hmac(pepper, salt + str(dob_sum), sha256)
                        dob_sum_str = str(dob_sum_val).encode()
                        h = hmac.new(pepper, salt + dob_sum_str, hashlib.sha256).hexdigest()

                        # Update record
                        bind.execute(
                            admins_table.update().where(admins_table.c.id == admin_id).values(
                                dob_sum_hash=h,
                                salt=salt
                            )
                        )
    except Exception as e:
        print(f"Warning: Data migration failed: {e}")

    # 3. Drop old columns
    with op.batch_alter_table('admins', schema=None) as batch_op:
        # Check if column exists before dropping to avoid errors if it was already gone
        # But batch_op doesn't support 'if_exists'.
        # We assume it exists based on previous state.
        batch_op.drop_column('dob_sum')

    with op.batch_alter_table('recovery_requests', schema=None) as batch_op:
        batch_op.drop_column('dob_sum')


def downgrade():
    # Revert changes
    with op.batch_alter_table('recovery_requests', schema=None) as batch_op:
        batch_op.add_column(sa.Column('dob_sum', sa.INTEGER(), nullable=True))
        batch_op.drop_column('dob_sum_hash')

    with op.batch_alter_table('admins', schema=None) as batch_op:
        batch_op.add_column(sa.Column('dob_sum', sa.INTEGER(), nullable=True))
        batch_op.drop_column('salt')
        batch_op.drop_column('dob_sum_hash')
