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
