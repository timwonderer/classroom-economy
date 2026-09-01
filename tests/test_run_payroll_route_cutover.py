"""Slice 8.3e — manual /run_payroll route cutover to FEAT-PROD-004.

Proves that a real HTTP manual-payroll invocation drives the entire canonical
economic-cycle lifecycle through FEAT-PROD-004 (the route no longer owns a
per-seat loop), and that replaying the same manual command reproduces none of it.

    POST /admin/run_payroll
        → PayrollEvent rows (stamped with the run's payroll_cycle_id)
        → one interpretation_cycle_record
        → pending next-cycle policy activates
        → payroll_cycle_completion anchor
"""

from __future__ import annotations

from datetime import timedelta

from app.extensions import db
from app.feats.base import FEATContext
from app.models import (
    AttendanceSession,
    InterpretationCycleRecord,
    PayrollEvent,
    PolicyTransition,
    PolicyVersion,
)
from app.services.payroll.cycle_completion import resolve_completed_run
from app.utils.canonical_temporal_resolver import utc_now
from tests.helpers.classroom_initializer import initialize_as_teacher


def _seed(classroom):
    """Active payroll policy (v1) + pending next_payroll transition (v2) + attendance."""
    cid = classroom.class_id
    student = classroom.students[0]
    now = utc_now()
    with FEATContext("FEAT-BYPASS-LEGACY", correlation_id=f"seed:{cid}"):
        v1 = PolicyVersion(class_id=cid, domain="payroll", version_number=1,
                           policy_payload_json="{}", activated_at=now, is_active=True)
        db.session.add(v1)
        db.session.flush()
        v2 = PolicyVersion(class_id=cid, domain="payroll", version_number=2,
                           policy_payload_json="{}", activated_at=None, is_active=False)
        db.session.add(v2)
        db.session.flush()
        db.session.add(PolicyTransition(
            class_id=cid, domain="payroll", source_policy_version_id=v1.id,
            target_policy_version_id=v2.id, activation_mode="next_payroll",
            status="pending", created_at=now,
        ))
        db.session.flush()
        v1_id, v2_id = v1.id, v2.id
    with FEATContext("FEAT-PROD-001", correlation_id=f"att:{cid}", idempotency_key=f"att:{cid}"):
        db.session.add(AttendanceSession(
            target_seat_id=student.seat.id, class_id=cid, target_user_id=student.user.id,
            actor_seat_id=classroom.teacher_seat_id, reason_code="start_work",
            timestamp=now - timedelta(minutes=30),
        ))
        db.session.flush()
    return cid, v1_id, v2_id


def test_manual_run_payroll_drives_full_lifecycle_and_replay_is_inert(client):
    app = client.application
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    cid, v1_id, v2_id = _seed(classroom)
    token = "tok-http-1"

    response = client.post("/admin/run_payroll", data={"idempotency_token": token})
    assert response.status_code in (200, 302), response.data
    assert b"Database error" not in response.data

    # The manual command produced a resolvable completed run.
    key = f"manual-payroll:{cid}:{token}"
    cycle_id = resolve_completed_run(cid, key)
    assert cycle_id is not None

    # PROD: payroll events stamped with the run's cycle id.
    events = PayrollEvent.query.filter_by(
        class_id=cid, payroll_cycle_id=cycle_id, payroll_event_type="payroll"
    ).all()
    assert len(events) >= 1

    # ITR: exactly one immutable, complete record bound to the cycle.
    record = InterpretationCycleRecord.query.filter_by(class_id=cid, payroll_cycle_id=cycle_id).one()
    assert record.observations_json["coverage"]["complete"] is True

    # CLASS: the pending next-cycle policy activated.
    assert db.session.get(PolicyVersion, v2_id).is_active is True
    assert db.session.get(PolicyVersion, v1_id).is_active is False

    # --- Replay the SAME manual command: it must reproduce nothing. ---
    events_before = PayrollEvent.query.filter_by(class_id=cid).count()

    replay = client.post("/admin/run_payroll", data={"idempotency_token": token})
    assert replay.status_code in (200, 302), replay.data

    assert PayrollEvent.query.filter_by(class_id=cid).count() == events_before
    assert InterpretationCycleRecord.query.filter_by(class_id=cid).count() == 1
    # Still resolves to the original cycle id — no second cycle allocated.
    assert resolve_completed_run(cid, key) == cycle_id
