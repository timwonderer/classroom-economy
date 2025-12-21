"""fix incorrectly encrypted names

Revision ID: d1b3c4d5e6f7
Revises: 9e7a8d4f5c6b
Create Date: 2025-10-06 19:22:00.000000

"""
from alembic import op
import sqlalchemy as sa
import os
from cryptography.fernet import Fernet, InvalidToken

# revision identifiers, used by Alembic.
revision = 'd1b3c4d5e6f7'
down_revision = '9e7a8d4f5c6b'
branch_labels = None
depends_on = None

# Define a minimal table structure for the data migration
students_table = sa.table('students',
    sa.column('id', sa.Integer),
    sa.column('first_name', sa.LargeBinary)
)

def upgrade():
    """
    Identifies student records with incorrectly encoded (not encrypted) first names
    and re-encrypts them correctly.
    """
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        raise ValueError("ENCRYPTION_KEY environment variable not set for data migration.")

    fernet = Fernet(key.encode())
    bind = op.get_bind()

    # Select all student records
    students_to_check = bind.execute(sa.select(students_table.c.id, students_table.c.first_name)).fetchall()

    for student_id, raw_name_bytes in students_to_check:
        if not raw_name_bytes:
            continue

        try:
            # Try to decrypt. If it succeeds, the data is already correctly encrypted.
            fernet.decrypt(raw_name_bytes)
        except InvalidToken:
            # If decryption fails, it's likely a corrupted record.
            # The corruption happened because a plaintext string 'name' was cast
            # to bytea directly, e.g., b'name', instead of being encrypted.
            try:
                # Decode the raw bytes back to a UTF-8 string.
                plaintext_name = raw_name_bytes.decode('utf-8')

                # Now, correctly encrypt the plaintext name.
                corrected_encrypted_name = fernet.encrypt(plaintext_name.encode('utf-8'))

                # Update the database record with the correctly encrypted name.
                update_stmt = (
                    sa.update(students_table)
                    .where(students_table.c.id == student_id)
                    .values(first_name=corrected_encrypted_name)
                )
                bind.execute(update_stmt)
                print(f"Corrected record for student_id: {student_id}")
            except Exception as e:
                print(f"Could not correct record for student_id: {student_id}, error: {e}")


def downgrade():
    """
    This is a data-correction migration. A downgrade is not typically necessary,
    as the 'upgrade' fixes the data in place. If a downgrade were needed, it
    would imply re-corrupting the data, which is not a standard practice.
    We will provide a pass-through downgrade.
    """
    pass