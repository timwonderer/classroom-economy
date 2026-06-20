"""
FEAT-STOR-006: Redemption Disposition — enforcement-active tests.

These tests are marked `enforce_feat` so the conftest does NOT wrap them in
the global FEATBypass. That means the FEAT constitutional enforcement
(before_flush listener in app/feats/base.py) is fully live during the route
calls. If the routes' @feat_shell decorator is removed, these tests will
fail loudly with FEATContextError instead of silently passing.

FEATBypass is used only inside fixture-setup blocks where we're seeding rows,
not exercising business logic.
"""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.extensions import db
from app.feats.base import FEATBypass
from app.models import (
    Admin,
    ClassEconomy,
    ClassMembership,
    IdentityProfile,
    RedemptionAuditAction,
    RedemptionAuditLog,
    Seat,
    StoreItem,
    Student,
    StudentItem,
    Transaction,
    TransactionStatus,
    User,
    UserRole,
)
from app.utils.auth_username import build_hashed_username_fields
from tests.helpers.v2_fixtures import make_admin


def _seed_redemption_scenario(*, username: str, join_code: str, item_price: Decimal):
    """
    Seed a realistic redemption scenario: one teacher (with canonical User),
    one student, one seat, one store item, and one StudentItem in 'processing'
    state with a matching purchase transaction.

    All seeding occurs inside FEATBypass — this is fixture construction, not
    a business path under test.

    Returns a dict of primary-key IDs (not detached ORM objects) so callers
    can rehydrate after a route call.
    """
    with FEATBypass():
        admin = make_admin(username, "secret")
        salt, uh, ulh = build_hashed_username_fields(username)
        user = User(
            username_hash=uh,
            username_lookup_hash=ulh,
            password_hash="x",
            user_role=UserRole.TEACHER,
            totp_secret_encrypted="x",
        )
        db.session.add_all([admin, user])
        db.session.flush()
        admin.user_id = user.id

        profile = IdentityProfile(profile_type="student", first_name="X", last_name="S")
        db.session.add(profile)
        db.session.flush()
        student = Student(identity_profile=profile, block="A", salt=b"salt")
        db.session.add(student)
        db.session.flush()

        economy = ClassEconomy(
            join_code=join_code,
            teacher_id=admin.id,
            status="active",
            created_by_admin_id=admin.id,
        )
        db.session.add(economy)
        db.session.flush()
        db.session.add(
            ClassMembership(class_id=economy.class_id, admin_id=admin.id, role="admin")
        )

        seat = Seat(
            student_id=student.id,
            class_id=economy.class_id,
            join_code=join_code,
            block="A",
            role="student",
        )
        db.session.add(seat)
        db.session.flush()

        item = StoreItem(
            name="Prize",
            price=item_price,
            teacher_id=admin.id,
            class_id=economy.class_id,
            is_active=True,
        )
        db.session.add(item)
        db.session.flush()

        # Original purchase transaction (the money that left the student's account)
        purchase_tx = Transaction(
            seat_id=seat.id,
            class_id=economy.class_id,
            teacher_id=admin.id,
            amount=-item_price,
            account_type="checking",
            type="purchase",
            status=TransactionStatus.PENDING,
            description=f"Purchase: {item.name}",
            join_code=join_code,
        )
        db.session.add(purchase_tx)
        db.session.flush()

        # Redemption transaction (the held-pending entry created by /use-item)
        redemption_tx = Transaction(
            seat_id=seat.id,
            class_id=economy.class_id,
            teacher_id=admin.id,
            amount=Decimal("0.00"),
            account_type="checking",
            type="redemption",
            status=TransactionStatus.PENDING,
            description=f"Used: {item.name}",
            join_code=join_code,
        )
        db.session.add(redemption_tx)
        db.session.flush()

        si = StudentItem(
            correlation_id=f"c-{username}",
            student_id=student.id,
            seat_id=seat.id,
            class_id=economy.class_id,
            store_item_id=item.id,
            status="processing",
            join_code=join_code,
        )
        db.session.add(si)
        db.session.flush()

        # Snapshot all IDs BEFORE commit; SQLAlchemy expires attributes on commit
        # and we don't want to re-read them through a closed transaction.
        snapshot = {
            "admin_id": admin.id,
            "user_id": user.id,
            "student_id": student.id,
            "class_id": economy.class_id,
            "seat_id": seat.id,
            "item_id": item.id,
            "student_item_id": si.id,
            "purchase_tx_id": purchase_tx.id,
            "redemption_tx_id": redemption_tx.id,
        }
        db.session.commit()
        return snapshot


def _login_canonical_admin(client, *, admin_id: int, user_id: int):
    with client.session_transaction() as sess:
        sess["admin_id"] = admin_id
        sess["user_id"] = user_id
        sess["is_admin"] = True
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()


@pytest.mark.enforce_feat
def test_approve_redemption_succeeds_under_feat_enforcement(client):
    """
    With FEAT enforcement ACTIVE (no global FEATBypass), POST /api/approve-redemption
    must succeed end-to-end: 200 response, audit row written, item status flipped.

    Before FEAT-STOR-006 was added, this exact path raised FEATContextError → 500.
    """
    ids = _seed_redemption_scenario(
        username="approver_enforced",
        join_code="ENF001",
        item_price=Decimal("10.00"),
    )
    _login_canonical_admin(client, admin_id=ids["admin_id"], user_id=ids["user_id"])

    resp = client.post(
        "/api/approve-redemption",
        json={"student_item_id": ids["student_item_id"]},
    )

    assert resp.status_code == 200, f"expected 200 under enforcement, got {resp.status_code}: {resp.data!r}"
    assert resp.json["status"] == "success"

    # Audit row persisted
    audit_rows = RedemptionAuditLog.query.filter_by(
        student_item_id=ids["student_item_id"],
        action=RedemptionAuditAction.APPROVED,
    ).all()
    assert len(audit_rows) == 1
    assert audit_rows[0].teacher_id == ids["admin_id"]
    assert audit_rows[0].class_id == ids["class_id"]

    # Item state advanced
    refetched_item = db.session.get(StudentItem, ids["student_item_id"])
    assert refetched_item.status == "completed"

    # Redemption transaction description rewritten
    refetched_tx = db.session.get(Transaction, ids["redemption_tx_id"])
    assert refetched_tx.description.startswith("Redeemed:")


