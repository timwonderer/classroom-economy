"""Slice 8.3f — automatic (scheduled) payroll.

Automatic payroll is a second initiation mechanism for the same canonical
economic-cycle completion; the scheduler owns only "is this class due now?" and
then calls ``complete_payroll_cycle``. These tests prove:

* a due class runs the full lifecycle through FEAT-PROD-004 (events + ITR record +
  policy activation + completion anchor keyed by the scheduled occurrence);
* ``next_payroll_date`` advances so the class is no longer due, and a second job
  tick is inert;
* the scheduled occurrence is the deterministic command identity: replaying the
  same occurrence (date not advanced) resolves the completed run and reproduces
  nothing.
"""

from __future__ import annotations

from datetime import timedelta

from app.extensions import db
from app.feats.base import FEATContext
from app.models import (
    AttendanceSession,
    InterpretationCycleRecord,
    PayrollEvent,
    PayrollSettings,
    PolicyTransition,
    PolicyVersion,
)
from app.scheduled_tasks import run_automatic_payroll_job
from app.services.payroll.cycle_completion import resolve_completed_run
from app.utils.canonical_temporal_resolver import utc_now
from tests.helpers.classroom_initializer import initialize


def _seed_due_class(classroom, *, due=True):
    cid = classroom.class_id
    student = classroom.students[0]
    now = utc_now()
    occurrence = (now - timedelta(minutes=1)) if due else (now + timedelta(days=7))

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
        settings = PayrollSettings.query.filter_by(class_id=cid).first()
        if settings is None:
            settings = PayrollSettings(class_id=cid, pay_rate=0.25)
            db.session.add(settings)
        settings.is_active = True
        settings.next_payroll_date = occurrence
        settings.payroll_frequency_days = 14
        db.session.flush()
        v1_id, v2_id = v1.id, v2.id

    with FEATContext("FEAT-PROD-001", correlation_id=f"att:{cid}", idempotency_key=f"att:{cid}"):
        db.session.add(AttendanceSession(
            target_seat_id=student.seat.id, class_id=cid, target_user_id=student.user.id,
            actor_seat_id=classroom.teacher_seat_id, reason_code="start_work",
            timestamp=now - timedelta(minutes=30),
        ))
        db.session.flush()

    return cid, v1_id, v2_id, occurrence


def test_due_class_runs_full_lifecycle_and_advances_next_date(app):
    classroom = initialize("chemistry_p1", app)
    cid, v1_id, v2_id, occurrence = _seed_due_class(classroom, due=True)

    run_automatic_payroll_job()

    key = f"auto-payroll:{cid}:{occurrence.isoformat()}"
    cycle_id = resolve_completed_run(cid, key)
    assert cycle_id is not None

    assert PayrollEvent.query.filter_by(
        class_id=cid, payroll_cycle_id=cycle_id, payroll_event_type="payroll"
    ).count() >= 1
    record = InterpretationCycleRecord.query.filter_by(class_id=cid, payroll_cycle_id=cycle_id).one()
    assert record.observations_json["coverage"]["complete"] is True
    assert db.session.get(PolicyVersion, v2_id).is_active is True
    assert db.session.get(PolicyVersion, v1_id).is_active is False

    # next_payroll_date advanced by one frequency → class no longer due.
    settings = PayrollSettings.query.filter_by(class_id=cid).one()
    assert settings.next_payroll_date == occurrence + timedelta(days=14)

    # A second tick is inert — the class is not due.
    events_before = PayrollEvent.query.filter_by(class_id=cid).count()
    run_automatic_payroll_job()
    assert PayrollEvent.query.filter_by(class_id=cid).count() == events_before
    assert InterpretationCycleRecord.query.filter_by(class_id=cid).count() == 1


def test_not_due_class_is_skipped(app):
    classroom = initialize("chemistry_p1", app)
    cid, *_ = _seed_due_class(classroom, due=False)

    run_automatic_payroll_job()

    assert PayrollEvent.query.filter_by(class_id=cid).count() == 0
    assert InterpretationCycleRecord.query.filter_by(class_id=cid).count() == 0


def test_replaying_same_occurrence_is_idempotent(app):
    classroom = initialize("chemistry_p1", app)
    cid, v1_id, v2_id, occurrence = _seed_due_class(classroom, due=True)

    run_automatic_payroll_job()
    events_after_first = PayrollEvent.query.filter_by(class_id=cid).count()
    assert events_after_first >= 1

    # Simulate the scheduled occurrence being retried (as if the advance had not
    # stuck): re-arm the SAME next_payroll_date, so the derived key is identical.
    with FEATContext("FEAT-BYPASS-LEGACY", correlation_id=f"rearm:{cid}"):
        settings = PayrollSettings.query.filter_by(class_id=cid).one()
        settings.next_payroll_date = occurrence
        db.session.flush()

    run_automatic_payroll_job()

    # The completion anchor for this occurrence already exists, so the FEAT
    # short-circuits: no new payroll events, still one interpretation record.
    assert PayrollEvent.query.filter_by(class_id=cid).count() == events_after_first
    assert InterpretationCycleRecord.query.filter_by(class_id=cid).count() == 1
