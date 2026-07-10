
from datetime import datetime, timezone, timedelta
from tests.helpers.v2_fixtures import make_admin
from tests.helpers.class_scope import make_student_identity, create_class_scope
import pytest
from app.extensions import db
from app.models import User, UserRole, ClassEconomy, Transaction, TransactionStatus, StoreItem, StudentItem, IssueCategory, Issue, Seat, ClassFeature, IdentityProfile
from tests.helpers.canonical_session import set_canonical_context

def _login_admin(client, admin_id):
    with client.session_transaction() as sess:
        sess["user_id"] = admin_id
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()

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
    admin = make_admin("hall_pass_admin", "secret")
    other_admin = make_admin("hall_pass_other", "secret")
    db.session.flush()

    class_a = create_class_scope(teacher_user=admin, join_code="HPCLSA")
    class_b = create_class_scope(teacher_user=admin, join_code="HPCLSB")
    class_other = create_class_scope(teacher_user=other_admin, join_code="HPCLSO")
    db.session.flush()

    student_a_seat = make_student_identity(class_id=class_a.class_id, first_name="Alpha", last_name="A")
    student_b_seat = make_student_identity(class_id=class_other.class_id, first_name="Bravo", last_name="B")
    db.session.flush()

    teacher_seat_a = Seat.query.filter_by(class_id=class_a.class_id, role="teacher").first()
    teacher_seat_b = Seat.query.filter_by(class_id=class_b.class_id, role="teacher").first()

    from app.models import HallPassLog
    now = datetime.now(timezone.utc)
    db.session.add_all([
        HallPassLog(
            user_id=student_a_seat.user_id,
            reason="Restroom",
            status="left",
            period="A",
            class_id=class_a.class_id,
            left_time=now,
            request_time=now,
        ),
        HallPassLog(
            user_id=student_a_seat.user_id,
            reason="Nurse",
            status="returned",
            period="B",
            class_id=class_b.class_id,
            left_time=now - timedelta(minutes=2),
            return_time=now - timedelta(minutes=1),
            request_time=now - timedelta(minutes=3),
        ),
        HallPassLog(
            user_id=student_b_seat.user_id,
            reason="Office",
            status="left",
            period="A",
            class_id=class_other.class_id,
            left_time=now - timedelta(minutes=4),
            request_time=now - timedelta(minutes=4),
        ),
    ])
    db.session.commit()

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
    admin_owner = make_admin("owner_admin", "secret")
    admin_intruder = make_admin("intruder_admin", "secret")
    db.session.flush()

    class_row = create_class_scope(teacher_user=admin_owner, join_code="REDEEM1")
    db.session.flush()

    student_seat = make_student_identity(class_id=class_row.class_id, first_name="Redeem", last_name="S")
    db.session.flush()

    seat = Seat.query.filter_by(user_id=student_seat.user_id, class_id=class_row.class_id, role="student").first()
    item = StoreItem(name="Prize", price=10, user_id=admin_owner.id, class_id=class_row.class_id, is_active=True)
    db.session.add(item)
    db.session.flush()

    student_item = StudentItem(correlation_id='corr_test',
        user_id=student_seat.user_id,
        seat_id=seat.id,
        class_id=class_row.class_id,
        store_item_id=item.id,
        status="processing")
    db.session.add(student_item)
    db.session.commit()

    # Intruder tries to approve
    _login_admin(client, admin_intruder.id)
    response = client.post("/api/approve-redemption", json={"student_item_id": student_item.id})
    assert response.status_code == 403
    assert b"You do not have access to this class" in response.data

    # Owner tries to approve
    _login_admin(client, admin_owner.id)
    response = client.post("/api/approve-redemption", json={"student_item_id": student_item.id})
    assert response.status_code == 200
    assert b"success" in response.data

def test_file_claim_scoped_to_class(client):
    """Test that insurance claims are scoped to the class of the policy."""
    admin = make_admin("claim_admin", "secret")
    db.session.flush()

    class_a = create_class_scope(teacher_user=admin, join_code="CLAIM_A")
    class_b = create_class_scope(teacher_user=admin, join_code="CLAIM_B")
    db.session.flush()

    student_seat_a = make_student_identity(class_id=class_a.class_id, first_name="Claimer", last_name="S", claimed=True)
    db.session.flush()
    seat_b = Seat(user_id=student_seat_a.user_id, class_id=class_b.class_id, block="B", block_identifier="B", role="student", claimed_at=datetime.now(timezone.utc))
    db.session.add(seat_b)
    db.session.flush()
    db.session.add(IdentityProfile(seat_id=seat_b.id, profile_type='student_claimed', first_name="Claimer", last_name="S", class_id=class_b.class_id))
    db.session.flush()

    db.session.add_all([
        ClassFeature(class_id=class_a.class_id, feature_name="insurance"),
        ClassFeature(class_id=class_b.class_id, feature_name="insurance"),
    ])

    seat_a = Seat.query.filter_by(user_id=student_seat_a.user_id, class_id=class_a.class_id, role="student").first()

    from app.models import InsurancePolicy, InsuranceEnrollment
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
    db.session.commit()

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
