from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.extensions import db
from app.feats.base import FEATContext
from app.feats.prod import (
    record_attendance_session,
    record_hall_pass_log,
    record_payroll_event,
    record_payroll_reversal,
)
from app.models import AttendanceSession, EntitlementEvent, HallPassLog, PayrollEvent, PolicyVersion, Transaction
from app.services.context_resolver import CanonicalContext
from app.services.entitlement_service import grant_hall_passes, get_hall_pass_balance, remove_hall_passes
from tests.helpers.classroom_initializer import initialize


def _teacher_ctx(classroom) -> CanonicalContext:
    return CanonicalContext(
        user_id=classroom.teacher_user.id,
        class_id=classroom.class_id,
        seat_id=classroom.teacher_seat.id,
        actor_role="teacher",
    )


def _student_ctx(classroom, index: int = 0) -> CanonicalContext:
    student = classroom.students[index]
    return CanonicalContext(
        user_id=student.user.id,
        class_id=classroom.class_id,
        seat_id=student.seat.id,
        actor_role="student",
    )


def _active_payroll_policy_version(classroom) -> PolicyVersion:
    with FEATContext("FEAT-BYPASS-LEGACY", correlation_id="bypass_test_payroll_policy_seed"):
        policy = PolicyVersion(
            class_id=classroom.class_id,
            domain="payroll",
            version_number=1,
            policy_payload_json='{"source":"test"}',
            activated_at=datetime(2026, 7, 19, 15, 0, tzinfo=timezone.utc),
            is_active=True,
        )
        db.session.add(policy)
        db.session.flush()
    return policy


def test_FEAT_PROD_001__records_attendance_session(app):
    classroom = initialize("chemistry_p1", app)
    ctx = _student_ctx(classroom)
    now = datetime(2026, 7, 19, 15, 0, tzinfo=timezone.utc)

    result = record_attendance_session(
        ctx=ctx,
        status="inactive",
        reason="hall pass",
        hall_pass_id="HP-001",
        correlation_id="corr-att-001",
        idempotency_key="feat:prod:attendance:001",
        reference_time_utc=now,
    )

    session = db.session.get(AttendanceSession, result.session.id)
    assert session is not None
    assert session.target_seat_id == ctx.seat_id
    assert session.actor_seat_id == ctx.seat_id
    assert session.target_user_id == ctx.user_id
    assert session.class_id == ctx.class_id
    assert session.hall_pass_id == "HP-001"
    assert session.status == "inactive"
    assert session.reason_code == "hall_pass"
    assert session.timestamp == now
    assert session.mechanism == "self"


def test_FEAT_PROD_002__records_hall_pass_and_consumes_entitlement(app):
    classroom = initialize("chemistry_p1", app)
    student = classroom.students[0]
    ctx = _teacher_ctx(classroom)
    with FEATContext("FEAT-BYPASS-LEGACY", correlation_id="bypass_test_hall_pass_seed"):
        grant_hall_passes(
            student.seat,
            1,
            trigger_id="seed:hall-pass",
            correlation_id="corr-hall-pass-grant-001",
        )

    result = record_hall_pass_log(
        ctx=ctx,
        requested_by_seat_id=student.seat.id,
        approved_by_seat_id=classroom.teacher_seat.id,
        destination="Office",
        reason="office",
        idempotency_key="feat:prod:hallpass:002",
        reference_time_utc=datetime(2026, 7, 19, 15, 15, tzinfo=timezone.utc),
    )

    log = db.session.get(HallPassLog, result.hall_pass_log.id)
    assert log is not None
    assert log.correlation_id == "corr-hall-pass-grant-001"
    assert log.destination == "Office"
    assert log.class_id == classroom.class_id
    assert log.requested_by_seat_id == student.seat.id
    assert log.approved_by_seat_id == classroom.teacher_seat.id
    consume_event = EntitlementEvent.query.filter_by(
        seat_id=student.seat.id,
        class_id=classroom.class_id,
        quantity_delta=-1,
    ).one()
    assert consume_event.correlation_id == log.correlation_id
    assert consume_event.entitlement_id == log.hall_pass_id
    grant_event = EntitlementEvent.query.filter_by(
        seat_id=student.seat.id,
        class_id=classroom.class_id,
        quantity_delta=1,
    ).one()
    assert grant_event.entitlement_id == log.hall_pass_id
    assert grant_event.correlation_id == log.correlation_id
    assert get_hall_pass_balance(student.seat.id, classroom.class_id) == 0


