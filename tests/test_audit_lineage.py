"""Tests for the audit lineage system.

Covers:
  - emit_audit_event creates AuditEvent + updates ChainHead
  - Hash continuity across multiple events
  - verify_chain detects tampered payload_digest
  - verify_chain detects deleted mid-chain event (sequence gap)
  - emit_audit_event outside FEAT raises AuditContextError
  - create_pending_transaction attaches non-null lineage_token
  - run_full_invariant_check + update_integrity_status mark IntegrityStatus degraded on bad chain
  - system_audit_authority allows writes without a FEAT context
"""
import uuid

import pyotp
import pytest
from sqlalchemy import text

from app.extensions import db
from app.feats.base import FEATContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_class_id():
    return str(uuid.uuid4())


def _make_user():
    """Create a minimal User row (teacher role) and return it (does not commit)."""
    from app.models import User, UserRole

    user = User(
        username_hash=f"auditu_{uuid.uuid4().hex[:12]}",
        username_lookup_hash=f"auditlup_{uuid.uuid4().hex[:12]}",
        user_role=UserRole.TEACHER,
    )
    db.session.add(user)
    db.session.flush()
    return user


def _make_class(user_id):
    """Create a minimal ClassEconomy row and return it (does not commit)."""
    from app.models import ClassEconomy

    class_id = _make_class_id()
    join_code = f"AUD{uuid.uuid4().hex[:5].upper()}"
    ce = ClassEconomy(class_id=class_id, join_code=join_code, user_id=user_id)
    db.session.add(ce)
    db.session.flush()
    return ce


def _make_seat(class_id):
    """Create a minimal Seat row and return it (does not commit)."""
    from app.models import Seat

    seat = Seat(class_id=class_id)
    db.session.add(seat)
    db.session.flush()
    return seat


# ---------------------------------------------------------------------------
# Test: emit_audit_event creates chain entry and updates ChainHead
# ---------------------------------------------------------------------------

def test_emit_audit_event_creates_chain_entry(app):
    with app.app_context():
        from app.models import AuditEvent, ChainHead
        from app.services.audit_service import emit_audit_event

        class_id = _make_class_id()
        scope = f"class:{class_id}"

        with FEATContext("FEAT-TEST-AUDIT"):
            event = emit_audit_event(
                table_name="ledger_transaction",
                row_pk="999",
                operation="INSERT",
                protected_fields={"amount": "10.00", "type": "payroll"},
                class_id=class_id,
            )
        db.session.commit()

        ae = AuditEvent.query.filter_by(id=event.id).first()
        assert ae is not None
        assert ae.chain_scope == scope
        assert ae.sequence_number == 1
        assert ae.previous_hash == "genesis"
        assert len(ae.event_hash) == 64
        assert ae.hmac_signature == ae.event_hash

        head = ChainHead.query.filter_by(chain_scope=scope).first()
        assert head is not None
        assert head.latest_sequence == 1
        assert head.latest_hash == ae.event_hash
        assert head.event_count == 1


# ---------------------------------------------------------------------------
# Test: hash continuity across multiple events in the same chain
# ---------------------------------------------------------------------------

def test_chain_hash_continuity(app):
    with app.app_context():
        from app.models import AuditEvent
        from app.services.audit_service import emit_audit_event

        class_id = _make_class_id()
        scope = f"class:{class_id}"

        with FEATContext("FEAT-TEST-AUDIT", idempotency_key=f"audit-lineage:chain:{class_id}"):
            for i in range(1, 6):
                emit_audit_event(
                    table_name="ledger_transaction",
                    row_pk=str(i),
                    operation="INSERT",
                    protected_fields={"amount": str(i * 10)},
                    class_id=class_id,
                )

        events = (
            AuditEvent.query
            .filter_by(chain_scope=scope)
            .order_by(AuditEvent.sequence_number.asc())
            .all()
        )
        assert len(events) == 5
        assert events[0].previous_hash == "genesis"
        for i in range(1, 5):
            assert events[i].previous_hash == events[i - 1].event_hash, (
                f"Event {i+1} previous_hash does not match event {i} event_hash"
            )


# ---------------------------------------------------------------------------
# Test: verify_chain detects tampered payload_digest
# ---------------------------------------------------------------------------

def test_verify_chain_detects_tampered_payload(app):
    with app.app_context():
        from app.models import AuditEvent
        from app.services.audit_service import emit_audit_event, LineageState
        from app.utils.audit_verifier import verify_chain

        class_id = _make_class_id()
        scope = f"class:{class_id}"

        with FEATContext("FEAT-TEST-AUDIT", idempotency_key=f"audit-lineage:tamper:{class_id}"):
            for i in range(1, 4):
                emit_audit_event(
                    table_name="ledger_transaction",
                    row_pk=str(i),
                    operation="INSERT",
                    protected_fields={"amount": str(i)},
                    class_id=class_id,
                )

        # Directly corrupt payload_digest on the second event outside FEAT.
        second = (
            AuditEvent.query
            .filter_by(chain_scope=scope, sequence_number=2)
            .first()
        )
        assert second is not None
        db.session.execute(
            text("UPDATE audit_events SET payload_digest = :payload_digest WHERE id = :id"),
            {"payload_digest": "a" * 64, "id": second.id},
        )
        db.session.commit()

        result = verify_chain(scope)
        assert result.state == LineageState.INVALID
        assert result.failure_type in ("BAD_HMAC", "PAYLOAD_MISMATCH")
        assert result.first_bad_sequence == 2


