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
    Uses raw SQL with a USING clause for PostgreSQL compatibility.
    """
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        raise ValueError("ENCRYPTION_KEY environment variable not set for data migration.")

    fernet = Fernet(key.encode())
    bind = op.get_bind()

    # 1. Fetch all existing plaintext names into memory BEFORE changing the type
    students_to_encrypt = bind.execute(sa.select(students_varchar_table.c.id, students_varchar_table.c.first_name)).fetchall()

    # 2. Use raw SQL to alter the column type with the USING clause for PostgreSQL
    op.execute('ALTER TABLE students ALTER COLUMN first_name TYPE BYTEA USING first_name::bytea')

    # 3. Now, encrypt the plaintext data we have in memory and update the rows
    for student in students_to_encrypt:
        student_id, first_name = student
        if first_name and isinstance(first_name, str):
            encrypted_name = fernet.encrypt(first_name.encode('utf-8'))
            update_stmt = (
                sa.update(students_binary_table)
                .where(students_binary_table.c.id == student_id)
                .values(first_name=encrypted_name)
            )
            bind.execute(update_stmt)

def downgrade():
    """
    Decrypts existing first_name data and changes the column type back to VARCHAR.
    Uses a temporary column to avoid type casting issues with encrypted data.
    """
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        raise ValueError("ENCRYPTION_KEY environment variable not set for data migration.")

    fernet = Fernet(key.encode())
    bind = op.get_bind()

    # 1. Fetch all existing encrypted names into memory
    students_to_decrypt = bind.execute(sa.select(students_binary_table.c.id, students_binary_table.c.first_name)).fetchall()

    # 2. Add a temporary column to hold the decrypted names
    op.add_column('students', sa.Column('first_name_tmp', sa.String(50), nullable=True))

    # 3. Decrypt and update the temporary column
    for student in students_to_decrypt:
        student_id, encrypted_name = student
        if encrypted_name and isinstance(encrypted_name, bytes):
            try:
                decrypted_name = fernet.decrypt(encrypted_name).decode('utf-8')
            except Exception:
                decrypted_name = 'decryption_failed'

            # Use text() for the update statement to avoid table reflection issues
            update_stmt = sa.text("UPDATE students SET first_name_tmp = :name WHERE id = :id")
            bind.execute(update_stmt, {"name": decrypted_name, "id": student_id})

    # 4. Drop the old encrypted column
    op.drop_column('students', 'first_name')

    # 5. Rename the temporary column to 'first_name' and make it non-nullable
    op.alter_column('students', 'first_name_tmp', new_column_name='first_name', nullable=False, existing_type=sa.String(50))
