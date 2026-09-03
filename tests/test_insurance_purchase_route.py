"""Slice E — student insurance marketplace/purchase routes wired to FEAT-OBL-004.

Proves the route layer: the marketplace lists IN_USE insurance_policies, and the
purchase route drives execute_purchase_insurance so a student can actually buy
coverage end-to-end (the original goal of the whole arc).
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from app.extensions import db
from app.feats.base import FEATContext
from app.feats.class_configuration import configure_insurance_definition
from app.services.context_resolver import CanonicalContext
from app.services import insurance_definition_service as insurance_defs
from app.services import entitlement_read_service
from app.models import InsuranceClaim
from app.feats.purchase_insurance_feat import execute_purchase_insurance
from app.utils.transaction_idempotency import create_idempotent_transaction
from tests.helpers.canonical_classroom import provision_classroom, login_student
from tests.helpers.class_domain import enable_class_feature


def _teacher_ctx(classroom):
    return CanonicalContext(
        user_id=classroom.teacher_user.id, class_id=classroom.class_id,
        seat_id=classroom.teacher_seat.id, actor_role="teacher",
    )


def _make_policy(classroom, premium="10.00"):
    row = configure_insurance_definition(
        class_id=classroom.class_id,
        submission=dict(
            insurance_type="TRANSACTION", premium=premium, charge_frequency="WEEKLY",
            reimbursement_percentage="80", payout_multiple="3",
            claims_per_week_equivalent="1", claim_window_days="7",
            title="Basic Cover",
        ),
        canonical_context=_teacher_ctx(classroom),
        correlation_id=f"corr_{uuid4().hex}",
        idempotency_key=f"cfg:{uuid4().hex}",
    )
    return row.policy_uuid


def _fund(seat, amount="100.00"):
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"fund:{seat.id}:{uuid4().hex}"):
        create_idempotent_transaction(
            idempotency_key=f"fund:{seat.id}:{uuid4().hex}",
            seat_id=seat.id, class_id=seat.class_id, target_seat_id=seat.id,
            actor_seat_id=seat.id, mechanism="self", user_id=seat.user_id,
            amount=Decimal(amount), account_type="checking", type="payroll",
            description="test funding",
        )
    db.session.commit()


def test_marketplace_lists_and_student_can_buy(app, client):
    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        enable_class_feature(class_id=classroom.class_id, feature="insurance")
        policy_uuid = _make_policy(classroom)
        student = classroom.students[0]
        _fund(student.seat)
        seat_id = student.seat.id
        class_id = classroom.class_id
        login_student(client, student)

    # Marketplace lists the available policy with a buy action.
    resp = client.get("/student/insurance")
    assert resp.status_code == 200
    assert b"Basic Cover" in resp.data
    assert b"Buy" in resp.data

    # Purchase drives FEAT-OBL-004.
    resp = client.post(f"/student/insurance/purchase/{policy_uuid}")
    assert resp.status_code == 302  # redirect back to the marketplace

    with app.app_context():
        assert entitlement_read_service.has_active_insurance_coverage(
            seat_id, class_id, policy_uuid) is True

    # Marketplace now shows it as owned (no buy button for it).
    resp = client.get("/student/insurance")
    assert resp.status_code == 200
    assert b"You have this coverage" in resp.data


def test_purchase_insufficient_funds_flashes_and_writes_nothing(app, client):
    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        enable_class_feature(class_id=classroom.class_id, feature="insurance")
        policy_uuid = _make_policy(classroom, premium="10.00")
        student = classroom.students[0]
        _fund(student.seat, "5.00")  # cannot afford the 10.00 premium
        seat_id = student.seat.id
        class_id = classroom.class_id
        login_student(client, student)

    resp = client.post(f"/student/insurance/purchase/{policy_uuid}", follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        assert entitlement_read_service.has_active_insurance_coverage(
            seat_id, class_id, policy_uuid) is False


def _student_ctx(classroom):
    s = classroom.students[0]
    return CanonicalContext(
        user_id=s.user.id, class_id=classroom.class_id,
        seat_id=s.seat.id, actor_role="student")


def _make_claimable_txn(seat):
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"txn:{seat.id}:{uuid4().hex}"):
        t, _created = create_idempotent_transaction(
            idempotency_key=f"claimtxn:{seat.id}:{uuid4().hex}",
            seat_id=seat.id, class_id=seat.class_id, target_seat_id=seat.id,
            actor_seat_id=seat.id, mechanism="self", user_id=seat.user_id,
            amount=Decimal("-20.00"), account_type="checking", type="purchase",
            description="Store purchase")
    db.session.commit()
    return t.id


def test_file_claim_form_and_submission(app, client):
    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        enable_class_feature(class_id=classroom.class_id, feature="insurance")
        policy_uuid = _make_policy(classroom)
        student = classroom.students[0]
        _fund(student.seat)
        # Hold coverage.
        execute_purchase_insurance(
            canonical_context=_student_ctx(classroom),
            policy_uuid=policy_uuid, idempotency_key=f"ins:{uuid4().hex}")
        db.session.commit()
        txn_id = _make_claimable_txn(student.seat)
        class_id, seat_id = classroom.class_id, student.seat.id
        login_student(client, student)

    # Claim form renders for held coverage.
    resp = client.get(f"/student/insurance/claim/{policy_uuid}")
    assert resp.status_code == 200
    assert b"New claim" in resp.data

    # Submitting a claim reaches FEAT-STOR-003 and records a claim.
    resp = client.post(f"/student/insurance/claim/{policy_uuid}",
                       data={"transaction_id": str(txn_id)})
    assert resp.status_code in (200, 302)
    with app.app_context():
        claims = InsuranceClaim.query.filter_by(class_id=class_id, target_seat_id=seat_id).count()
        assert claims == 1


def test_file_claim_fails_closed_without_coverage(app, client):
    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        enable_class_feature(class_id=classroom.class_id, feature="insurance")
        policy_uuid = _make_policy(classroom)  # exists in class, but student does NOT hold it
        student = classroom.students[0]
        class_id, seat_id = classroom.class_id, student.seat.id
        login_student(client, student)

    resp = client.get(f"/student/insurance/claim/{policy_uuid}", follow_redirects=False)
    assert resp.status_code == 302  # redirected away, fail-closed
    with app.app_context():
        assert InsuranceClaim.query.filter_by(class_id=class_id, target_seat_id=seat_id).count() == 0


def _make_productivity_policy(classroom):
    row = configure_insurance_definition(
        class_id=classroom.class_id,
        submission=dict(
            insurance_type="PRODUCTIVITY", premium="10.00", charge_frequency="WEEKLY",
            reimbursement_percentage="80", payout_multiple="5",
            claimable_dates_per_week_equivalent="5", title="Productivity Cover",
        ),
        canonical_context=_teacher_ctx(classroom),
        correlation_id=f"corr_{uuid4().hex}", idempotency_key=f"cfg:{uuid4().hex}",
    )
    return row.policy_uuid


def test_file_claim_productivity_form_renders_and_submits(app, client):
    from datetime import datetime, timezone
    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        enable_class_feature(class_id=classroom.class_id, feature="insurance")
        policy_uuid = _make_productivity_policy(classroom)
        student = classroom.students[0]
        _fund(student.seat)
        execute_purchase_insurance(
            canonical_context=_student_ctx(classroom),
            policy_uuid=policy_uuid, idempotency_key=f"ins:{uuid4().hex}")
        db.session.commit()
        class_id, seat_id = classroom.class_id, student.seat.id
        login_student(client, student)

    # The productivity claim surface renders (multi-date rows, not the txn picker).
    resp = client.get(f"/student/insurance/claim/{policy_uuid}")
    assert resp.status_code == 200
    assert b"Add another day" in resp.data
    assert b"Days you&#39;re claiming" in resp.data or b"Days you're claiming" in resp.data

    # A productivity submission reaches FEAT-STOR-003 and is surfaced gracefully by
    # the route (approval depends on the student's work records — a FEAT concern
    # covered end-to-end in test_insurance_claim_feat.py — so we assert the route
    # wiring never 500s and the claim_subject shape is accepted for parsing).
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    resp = client.post(
        f"/student/insurance/claim/{policy_uuid}",
        data={"claim_date": today, "claim_hours": "2.0",
              "claim_explanation": "Lost class time to a jam"},
    )
    assert resp.status_code in (200, 302)  # handled, never a server error


def _make_tier(classroom, group, level, premium="10.00"):
    row = configure_insurance_definition(
        class_id=classroom.class_id,
        submission=dict(
            insurance_type="TRANSACTION", premium=premium, charge_frequency="WEEKLY",
            reimbursement_percentage="80", payout_multiple="3",
            claims_per_week_equivalent="1", claim_window_days="7",
            title=f"{group} {level}", tier_group=group, tier_level=str(level),
        ),
        canonical_context=_teacher_ctx(classroom),
        correlation_id=f"corr_{uuid4().hex}",
        idempotency_key=f"cfg:{uuid4().hex}",
    )
    return row.policy_uuid


def test_grouped_marketplace_shows_group_and_cancel_stops_renewal(app, client):
    from app.services import obligations_service
    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        enable_class_feature(class_id=classroom.class_id, feature="insurance")
        basic = _make_tier(classroom, "Paycheck Protection", 1)
        _make_tier(classroom, "Paycheck Protection", 2)
        student = classroom.students[0]
        _fund(student.seat)
        seat_id = student.seat.id
        class_id = classroom.class_id
        login_student(client, student)

    # Marketplace groups the tiers under the group name.
    resp = client.get("/student/insurance")
    assert resp.status_code == 200
    assert b"Paycheck Protection" in resp.data

    # Buy the Basic tier.
    assert client.post(f"/student/insurance/purchase/{basic}").status_code == 302

    # The group now shows as enrolled; the other tier is unavailable (one per group).
    resp = client.get("/student/insurance")
    assert b"Enrolled" in resp.data
    assert b"Unavailable" in resp.data

    # Cancel via FEAT-OBL-005 — stop renewal (terminal bill cycle).
    resp = client.post(f"/student/insurance/cancel/{basic}")
    assert resp.status_code == 302

    with app.app_context():
        # The seat's premium lineage is now terminal (no next assessment).
        assessments = obligations_service.get_assessment_events_for_seat_class(
            seat_id, class_id, obligation_type="INSURANCE_PREMIUM")
        ref = assessments[0].internal_ref
        latest = obligations_service.get_latest_bill_cycle(ref)
        assert latest.next_assessment_at is None


def test_cancel_without_coverage_warns(app, client):
    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        enable_class_feature(class_id=classroom.class_id, feature="insurance")
        policy_uuid = _make_policy(classroom)
        student = classroom.students[0]
        login_student(client, student)

    resp = client.post(f"/student/insurance/cancel/{policy_uuid}", follow_redirects=True)
    assert resp.status_code == 200  # redirected back with a warning flash