# ---------------------------------------------------------------------------
# Test: verify_chain detects a deleted mid-chain event (sequence gap)
# ---------------------------------------------------------------------------

def test_verify_chain_detects_deleted_event(app):
    with app.app_context():
        from app.models import AuditEvent
        from app.services.audit_service import emit_audit_event, LineageState
        from app.utils.audit_verifier import verify_chain

        class_id = _make_class_id()
        scope = f"class:{class_id}"

        with FEATContext("FEAT-TEST-AUDIT", idempotency_key=f"audit-lineage:delete:{class_id}"):
            for i in range(1, 5):
                emit_audit_event(
                    table_name="ledger_transaction",
                    row_pk=str(i),
                    operation="INSERT",
                    protected_fields={"amount": str(i)},
                    class_id=class_id,
                )

        # Delete the second event to create a sequence gap.
        second = (
            AuditEvent.query
            .filter_by(chain_scope=scope, sequence_number=2)
            .first()
        )
        assert second is not None
        db.session.execute(
            text("DELETE FROM audit_events WHERE id = :id"),
            {"id": second.id},
        )
        db.session.commit()

        result = verify_chain(scope)
        assert result.state == LineageState.INVALID
        assert result.failure_type == "SEQUENCE_GAP"
        assert result.first_bad_sequence == 2


# ---------------------------------------------------------------------------
# Test: emit_audit_event outside FEAT context raises AuditContextError
# This test intentionally runs without a FEAT context to verify fail-closed behavior.
# ---------------------------------------------------------------------------

@pytest.mark.enforce_feat
def test_emit_outside_feat_raises(app):
    with app.app_context():
        from app.feats.base import is_feat_active
        from app.services.audit_service import emit_audit_event, AuditContextError

        assert not is_feat_active(), "Precondition: no FEAT active"

        with pytest.raises(AuditContextError):
            emit_audit_event(
                table_name="ledger_transaction",
                row_pk="1",
                operation="INSERT",
                protected_fields={"amount": "5.00"},
                class_id=_make_class_id(),
            )


# ---------------------------------------------------------------------------
# Test: create_pending_transaction attaches non-null lineage_token
# ---------------------------------------------------------------------------

def test_protected_write_attaches_lineage_token(app):
    with app.app_context():
        from app.services.ledger_service import create_pending_transaction

        with FEATContext("FEAT-TEST-AUDIT", idempotency_key="audit-lineage:protected-write"):
            teacher_user = _make_user()
            ce = _make_class(teacher_user.id)
            seat = _make_seat(ce.class_id)

            txn = create_pending_transaction(
                seat_id=seat.id,
                class_id=ce.class_id,
                user_id=teacher_user.id,
                amount="25.00",
                account_type="checking",
                type="payroll",
                description="Test payroll",
            )

        assert txn.lineage_token is not None, (
            "lineage_token must be set after create_pending_transaction"
        )
        assert txn.lineage_event_id is not None, "lineage_event_id must be set"
        assert txn.lineage_version is not None


# ---------------------------------------------------------------------------
# Test: IntegrityStatus is set degraded when invariant check finds a bad chain
# ---------------------------------------------------------------------------

def test_integrity_status_degraded_on_bad_chain(app):
    with app.app_context():
        from app.models import AuditEvent, IntegrityStatus
        from app.services.audit_service import emit_audit_event
        from app.utils.audit_verifier import run_full_invariant_check, update_integrity_status

        class_id = _make_class_id()
        scope = f"class:{class_id}"

        with FEATContext("FEAT-TEST-AUDIT", idempotency_key=f"audit-lineage:integrity:{class_id}"):
            for i in range(1, 3):
                emit_audit_event(
                    table_name="ledger_transaction",
                    row_pk=str(i),
                    operation="INSERT",
                    protected_fields={"amount": str(i)},
                    class_id=class_id,
                )

        # Break the chain by corrupting the first event's hash outside FEAT.
        first = (
            AuditEvent.query
            .filter_by(chain_scope=scope, sequence_number=1)
            .first()
        )
        assert first is not None
        db.session.execute(
            text(
                "UPDATE audit_events SET event_hash = :event_hash, hmac_signature = :hmac_signature "
                "WHERE id = :id"
            ),
            {"event_hash": "b" * 64, "hmac_signature": "b" * 64, "id": first.id},
        )
        db.session.commit()

        results = run_full_invariant_check()
        update_integrity_status(results)

        status = IntegrityStatus.query.first()
        assert status is not None
        assert status.passing is False
        assert status.degraded_since is not None
        assert status.failure_detail is not None


# ---------------------------------------------------------------------------
# Test: system_audit_authority allows writes without a FEAT context
# ---------------------------------------------------------------------------

@pytest.mark.enforce_feat
def test_system_audit_authority_allows_write(app):
    with app.app_context():
        from app.models import AuditEvent
        from app.services.audit_service import emit_audit_event, system_audit_authority

        with system_audit_authority("test-genesis"):
            event = emit_audit_event(
                table_name="ledger_transaction",
                row_pk="system-1",
                operation="INSERT",
                protected_fields={"amount": "0.00"},
                class_id=None,
            )
            db.session.commit()

        ae = AuditEvent.query.get(event.id)
        assert ae is not None
        assert ae.actor_type == "system"
        assert ae.chain_scope == "system"
