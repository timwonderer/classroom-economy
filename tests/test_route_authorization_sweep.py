
from datetime import datetime, timezone, timedelta
import secrets
from tests.helpers.v2_fixtures import seed_canonical_admin
from tests.helpers.class_scope import make_student_identity, create_class_scope
import pytest
from app.extensions import db
from app.feats.base import FEATContext
from app.models import User, UserRole, ClassEconomy, Transaction, TransactionStatus, StoreItem, StorePurchase, IssueCategory, Issue, Seat, ClassFeature, IdentityProfile
from tests.helpers.admin_context import login_teacher
from tests.helpers.canonical_session import set_canonical_context

def _login_admin(client, user_id, class_id=None):
    user = db.session.get(User, user_id)
    if user is None:
        return
    if class_id is None:
        login_teacher(client, user)
        return
    teacher_seat = Seat.query.filter_by(class_id=class_id, user_id=user_id, role="teacher").first()
    if teacher_seat is not None:
        login_teacher(client, user, class_id=class_id, seat_id=teacher_seat.id)
        return
    login_teacher(client, user)

def _login_student(client, student_user_id, class_id, seat_id):
    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=student_user_id,
            class_id=class_id,
            seat_id=seat_id,
            role="student",
        )

def test_hall_pass_active_requires_teacher_seat_public_id_and_scopes_to_one_class(client):
    """Verification display should require one class-bound teacher seat public ID."""
    admin = seed_canonical_admin("hall_pass_admin", "secret").user
    other_admin = seed_canonical_admin("hall_pass_other", "secret").user
    db.session.flush()

    class_a = create_class_scope(teacher_user=admin, join_code="RAS-A", section="A")
    class_b = create_class_scope(teacher_user=admin, join_code="RAS-B", section="B")
    class_other = create_class_scope(teacher_user=other_admin, join_code="RAS-C", section="C")
    db.session.flush()

    student_a_seat = make_student_identity(class_id=class_a.class_id, first_name="Alpha", last_name="A")
    student_b_seat = make_student_identity(class_id=class_other.class_id, first_name="Bravo", last_name="B")
    db.session.flush()

    teacher_seat_a = Seat.query.filter_by(class_id=class_a.class_id, role="teacher").first()
    teacher_seat_b = Seat.query.filter_by(class_id=class_b.class_id, role="teacher").first()

    from app.models import HallPassLog
    now = datetime.now(timezone.utc)
    with FEATContext("FEAT-ATTN-001", idempotency_key="route_authorization_sweep:hall_pass_logs"):
        db.session.add_all([
            HallPassLog(
                seat_id=student_a_seat.id,
                reason="Restroom",
                status="left",
                period="A",
                class_id=class_a.class_id,
                left_time=now,
                request_time=now,
            ),
            HallPassLog(
                seat_id=student_a_seat.id,
                reason="Nurse",
                status="returned",
                period="B",
                class_id=class_b.class_id,
                left_time=now - timedelta(minutes=2),
                return_time=now - timedelta(minutes=1),
                request_time=now - timedelta(minutes=3),
            ),
            HallPassLog(
                seat_id=student_b_seat.id,
                reason="Office",
                status="left",
                period="A",
                class_id=class_other.class_id,
                left_time=now - timedelta(minutes=4),
                request_time=now - timedelta(minutes=4),
            ),
        ])
        db.session.flush()

    # 1. Missing actor/class context -> 400
    response = client.get("/api/hall-pass/verification/active")
    assert response.status_code == 400
    assert b"actor and class_id are required" in response.data

    # 2. Cross-class actor reuse -> 404
    response = client.get(
        f"/api/hall-pass/verification/active?actor={teacher_seat_a.public_id}&class_id={class_b.class_id}"
    )
    assert response.status_code == 404

    # 3. Valid teacher seat scope includes only one class, even for a multi-class teacher.
    response = client.get(
        f"/api/hall-pass/verification/active?actor={teacher_seat_a.public_id}&class_id={class_a.class_id}"
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "success"
    destinations = [entry["destination"] for entry in payload["passes"]]
    assert "Restroom" in destinations
    assert "Nurse" not in destinations
    assert "Office" not in destinations

def test_approve_redemption_requires_membership(client):
    """Test that redemption approval requires admin membership in the class."""
    admin_owner = seed_canonical_admin("owner_admin", "secret").user
    admin_intruder = seed_canonical_admin("intruder_admin", "secret").user
    db.session.flush()

    class_row = create_class_scope(teacher_user=admin_owner, join_code="RAS-D")
    intruder_class_row = create_class_scope(teacher_user=admin_intruder, join_code="RAS-E")
    db.session.flush()

    student_seat = make_student_identity(class_id=class_row.class_id, first_name="Redeem", last_name="S")
    db.session.flush()

    with FEATContext("FEAT-STOR-001", idempotency_key="route_authorization_sweep:redemption_seed"):
        seat = Seat.query.filter_by(user_id=student_seat.user_id, class_id=class_row.class_id, role="student").first()
        item = StoreItem(name="Prize", price=10, user_id=admin_owner.id, class_id=class_row.class_id, is_active=True)
        db.session.add(item)
        db.session.flush()

        student_item = StorePurchase(
            seat_id=seat.id,
            class_id=class_row.class_id,
            store_item_id=item.id,
            quantity=1,
            price_at_purchase=item.price,
            total_price=item.price,
            status="processing",
        )
        db.session.add(student_item)
        db.session.flush()

    db.session.commit()

    # Intruder tries to approve
    intruder_teacher_seat = Seat.query.filter_by(class_id=intruder_class_row.class_id, user_id=admin_intruder.id, role="teacher").first()
    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=admin_intruder.id,
            class_id=intruder_class_row.class_id,
            seat_id=intruder_teacher_seat.id,
            role="teacher",
        )
    response = client.post("/api/approve-redemption", json={"student_item_id": student_item.id})
    assert response.status_code == 403, response.headers.get("Location")
    assert b"You do not have access to this class" in response.data

    # Owner tries to approve
    owner_teacher_seat = Seat.query.filter_by(class_id=class_row.class_id, user_id=admin_owner.id, role="teacher").first()
    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=admin_owner.id,
            class_id=class_row.class_id,
            seat_id=owner_teacher_seat.id,
            role="teacher",
        )
    response = client.post("/api/approve-redemption", json={"student_item_id": student_item.id})
    assert response.status_code == 200, response.headers.get("Location")
    assert b"success" in response.data

