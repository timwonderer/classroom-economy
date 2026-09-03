"""FEAT-OBL-005: insurance cancellation is STOP-RENEWAL, never revoke/refund/early-expiry.

Locks the EXPIRED-only canonical model (DOM-STORE-001 §1, FEAT-STOR-002 §IX.C/§XIV,
DOM-OBL-001 §160/§241):

- cancel terminates the recurring INSURANCE_PREMIUM lineage (terminal bill cycle,
  next_assessment_at = NULL) — no future premiums;
- the paid entitlement is NOT revoked or expired early (no REVOKED / EXPIRED event);
- no refund transaction is created;
- coverage still runs to its cycle boundary;
- cancellation is idempotent (no second terminal cycle, safe replay).

Reuses the real purchase flow + fixtures from test_insurance_purchase_feat so the
lineage under test is the one an actual FEAT-OBL-004 purchase establishes.
"""

from __future__ import annotations

import pytest

from app.extensions import db
from app.models import EntitlementEvent, BillCycle, Transaction
from app.services import obligations_service
from app.feats.purchase_insurance_feat import execute_purchase_insurance
from app.feats.cancel_insurance_feat import execute_cancel_insurance
from tests.test_insurance_purchase_feat import _setup, _student_ctx, _teacher_ctx


def _buy(classroom, policy_uuid, *, idem="buy:1"):
    result = execute_purchase_insurance(
        canonical_context=_student_ctx(classroom),
        policy_uuid=policy_uuid, idempotency_key=idem,
    )
    db.session.commit()
    assert result.success, result.error_message
    return result


def _terminal_lifecycle_events(classroom):
    seat_id = classroom.students[0].seat.id
    return (
        EntitlementEvent.query
        .filter(
            EntitlementEvent.class_id == classroom.class_id,
            EntitlementEvent.target_seat_id == seat_id,
            EntitlementEvent.entitlement_type == "INSURANCE",
            EntitlementEvent.event_type.in_(["REVOKED", "EXPIRED"]),
        )
        .all()
    )


def test_cancel_terminates_premium_lineage(app):
    """Cancel writes a terminal bill cycle (next_assessment_at = NULL) — no more premiums."""
    classroom, policy_uuid = _setup(app)
    with app.app_context():
        purchase = _buy(classroom, policy_uuid)

        result = execute_cancel_insurance(
            canonical_context=_student_ctx(classroom),
            policy_uuid=policy_uuid, idempotency_key="cancel:1",
        )
        db.session.commit()

        assert result.success
        assert result.internal_ref is not None
        latest = obligations_service.get_latest_bill_cycle(result.internal_ref)
        assert latest.next_assessment_at is None  # terminal — recurrence stopped
        assert result.coverage_boundary_at == latest.cycle_boundary_at


def test_cancel_does_not_revoke_or_expire_entitlement(app):
    """The paid entitlement is NOT revoked/expired by cancellation (FEAT-STOR-002 §IX.C)."""
    classroom, policy_uuid = _setup(app)
    with app.app_context():
        _buy(classroom, policy_uuid)
        execute_cancel_insurance(
            canonical_context=_student_ctx(classroom),
            policy_uuid=policy_uuid, idempotency_key="cancel:1",
        )
        db.session.commit()

        # No terminal entitlement lifecycle event was written by cancellation.
        assert _terminal_lifecycle_events(classroom) == []
        # The GRANTED coverage still exists and is unterminated.
        granted = EntitlementEvent.query.filter_by(
            class_id=classroom.class_id, entitlement_type="INSURANCE",
            event_type="GRANTED",
        ).count()
        assert granted == 1


def test_cancel_creates_no_refund_transaction(app):
    """Cancellation moves no money — insurance is non-refundable (FEAT-OBL-004 §XI)."""
    classroom, policy_uuid = _setup(app)
    with app.app_context():
        _buy(classroom, policy_uuid)
        before = Transaction.query.filter_by(class_id=classroom.class_id).count()

        execute_cancel_insurance(
            canonical_context=_student_ctx(classroom),
            policy_uuid=policy_uuid, idempotency_key="cancel:1",
        )
        db.session.commit()

        after = Transaction.query.filter_by(class_id=classroom.class_id).count()
        assert after == before  # no refund / no monetary effect


def test_cancel_is_idempotent(app):
    """Re-cancelling already-terminated coverage is a safe no-op (no second terminal cycle)."""
    classroom, policy_uuid = _setup(app)
    with app.app_context():
        _buy(classroom, policy_uuid)

        r1 = execute_cancel_insurance(
            canonical_context=_student_ctx(classroom),
            policy_uuid=policy_uuid, idempotency_key="cancel:1",
        )
        db.session.commit()
        r2 = execute_cancel_insurance(
            canonical_context=_student_ctx(classroom),
            policy_uuid=policy_uuid, idempotency_key="cancel:2",
        )
        db.session.commit()

        assert r1.success and r2.success
        assert r2.already_cancelled is True
        cycles = obligations_service.get_bill_cycles_for_internal_ref(r1.internal_ref)
        # genesis + single terminal only (not two terminal rows)
        assert sum(1 for c in cycles if c.next_assessment_at is None) == 1


def test_cancel_without_coverage_fails_closed(app):
    """Cancelling a policy the seat never purchased fails closed."""
    classroom, policy_uuid = _setup(app)
    with app.app_context():
        result = execute_cancel_insurance(
            canonical_context=_student_ctx(classroom),
            policy_uuid=policy_uuid, idempotency_key="cancel:1",
        )
        db.session.commit()
        assert result.success is False
        assert result.error_code == "COVERAGE_NOT_FOUND"


def test_teacher_can_cancel_a_covered_seat(app):
    """A teacher may cancel a covered seat's coverage via target_seat_id."""
    classroom, policy_uuid = _setup(app)
    with app.app_context():
        _buy(classroom, policy_uuid)
        seat_id = classroom.students[0].seat.id

        result = execute_cancel_insurance(
            canonical_context=_teacher_ctx(classroom),
            policy_uuid=policy_uuid, target_seat_id=seat_id,
            idempotency_key="cancel:teacher",
        )
        db.session.commit()
        assert result.success
        latest = obligations_service.get_latest_bill_cycle(result.internal_ref)
        assert latest.next_assessment_at is None