@pytest.mark.enforce_feat
def test_reject_redemption_succeeds_and_creates_refund_under_enforcement(client):
    """
    POST /api/reject-redemption under live enforcement: 200, audit row, refund Tx,
    item status set to 'rejected'.
    """
    ids = _seed_redemption_scenario(
        username="rejecter_enforced",
        join_code="ENF002",
        item_price=Decimal("15.00"),
    )
    _login_canonical_admin(client, admin_id=ids["admin_id"], user_id=ids["user_id"])

    resp = client.post(
        "/api/reject-redemption",
        json={"student_item_id": ids["student_item_id"]},
    )

    assert resp.status_code == 200, f"expected 200 under enforcement, got {resp.status_code}: {resp.data!r}"
    assert resp.json["status"] == "success"

    # Audit row persisted
    audit_rows = RedemptionAuditLog.query.filter_by(
        student_item_id=ids["student_item_id"],
        action=RedemptionAuditAction.REJECTED,
    ).all()
    assert len(audit_rows) == 1

    # Item is in terminal rejected state
    refetched_item = db.session.get(StudentItem, ids["student_item_id"])
    assert refetched_item.status == "rejected"
    assert refetched_item.redemption_details and "Status: rejected" in refetched_item.redemption_details

    # Refund transaction created with positive amount equal to item price
    refund_txs = Transaction.query.filter_by(
        seat_id=ids["seat_id"],
        class_id=ids["class_id"],
        type="refund",
    ).all()
    assert len(refund_txs) == 1
    assert refund_txs[0].amount == Decimal("15.00")

    # Original purchase tx now points at the refund as its reversal
    purchase_tx = db.session.get(Transaction, ids["purchase_tx_id"])
    assert purchase_tx.reversal_transaction_id == refund_txs[0].id


@pytest.mark.enforce_feat
def test_approve_rejects_non_processing_item_with_409(client):
    """
    Business-rule failure (item not in 'processing' state) should be caught
    by the route as RedemptionDispositionError and converted to a 409, NOT
    leak as a 500 or a FEATContextError.
    """
    ids = _seed_redemption_scenario(
        username="approver_stale",
        join_code="ENF003",
        item_price=Decimal("5.00"),
    )

    # Advance item to a terminal state before the route call
    with FEATBypass():
        si = db.session.get(StudentItem, ids["student_item_id"])
        si.status = "completed"
        db.session.commit()

    _login_canonical_admin(client, admin_id=ids["admin_id"], user_id=ids["user_id"])
    resp = client.post(
        "/api/approve-redemption",
        json={"student_item_id": ids["student_item_id"]},
    )

    # The route's pre-FEAT validation also catches this (returns 404 "already processed").
    # The point of this test is: under enforcement, the route does not 500.
    assert resp.status_code in (404, 409), f"got {resp.status_code}: {resp.data!r}"
    assert resp.status_code != 500


@pytest.mark.enforce_feat
def test_approve_redemption_missing_student_item_id_returns_400(client):
    """Pure validation path — must not reach FEAT, must not 500."""
    ids = _seed_redemption_scenario(
        username="approver_validate",
        join_code="ENF004",
        item_price=Decimal("1.00"),
    )
    _login_canonical_admin(client, admin_id=ids["admin_id"], user_id=ids["user_id"])

    resp = client.post("/api/approve-redemption", json={})
    assert resp.status_code == 400
    assert resp.json["status"] == "error"


@pytest.mark.enforce_feat
def test_approve_redemption_rejects_intruder_admin_with_403(client):
    """Authorization gate must fire before the FEAT body runs."""
    owner = _seed_redemption_scenario(
        username="owner_admin_isolation",
        join_code="ENF005A",
        item_price=Decimal("10.00"),
    )

    # Build a separate canonical admin who has NO membership in owner's class
    with FEATBypass():
        intruder_admin = make_admin("intruder_isolation", "secret")
        salt, uh, ulh = build_hashed_username_fields("intruder_isolation")
        intruder_user = User(
            username_hash=uh,
            username_lookup_hash=ulh,
            password_hash="x",
            user_role=UserRole.TEACHER,
            totp_secret_encrypted="x",
        )
        db.session.add_all([intruder_admin, intruder_user])
        db.session.flush()
        intruder_admin.user_id = intruder_user.id
        db.session.flush()
        # Snapshot IDs before commit (post-commit attribute access requires a live tx).
        intruder_admin_id = intruder_admin.id
        intruder_user_id = intruder_user.id
        db.session.commit()

    _login_canonical_admin(client, admin_id=intruder_admin_id, user_id=intruder_user_id)

    resp = client.post(
        "/api/approve-redemption",
        json={"student_item_id": owner["student_item_id"]},
    )
    assert resp.status_code == 403

    # And state was NOT mutated
    refetched = db.session.get(StudentItem, owner["student_item_id"])
    assert refetched.status == "processing"
    assert RedemptionAuditLog.query.filter_by(student_item_id=owner["student_item_id"]).count() == 0
