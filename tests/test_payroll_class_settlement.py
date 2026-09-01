"""Slice 8.3b — class-wide payroll-cycle settlement.

Settlement owns exactly one thing: settle the eligible class for one payroll cycle
under the governing configuration, stamping the same payroll_cycle_id on every
event, with NO commit of its own. The tests are nasty in the useful way:

* all eligible seats get the same payroll_cycle_id;
* a no-attendance seat is ineligible (current PROD doctrine) — no event;
* one per-seat failure lets the caller roll the whole transaction back;
* retry inside the same outer transaction manufactures no duplicate payroll rows;
* manual credits / reversals never become cycle-boundary events;
* no active payroll policy fails closed.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.extensions import db
from app.feats.base import FEATContext
from app.models import AttendanceSession, PayrollEvent, PolicyVersion
from app.services.payroll import settlement as settlement_module
from app.services.payroll.settlement import (
    ClassSettlementError,
    settle_class_payroll_cycle,
)
from app.utils.canonical_temporal_resolver import utc_now
from tests.helpers.classroom_initializer import initialize


def _seed(classroom, *, attend=("A", "B")):
    """Seed an active payroll policy + attendance for the named seats."""
    cid = classroom.class_id
    teacher_seat_id = classroom.teacher_seat_id
    sA, sB, sC, sD = classroom.students
    seat_map = {"A": sA, "B": sB, "C": sC, "D": sD}
    now = utc_now()

    with FEATContext("FEAT-BYPASS-LEGACY", correlation_id=f"pol:{cid}"):
        db.session.add(PolicyVersion(
            class_id=cid, domain="payroll", version_number=1,
            policy_payload_json="{}", activated_at=now, is_active=True,
        ))
        db.session.flush()

    with FEATContext("FEAT-PROD-001", correlation_id=f"att:{cid}", idempotency_key=f"att:{cid}"):
        for key in attend:
            seat = seat_map[key]
            db.session.add(AttendanceSession(
                target_seat_id=seat.seat_id, class_id=cid, target_user_id=seat.user.id,
                actor_seat_id=teacher_seat_id, reason_code="start_work",
                timestamp=now - timedelta(minutes=30),
            ))
        db.session.flush()

    return cid, now


def _cycle_events(cid, cycle_id):
    return PayrollEvent.query.filter_by(class_id=cid, payroll_cycle_id=cycle_id).all()


def test_all_eligible_seats_get_the_same_cycle_id(app):
    classroom = initialize("chemistry_p1", app)
    cid, now = _seed(classroom, attend=("A", "B"))
    sA, sB, sC, sD = classroom.students
    cycle_id = str(uuid4())

    with FEATContext("FEAT-PROD-004", idempotency_key=f"run:{cycle_id}"):
        result = settle_class_payroll_cycle(
            class_id=cid, payroll_cycle_id=cycle_id, boundary_utc=now,
        )

    assert set(result.settled_seat_ids) == {sA.seat_id, sB.seat_id}
    events = _cycle_events(cid, cycle_id)
    assert len(events) == 2
    assert all(e.payroll_cycle_id == cycle_id for e in events)
    assert all(e.payroll_event_type == "payroll" for e in events)
    assert {e.target_seat_id for e in events} == {sA.seat_id, sB.seat_id}


def test_seat_without_attendance_is_ineligible(app):
    classroom = initialize("chemistry_p1", app)
    cid, now = _seed(classroom, attend=("A",))  # only seat A attended
    sA, sB, sC, sD = classroom.students
    cycle_id = str(uuid4())

    with FEATContext("FEAT-PROD-004", idempotency_key=f"run:{cycle_id}"):
        result = settle_class_payroll_cycle(
            class_id=cid, payroll_cycle_id=cycle_id, boundary_utc=now,
        )

    assert result.settled_seat_ids == [sA.seat_id]
    # No-attendance seats never receive a payroll event.
    for absent in (sB, sC, sD):
        assert PayrollEvent.query.filter_by(
            class_id=cid, target_seat_id=absent.seat_id
        ).count() == 0


def test_manual_credits_and_reversals_are_not_cycle_events(app):
    classroom = initialize("chemistry_p1", app)
    cid, now = _seed(classroom, attend=("A", "B"))
    sA, sB, sC, sD = classroom.students

    # Pre-existing manual credit (not a cycle event) for seat C.
    with FEATContext("FEAT-PROD-003", correlation_id=f"mc:{cid}", idempotency_key=f"mc:{cid}"):
        policy = PolicyVersion.query.filter_by(class_id=cid, domain="payroll", is_active=True).first()
        db.session.add(PayrollEvent(
            class_id=cid, target_seat_id=sC.seat_id, target_user_id=sC.user.id,
            actor_seat_id=classroom.teacher_seat_id, correlation_id=f"corr_mc:{cid}",
            idempotency_key=f"mc:{cid}:evt", policy_version_id=policy.id,
            policy_uuid=policy.policy_uuid, mechanism="TEACHER",
            payroll_event_type="manual_credit", recorded_at=now, payroll_cycle_id=None,
        ))
        db.session.flush()

    cycle_id = str(uuid4())
    with FEATContext("FEAT-PROD-004", idempotency_key=f"run:{cycle_id}"):
        settle_class_payroll_cycle(class_id=cid, payroll_cycle_id=cycle_id, boundary_utc=now)

    # The manual credit is untouched — never stamped with the cycle id.
    manual = PayrollEvent.query.filter_by(
        class_id=cid, target_seat_id=sC.seat_id, payroll_event_type="manual_credit"
    ).one()
    assert manual.payroll_cycle_id is None

    # Settlement produced only 'payroll' events for the cycle — no manual/reversal.
    cycle_events = _cycle_events(cid, cycle_id)
    assert cycle_events
    assert {e.payroll_event_type for e in cycle_events} == {"payroll"}


def test_retry_in_same_transaction_makes_no_duplicates(app):
    classroom = initialize("chemistry_p1", app)
    cid, now = _seed(classroom, attend=("A", "B"))
    cycle_id = str(uuid4())

    with FEATContext("FEAT-PROD-004", idempotency_key=f"run:{cycle_id}"):
        first = settle_class_payroll_cycle(class_id=cid, payroll_cycle_id=cycle_id, boundary_utc=now)
        second = settle_class_payroll_cycle(class_id=cid, payroll_cycle_id=cycle_id, boundary_utc=now)

    assert len(first.settled_seat_ids) == 2
    assert second.settled_seat_ids == []                 # all already settled
    assert set(second.skipped_seat_ids) == set(first.settled_seat_ids)
    assert len(_cycle_events(cid, cycle_id)) == 2        # not doubled


def test_one_seat_failure_rolls_back_the_whole_transaction(app, monkeypatch):
    classroom = initialize("chemistry_p1", app)
    cid, now = _seed(classroom, attend=("A", "B"))
    cycle_id = str(uuid4())

    real = settlement_module.record_payroll_event
    calls = {"n": 0}

    def flaky(**kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return real(**kwargs)          # first seat settles (row flushed)
        raise RuntimeError("injected per-seat failure")

    monkeypatch.setattr(settlement_module, "record_payroll_event", flaky)

    with pytest.raises(RuntimeError):
        with FEATContext("FEAT-PROD-004", idempotency_key=f"run:{cycle_id}"):
            settle_class_payroll_cycle(class_id=cid, payroll_cycle_id=cycle_id, boundary_utc=now)

    # The whole transaction rolled back — even the first seat's flushed event is gone.
    assert _cycle_events(cid, cycle_id) == []


def test_no_active_payroll_policy_fails_closed(app):
    classroom = initialize("chemistry_p1", app)
    cid = classroom.class_id  # no policy seeded

    with pytest.raises(ClassSettlementError):
        with FEATContext("FEAT-PROD-004", idempotency_key="run:nopolicy"):
            settle_class_payroll_cycle(
                class_id=cid, payroll_cycle_id=str(uuid4()), boundary_utc=utc_now(),
            )