def test_file_claim_scoped_to_class(client):
    """Test that insurance claims are scoped to the class of the policy."""
    admin = seed_canonical_admin("claim_admin", "secret").user
    db.session.flush()

    class_a = create_class_scope(teacher_user=admin, join_code="RAS-F", section="A")
    class_b = create_class_scope(teacher_user=admin, join_code="RAS-G", section="B")
    db.session.flush()

    student_seat_a = make_student_identity(class_id=class_a.class_id, first_name="Claimer", last_name="S", claimed=True)
    db.session.flush()
    with FEATContext("FEAT-IDEN-001", idempotency_key="route_authorization_sweep:claimed_seat"):
        seat_b = Seat(user_id=student_seat_a.user_id, class_id=class_b.class_id, role="student", claimed_at=datetime.now(timezone.utc))
        db.session.add(seat_b)
        db.session.flush()
        db.session.add(IdentityProfile(seat_id=seat_b.id, profile_type='student_claimed', first_name="Claimer", last_name="S", class_id=class_b.class_id))
        db.session.flush()

    with FEATContext("FEAT-ADMN-001", idempotency_key="route_authorization_sweep:class_features"):
        db.session.add_all([
            ClassFeature(class_id=class_a.class_id, feature_name="insurance"),
            ClassFeature(class_id=class_b.class_id, feature_name="insurance"),
        ])
        db.session.flush()

    seat_a = Seat.query.filter_by(user_id=student_seat_a.user_id, class_id=class_a.class_id, role="student").first()

    from app.models import InsurancePolicy, InsuranceEnrollment
    with FEATContext("FEAT-ADMN-001", idempotency_key="route_authorization_sweep:insurance_seed"):
        policy_a = InsurancePolicy(
            teacher_id=admin.id,
            policy_code="POL-A-1",
            tier_category_id=1,
            tier_level=1,
            title="Policy A",
            premium=10,
            claim_type="transaction_monetary",
            is_active=True
        )
        db.session.add(policy_a)
        db.session.flush()

        enrollment = InsuranceEnrollment(
            policy_id=policy_a.id,
            seat_id=seat_a.id,
            class_id=seat_a.class_id,
            status="active",
            coverage_start_date=datetime.now(timezone.utc) - timedelta(days=1))
        db.session.add(enrollment)

        tx_b = Transaction(
            user_id=student_seat_a.user_id,
            seat_id=seat_b.id,
            class_id=class_b.class_id,
            amount=-50,
            status=TransactionStatus.POSTED,
            type="fine",
            description="Fine in Class B",
            timestamp=datetime.now(timezone.utc)
        )
        tx_a = Transaction(
            user_id=student_seat_a.user_id,
            seat_id=seat_a.id,
            class_id=class_a.class_id,
            amount=-50,
            status=TransactionStatus.POSTED,
            type="fine",
            description="Fine in Class A",
            timestamp=datetime.now(timezone.utc)
        )
        db.session.add_all([tx_b, tx_a])
        db.session.flush()

    _login_student(client, student_seat_a.user_id, class_a.class_id, seat_a.id)

    response = client.post(
        f"/student/insurance/claim/{policy_a.id}",
        data={
            "transaction_id": tx_b.id,
            "claim_amount": 50,
            "incident_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "description": "Claiming fine from Class B"
        },
        follow_redirects=True
    )
    assert response.status_code == 200
    assert b"Claim submitted successfully" not in response.data

    response = client.post(
        f"/student/insurance/claim/{policy_a.id}",
        data={
            "transaction_id": tx_a.id,
            "claim_amount": 50,
            "incident_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "description": "Claiming fine from Class A"
        },
        follow_redirects=True
    )
    assert response.status_code == 200
    assert b"Selected transaction is not eligible for claims." not in response.data
