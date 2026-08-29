"""Normalize insurance claim_type taxonomy in policy_payload_json

Cuts the persisted insurance policy taxonomy over to the single canonical
vocabulary defined by SPEC-ECON-003 §4.5:

    transaction_monetary  -> TRANSACTION
    legacy_monetary       -> TRANSACTION   (RETIRED — "Variable Monetary" had no
                                            defined reimbursement architecture per
                                            ARC-OPS-001; it is a generic monetary
                                            product, NOT lost-wage/attendance
                                            insurance, so it collapses into the
                                            generic TRANSACTION product and is
                                            never reinterpreted as PRODUCTIVITY)
    non_monetary          -> NON_MONETARY

``claim_type`` is stored inside ``policy_versions.policy_payload_json`` (Text
JSON), not as an ORM column, so this is a data migration over that JSON blob.
It is idempotent: rows already carrying canonical UPPERCASE values are left
untouched, and unknown/missing values default to TRANSACTION (the generic
monetary product) rather than inventing a PRODUCTIVITY reinterpretation.

PRODUCTIVITY has no historical data — it is introduced as genuinely new
behavior (FEAT-STOR-003) after this taxonomy cutover lands.

Revision ID: d4e5f6a7b8c9
Revises: cafe1234beef
Create Date: 2026-08-25

"""
import json

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd4e5f6a7b8c9'
down_revision = 'cafe1234beef'
branch_labels = None
depends_on = None


# Canonical taxonomy (mirrors app.services.economic_engine._LEGACY_CLAIM_TYPE_ALIASES).
# Inlined here so the migration is self-contained and independent of app-code drift.
_TO_CANONICAL = {
    "transaction_monetary": "TRANSACTION",
    "legacy_monetary": "TRANSACTION",
    "non_monetary": "NON_MONETARY",
    "TRANSACTION": "TRANSACTION",
    "PRODUCTIVITY": "PRODUCTIVITY",
    "NON_MONETARY": "NON_MONETARY",
}

# Reverse mapping for downgrade. The canonical taxonomy is lossy with respect to
# the old vocabulary (both transaction_monetary and legacy_monetary map to
# TRANSACTION), so downgrade restores the primary legacy value.
_TO_LEGACY = {
    "TRANSACTION": "transaction_monetary",
    "NON_MONETARY": "non_monetary",
    # PRODUCTIVITY had no pre-cutover legacy representation; leave it as-is.
    "PRODUCTIVITY": "PRODUCTIVITY",
}


def table_exists(table_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def _rewrite_claim_types(mapping):
    """Rewrite claim_type inside policy_versions.policy_payload_json via mapping."""
    if not table_exists('policy_versions'):
        print("⚠️  policy_versions table missing, skipping claim_type normalization")
        return

    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, policy_payload_json FROM policy_versions")
    ).fetchall()

    updated = 0
    for row in rows:
        raw = row[1]
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except (ValueError, TypeError):
            continue
        if not isinstance(payload, dict) or "claim_type" not in payload:
            continue

        current = payload.get("claim_type")
        key = current.strip() if isinstance(current, str) else current
        new_value = mapping.get(key)
        if new_value is None or new_value == current:
            continue

        payload["claim_type"] = new_value
        conn.execute(
            sa.text(
                "UPDATE policy_versions SET policy_payload_json = :payload WHERE id = :id"
            ),
            {"payload": json.dumps(payload), "id": row[0]},
        )
        updated += 1

    print(f"✅ Normalized claim_type in {updated} policy_versions row(s)")


def upgrade():
    _rewrite_claim_types(_TO_CANONICAL)


def downgrade():
    _rewrite_claim_types(_TO_LEGACY)
