"""Add policy_code and teacher_id to insurance_policies for multi-tenancy

Revision ID: h2i3j4k5l6m7
Revises: g1h2i3j4k5l6
Create Date: 2025-11-23 03:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import secrets


# revision identifiers, used by Alembic.
revision = 'h2i3j4k5l6m7'
down_revision = 'g1h2i3j4k5l6'
branch_labels = None
depends_on = None


def generate_policy_code():
    """Generate a unique 16-character policy code."""
    return secrets.token_urlsafe(12)[:16]


def upgrade():
    # Add teacher_id column
    op.add_column('insurance_policies', sa.Column('teacher_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_insurance_policies_teacher_id',
        'insurance_policies', 'admins',
        ['teacher_id'], ['id'],
        ondelete='SET NULL'
    )

    # Add policy_code column (nullable first for backfill)
    op.add_column('insurance_policies', sa.Column('policy_code', sa.String(16), nullable=True))

    # Backfill existing policies with unique policy codes
    # Note: In production, you might want to generate these more carefully
    connection = op.get_bind()

    # Get all existing policies
    policies = connection.execute(sa.text("SELECT id FROM insurance_policies")).fetchall()

    # Generate unique codes for each
    for policy in policies:
        policy_id = policy[0]
        # Generate unique code
        while True:
            code = generate_policy_code()
            # Check if code already exists
            existing = connection.execute(
                sa.text("SELECT id FROM insurance_policies WHERE policy_code = :code"),
                {"code": code}
            ).fetchone()
            if not existing:
                break

        # Update the policy with the code
        connection.execute(
            sa.text("UPDATE insurance_policies SET policy_code = :code WHERE id = :id"),
            {"code": code, "id": policy_id}
        )
        connection.commit()

    # Backfill teacher_id for existing policies using enrolled students' primary teacher
    # Choose the most frequent teacher_id among students attached to each policy
    teacher_counts = connection.execute(
        sa.text(
            """
            SELECT si.policy_id, s.teacher_id, COUNT(*) AS cnt
            FROM student_insurance si
            JOIN students s ON s.id = si.student_id
            WHERE s.teacher_id IS NOT NULL
            GROUP BY si.policy_id, s.teacher_id
            """
        )
    ).fetchall()

    teacher_by_policy = {}
    for policy_id, teacher_id, count in teacher_counts:
        current = teacher_by_policy.get(policy_id)
        if current is None or count > current[1]:
            teacher_by_policy[policy_id] = (teacher_id, count)

    for policy_id, (teacher_id, _) in teacher_by_policy.items():
        connection.execute(
            sa.text(
                "UPDATE insurance_policies SET teacher_id = :teacher_id "
                "WHERE id = :policy_id AND teacher_id IS NULL"
            ),
            {"teacher_id": teacher_id, "policy_id": policy_id},
        )

    connection.commit()

    # Now make policy_code non-nullable and unique
    op.alter_column('insurance_policies', 'policy_code', nullable=False)
    op.create_unique_constraint('uq_insurance_policies_policy_code', 'insurance_policies', ['policy_code'])
    op.create_index('ix_insurance_policies_policy_code', 'insurance_policies', ['policy_code'])


def downgrade():
    # Remove indexes and constraints
    op.drop_index('ix_insurance_policies_policy_code', table_name='insurance_policies')
    op.drop_constraint('uq_insurance_policies_policy_code', 'insurance_policies', type_='unique')
    op.drop_column('insurance_policies', 'policy_code')

    # Remove teacher_id
    op.drop_constraint('fk_insurance_policies_teacher_id', 'insurance_policies', type_='foreignkey')
    op.drop_column('insurance_policies', 'teacher_id')
