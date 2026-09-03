"""Slice 3 — daily insurance boundary-expiry job (Store-owned EXPIRED at boundary).

Canonical model (DOM-STORE-001 §1, FEAT-STOR-002 §VIII/§IX.C): purchased insurance
ends by EXPIRED at its coverage boundary — never revoked/refunded. Cancellation
(FEAT-OBL-005) stops renewal by terminating the premium lineage; this daily job
reads the bill-cycle table for terminal lineages past their boundary and writes
EXPIRED for the matching coverage.

Locks:
- coverage is NOT expired before its boundary is reached;
- once the terminal lineage's boundary passes, the job writes exactly one EXPIRED;
- the job is idempotent (re-runs create no duplicate terminal);
- ACTIVE (still-renewing, non-terminal) coverage is never expired by the job.
"""

from __future__ import annotations

from uuid import uuid4

from app.extensions import db
from app.models import EntitlementEvent, BillCycle
from app.services import obligations_service
from app.feats.base import FEATContext
from app.feats.purchase_insurance_feat import execute_purchase_insurance
from app.feats.cancel_insurance_feat import execute_cancel_insurance
from app.scheduled_tasks import run_insurance_expiry_job
from app.utils.canonical_temporal_resolver import utc_now
from datetime import timedelta
from tests.test_insurance_purchase_feat import _setup, _student_ctx


def _buy(classroom, policy_uuid, idem="buy:1"):
    r = execute_purchase_insurance(
        canonical_context=_student_ctx(classroom),
        policy_uuid=policy_uuid, idempotency_key=idem,
    )
    db.session.commit()
    assert r.success, r.error_message
    return r


def _cancel(classroom, policy_uuid, idem="cancel:1"):
    r = execute_cancel_insurance(
        canonical_context=_student_ctx(classroom),
        policy_uuid=policy_uuid, idempotency_key=idem,
    )
    db.session.commit()
    assert r.success
    return r


def _expired_events(classroom):
    seat_id = classroom.students[0].seat.id
    return EntitlementEvent.query.filter_by(
        class_id=classroom.class_id, target_seat_id=seat_id,
        entitlement_type="INSURANCE", event_type="EXPIRED",
    ).all()


def _move_boundary_to_past(internal_ref):
    """Push the terminal cycle's coverage boundary into the past."""
    terminal = obligations_service.get_latest_bill_cycle(internal_ref)
    assert terminal.next_assessment_at is None
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"bound:{uuid4().hex}"):
        terminal.cycle_boundary_at = utc_now() - timedelta(days=1)
    db.session.commit()
    return terminal


def test_not_expired_before_boundary(app):
    """A cancelled lineage whose boundary is still in the future is NOT expired yet."""
    classroom, policy_uuid = _setup(app)
    with app.app_context():
        _buy(classroom, policy_uuid)
        _cancel(classroom, policy_uuid)  # boundary is ~future

        run_insurance_expiry_job()

        assert _expired_events(classroom) == []


def test_expires_once_boundary_passed(app):
    """After the terminal boundary passes, the job writes exactly one EXPIRED."""
    classroom, policy_uuid = _setup(app)
    with app.app_context():
        _buy(classroom, policy_uuid)
        cancel = _cancel(classroom, policy_uuid)
        _move_boundary_to_past(cancel.internal_ref)

        run_insurance_expiry_job()

        events = _expired_events(classroom)
        assert len(events) == 1


def test_expiry_job_is_idempotent(app):
    """Re-running the job creates no duplicate EXPIRED terminal."""
    classroom, policy_uuid = _setup(app)
    with app.app_context():
        _buy(classroom, policy_uuid)
        cancel = _cancel(classroom, policy_uuid)
        _move_boundary_to_past(cancel.internal_ref)

        run_insurance_expiry_job()
        run_insurance_expiry_job()

        assert len(_expired_events(classroom)) == 1


def test_active_renewing_coverage_is_not_expired(app):
    """Active (non-terminal) coverage is never expired by the job, even past a boundary."""
    classroom, policy_uuid = _setup(app)
    with app.app_context():
        purchase = _buy(classroom, policy_uuid)
        # Force the ACTIVE cycle-1 boundary into the past WITHOUT cancelling —
        # its next_assessment_at is still set, so it is not a terminal lineage.
        cycle1 = db.session.get(BillCycle, purchase.bill_cycle_id)
        assert cycle1.next_assessment_at is not None
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"bound:{uuid4().hex}"):
            cycle1.cycle_boundary_at = utc_now() - timedelta(days=1)
        db.session.commit()

        run_insurance_expiry_job()

        assert _expired_events(classroom) == []
