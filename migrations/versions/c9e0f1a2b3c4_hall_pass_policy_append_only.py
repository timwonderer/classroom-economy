"""Convert hall-pass settings into immutable policy rows."""
from alembic import op
import sqlalchemy as sa
import json
import uuid

revision = "c9e0f1a2b3c4"
down_revision = "b8d99895056b"
branch_labels = None
depends_on = None

def upgrade():
    inspector = sa.inspect(op.get_bind())
    def has(table, name):
        return name in {col["name"] for col in inspector.get_columns(table)}
    if not has("hall_pass_logs", "policy_uuid"):
        op.add_column("hall_pass_logs", sa.Column("policy_uuid", sa.String(36), nullable=True))
    for name, column in (("policy_uuid", sa.String(36)), ("max_queue_limit", sa.Integer()), ("pass_type_payload", sa.JSON()), ("effective_date", sa.DateTime(timezone=True))):
        if not has("hall_pass_settings", name):
            op.add_column("hall_pass_settings", sa.Column(name, column, nullable=True))
    conn = op.get_bind()
    if has("hall_pass_settings", "queue_limit"):
        rows = conn.execute(sa.text("SELECT id, queue_limit, pass_types, created_at FROM hall_pass_settings")).mappings().all()
        for row in rows:
            payload = row["pass_types"] or []
            if isinstance(payload, str):
                payload = json.loads(payload)
            if not isinstance(payload, list):
                raise RuntimeError(f"hall_pass_settings.id={row['id']} has non-list pass_types")
            normalized = []
            for item in payload:
                if not isinstance(item, dict):
                    raise RuntimeError(f"hall_pass_settings.id={row['id']} has a non-object pass_types entry")
                normalized.append({"pass_name": item.get("name", ""), "max_queue": item.get("queue_limit") or row["queue_limit"] or 10, "consume_pass": bool(item.get("consume_pass", True))})
            conn.execute(sa.text("UPDATE hall_pass_settings SET policy_uuid=:uuid, max_queue_limit=:limit, pass_type_payload=CAST(:payload AS JSON), effective_date=:effective WHERE id=:id"), {"id": row["id"], "uuid": str(uuid.uuid4()), "limit": row["queue_limit"] or 10, "payload": json.dumps(normalized), "effective": row["created_at"]})
    conn.execute(sa.text("UPDATE hall_pass_logs SET policy_uuid=(SELECT policy_uuid FROM hall_pass_settings s WHERE s.class_id=hall_pass_logs.class_id ORDER BY s.effective_date DESC LIMIT 1) WHERE policy_uuid IS NULL"))
    orphan_logs = conn.execute(sa.text("SELECT COUNT(*) FROM hall_pass_logs WHERE policy_uuid IS NULL")).scalar()
    if orphan_logs:
        raise RuntimeError(f"{orphan_logs} hall_pass_logs rows have no matching hall-pass policy")
    op.alter_column("hall_pass_logs", "policy_uuid", nullable=False)
    for name in ("policy_uuid", "max_queue_limit", "pass_type_payload", "effective_date"):
        unset = conn.execute(sa.text(f"SELECT COUNT(*) FROM hall_pass_settings WHERE {name} IS NULL")).scalar()
        if unset:
            raise RuntimeError(f"{unset} hall_pass_settings rows have NULL {name}")
        op.alter_column("hall_pass_settings", name, nullable=False)
    existing_uniques = {c['name'] for c in sa.inspect(conn).get_unique_constraints('hall_pass_settings')}
    if "uq_hall_pass_settings_policy_uuid" not in existing_uniques:
        op.create_unique_constraint("uq_hall_pass_settings_policy_uuid", "hall_pass_settings", ["policy_uuid"])
    if "ix_hall_pass_settings_class_id" in {i['name'] for i in sa.inspect(conn).get_indexes('hall_pass_settings')}:
        op.drop_index("ix_hall_pass_settings_class_id", table_name="hall_pass_settings")
    for name in ("queue_enabled", "queue_limit", "pass_types", "updated_at"):
        if has("hall_pass_settings", name):
            op.drop_column("hall_pass_settings", name)

def downgrade():
    raise NotImplementedError("Hall-pass policy conversion is intentionally irreversible")
