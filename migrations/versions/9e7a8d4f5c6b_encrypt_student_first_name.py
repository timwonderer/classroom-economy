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
    """
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        raise ValueError("ENCRYPTION_KEY environment variable not set for data migration.")

    fernet = Fernet(key.encode())
    bind = op.get_bind()

    # 1. Fetch all existing plaintext names into memory
    students_to_encrypt = bind.execute(sa.select(students_varchar_table)).fetchall()

    # 2. Alter column to LargeBinary, making it nullable temporarily for the update
    op.alter_column('students', 'first_name',
               existing_type=sa.VARCHAR(length=50),
               type_=sa.LargeBinary(),
               nullable=True)

    # 3. Encrypt and update the data in the new LargeBinary column
    for student in students_to_encrypt:
        # Check if first_name is not None and is a string
        if student.first_name and isinstance(student.first_name, str):
            encrypted_name = fernet.encrypt(student.first_name.encode('utf-8'))
            update_stmt = (
                sa.update(students_binary_table)
                .where(students_binary_table.c.id == student.id)
                .values(first_name=encrypted_name)
            )
            bind.execute(update_stmt)

    # 4. Set the column back to non-nullable
    op.alter_column('students', 'first_name',
               existing_type=sa.LargeBinary(),
               nullable=False)


def downgrade():
    """
    Decrypts existing first_name data and changes the column type back to VARCHAR.
    """
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        raise ValueError("ENCRYPTION_KEY environment variable not set for data migration.")

    fernet = Fernet(key.encode())
    bind = op.get_bind()

    # 1. Fetch all existing encrypted names into memory
    students_to_decrypt = bind.execute(sa.select(students_binary_table)).fetchall()

    # 2. Alter column back to VARCHAR, making it nullable temporarily for the update
    op.alter_column('students', 'first_name',
               existing_type=sa.LargeBinary(),
               type_=sa.VARCHAR(length=50),
               nullable=True)

    # 3. Decrypt and update the data in the new VARCHAR column
    for student in students_to_decrypt:
        # Check if first_name is not None and is bytes
        if student.first_name and isinstance(student.first_name, bytes):
            try:
                decrypted_name = fernet.decrypt(student.first_name).decode('utf-8')
            except Exception:
                # If decryption fails, use a placeholder to avoid breaking the migration
                decrypted_name = 'decryption_failed'

            update_stmt = (
                sa.update(students_varchar_table)
                .where(students_varchar_table.c.id == student.id)
                .values(first_name=decrypted_name)
            )
            bind.execute(update_stmt)

    # 4. Set the column back to non-nullable
    op.alter_column('students', 'first_name',
               existing_type=sa.VARCHAR(length=50),
               nullable=False)