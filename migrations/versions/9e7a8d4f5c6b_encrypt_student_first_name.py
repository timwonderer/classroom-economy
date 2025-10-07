"""Encrypt student first_name with data migration

Revision ID: 9e7a8d4f5c6b
Revises: 8f4a660d5082
Create Date: 2025-10-02 21:50:00.000000

"""
from alembic import op
import sqlalchemy as sa
import os
from cryptography.fernet import Fernet

# revision identifiers, used by Alembic.
revision = '9e7a8d4f5c6b'
down_revision = '8f4a660d5082'
branch_labels = None
depends_on = None

# Define table structures for data migration
students_varchar_table = sa.table('students',
    sa.column('id', sa.Integer),
    sa.column('first_name', sa.String(50))
)

students_binary_table = sa.table('students',
    sa.column('id', sa.Integer),
    sa.column('first_name', sa.LargeBinary)
)

def upgrade():
    """
    Encrypts existing first_name data and changes the column type to LargeBinary.
    Uses a temporary column and batch mode for SQLite compatibility.
    """
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        raise ValueError("ENCRYPTION_KEY environment variable not set for data migration.")

    fernet = Fernet(key.encode())
    bind = op.get_bind()

    # 1. Add a temporary column to hold the encrypted data
    op.add_column('students', sa.Column('first_name_encrypted', sa.LargeBinary(), nullable=True))

    # 2. Fetch plaintext names, encrypt them, and update the new column
    students_to_encrypt = bind.execute(sa.select(students_varchar_table.c.id, students_varchar_table.c.first_name)).fetchall()
    for student_id, first_name in students_to_encrypt:
        if first_name and isinstance(first_name, str):
            encrypted_name = fernet.encrypt(first_name.encode('utf-8'))
            # Use text() for raw SQL update to avoid reflection issues
            update_stmt = sa.text("UPDATE students SET first_name_encrypted = :encrypted_name WHERE id = :id")
            bind.execute(update_stmt, {"encrypted_name": encrypted_name, "id": student_id})

    # 3. Use batch mode to drop the old column and rename the new one, which is SQLite-safe
    with op.batch_alter_table('students', schema=None) as batch_op:
        batch_op.drop_column('first_name')
        batch_op.alter_column('first_name_encrypted', new_column_name='first_name', nullable=False)


def downgrade():
    """
    Decrypts existing first_name data and changes the column type back to VARCHAR.
    Uses a temporary column and batch mode for SQLite compatibility.
    """
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        raise ValueError("ENCRYPTION_KEY environment variable not set for data migration.")

    fernet = Fernet(key.encode())
    bind = op.get_bind()

    # 1. Add a temporary column to hold the decrypted names
    op.add_column('students', sa.Column('first_name_decrypted', sa.String(50), nullable=True))

    # 2. Fetch encrypted names, decrypt them, and update the temporary column
    students_to_decrypt = bind.execute(sa.select(students_binary_table.c.id, students_binary_table.c.first_name)).fetchall()
    for student_id, encrypted_name in students_to_decrypt:
        if encrypted_name and isinstance(encrypted_name, bytes):
            try:
                decrypted_name = fernet.decrypt(encrypted_name).decode('utf-8')
            except Exception:
                # In case of a decryption error, store a placeholder
                decrypted_name = 'decryption_failed'

            update_stmt = sa.text("UPDATE students SET first_name_decrypted = :name WHERE id = :id")
            bind.execute(update_stmt, {"name": decrypted_name, "id": student_id})

    # 3. Use batch mode to drop the old encrypted column and rename the temporary one
    with op.batch_alter_table('students', schema=None) as batch_op:
        batch_op.drop_column('first_name')
        batch_op.alter_column('first_name_decrypted', new_column_name='first_name', nullable=False, existing_type=sa.String(50))