def test_FEAT_PROD_002__removes_hall_passes_by_reversing_entitlement_identity(app):
    classroom = initialize("chemistry_p1", app)
    student = classroom.students[0]
    with FEATContext("FEAT-BYPASS-LEGACY", correlation_id="bypass_test_hall_pass_remove_seed"):
        grant_hall_passes(
            student.seat,
            3,
            correlation_id="corr-hall-pass-removal-grant-001",
        )

    with FEATContext("FEAT-ENT-001", idempotency_key="feat:ent:hallpass:remove:001"):
        new_balance = remove_hall_passes(student.seat, 2)

    assert new_balance == 1
    grants = EntitlementEvent.query.filter_by(
        seat_id=student.seat.id,
        class_id=classroom.class_id,
        quantity_delta=1,
        event_type="GRANT",
    ).all()
    reversals = EntitlementEvent.query.filter_by(
        seat_id=student.seat.id,
        class_id=classroom.class_id,
        quantity_delta=-1,
        event_type="REVOCATION",
    ).all()
    assert len(grants) == 3
    assert len({grant.entitlement_id for grant in grants}) == 3
    assert len(reversals) == 2
    assert {reversal.correlation_id for reversal in reversals} == {"corr-hall-pass-removal-grant-001"}
    assert {reversal.entitlement_id for reversal in reversals}.issubset(
        {grant.entitlement_id for grant in grants}
    )
    assert all(reversal.trigger_id == reversal.entitlement_id for reversal in reversals)


def test_FEAT_PROD_003__records_payroll_event_and_reversal(app):
    classroom = initialize("chemistry_p1", app)
    student = classroom.students[0]
    ctx = _teacher_ctx(classroom)
    now = datetime(2026, 7, 19, 15, 30, tzinfo=timezone.utc)
    policy_version = _active_payroll_policy_version(classroom)

    record_attendance_session(
        ctx=_student_ctx(classroom),
        status="active",
        reference_time_utc=now - timedelta(minutes=10),
    )
    record_attendance_session(
        ctx=_student_ctx(classroom),
        status="inactive",
        reason="done_for_day",
        reference_time_utc=now,
    )

    payroll = record_payroll_event(
        ctx=ctx,
        target_seat_id=student.seat.id,
        payroll_event_type="payroll",
        correlation_id="corr-pay-001",
        idempotency_key="feat:prod:payroll:001",
        policy_version_id=policy_version.id,
        mechanism="TEACHER",
        summary_json={"description": "attendance-based payroll"},
        reference_time_utc=now,
    )

    payroll_event = db.session.get(PayrollEvent, payroll.payroll_event.id)
    assert payroll_event is not None
    assert payroll_event.payroll_event_type == "payroll"
    assert payroll_event.correlation_id == "corr-pay-001"
    assert payroll.ledger_transaction is not None
    assert Decimal(payroll.ledger_transaction.amount) > Decimal("0.00")

    reversal = record_payroll_reversal(
        ctx=ctx,
        target_seat_id=student.seat.id,
        correlation_id="corr-pay-001",
        idempotency_key="feat:prod:payroll:001:reversal",
        policy_version_id=policy_version.id,
        mechanism="TEACHER",
        summary_json={"description": "payroll reversal"},
        reference_time_utc=now + timedelta(minutes=5),
    )

    reversal_event = db.session.get(PayrollEvent, reversal.payroll_event.id)
    assert reversal_event is not None
    assert reversal_event.payroll_event_type == "reversal"
    assert reversal_event.correlation_id == "corr-pay-001"
    assert reversal.ledger_transaction is not None
    assert Decimal(reversal.ledger_transaction.amount) == -Decimal(payroll.ledger_transaction.amount)
