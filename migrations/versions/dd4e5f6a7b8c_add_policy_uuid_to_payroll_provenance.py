"""Add immutable domain-policy UUID provenance to payroll events."""

from alembic import op
import sqlalchemy as sa
import uuid

revision = "dd4e5f6a7b8c"
down_revision = "dc3d4e5f6a7b"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "policy_versions" in tables and "policy_uuid" not in {c["name"] for c in inspector.get_columns("policy_versions")}:
        op.add_column("policy_versions", sa.Column("policy_uuid", sa.String(length=36), nullable=True))
    if "payroll_event" in tables and "policy_uuid" not in {c["name"] for c in inspector.get_columns("payroll_event")}:
        op.add_column("payroll_event", sa.Column("policy_uuid", sa.String(length=36), nullable=True))
    if "policy_versions" in tables:
        rows = bind.execute(sa.text("SELECT id, class_id, domain, version_number FROM policy_versions WHERE policy_uuid IS NULL")).mappings()
        for row in rows:
            value = str(uuid.uuid5(uuid.NAMESPACE_URL, f"cth:policy:{row['class_id']}:{row['domain']}:{row['version_number']}"))
            bind.execute(sa.text("UPDATE policy_versions SET policy_uuid=:value WHERE id=:id"), {"value": value, "id": row["id"]})
        if "ix_policy_versions_policy_uuid" not in {i["name"] for i in inspector.get_indexes("policy_versions")}:
            op.create_index("ix_policy_versions_policy_uuid", "policy_versions", ["policy_uuid"], unique=True)
    if "payroll_event" in tables and "policy_versions" in tables:
        bind.execute(sa.text("UPDATE payroll_event pe SET policy_uuid=pv.policy_uuid FROM policy_versions pv WHERE pe.policy_version_id=pv.id AND pe.policy_uuid IS NULL"))
        if "ix_payroll_event_policy_uuid" not in {i["name"] for i in inspector.get_indexes("payroll_event")}:
            op.create_index("ix_payroll_event_policy_uuid", "payroll_event", ["policy_uuid"], unique=False)
    if "policy_versions" in tables:
        op.alter_column("policy_versions", "policy_uuid", nullable=False)
    if "payroll_event" in tables:
        op.alter_column("payroll_event", "policy_uuid", nullable=False)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "payroll_event" in tables:
        op.drop_index("ix_payroll_event_policy_uuid", table_name="payroll_event")
        op.drop_column("payroll_event", "policy_uuid")
    if "policy_versions" in tables:
        op.drop_index("ix_policy_versions_policy_uuid", table_name="policy_versions")
        op.drop_column("policy_versions", "policy_uuid")
