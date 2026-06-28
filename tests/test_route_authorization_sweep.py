
from datetime import datetime, timezone, timedelta
from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import pytest
from app.extensions import db
from app.models import Admin, ClassEconomy, ClassMembership, Student, Transaction, TransactionStatus, StoreItem, StudentItem, IssueCategory, Issue, Seat, ClassFeature, IdentityProfile

def _login_admin(client, admin_id):
    with client.session_transaction() as sess:
        sess["admin_id"] = admin_id
        sess["is_admin"] = True
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()

def _login_student(client, student_id):
    with client.session_transaction() as sess:
        sess["student_id"] = student_id
        sess["login_time"] = datetime.now(timezone.utc).isoformat()
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()

def test_hall_pass_active_requires_teacher_seat_public_id_and_scopes_to_one_class(client):
    """Verification display should require one class-bound teacher seat public ID."""
    admin = make_admin("hall_pass_admin", "secret")
    other_admin = make_admin("hall_pass_other", "secret")
    db.session.add(admin)
    db.session.add(other_admin)
    db.session.flush()

    profile_a = IdentityProfile(profile_type='student', first_name='Alpha', last_name='A')
    profile_b = IdentityProfile(profile_type='student', first_name='Bravo', last_name='B')
    db.session.add_all([profile_a, profile_b])
    db.session.flush()
    student_a = Student(identity_profile=profile_a, block="A", salt=b"salt")
    student_b = Student(identity_profile=profile_b, block="B", salt=b"salt")
    db.session.add_all([student_a, student_b])
    db.session.flush()

    class_a = ClassEconomy(join_code="HPASS01", user_id=admin.id, status="active", created_by_admin_id=admin.id)
    class_b = ClassEconomy(join_code="HPASS02", user_id=admin.id, status="active", created_by_admin_id=admin.id)
    class_other = ClassEconomy(join_code="HPASS99", user_id=other_admin.id, status="active", created_by_admin_id=other_admin.id)
    db.session.add_all([class_a, class_b, class_other])
    db.session.flush()
    teacher_seat_a = Seat(class_id=class_a.class_id, join_code="HPASS01", role="teacher")
    teacher_seat_b = Seat(class_id=class_b.class_id, join_code="HPASS02", role="teacher")
    db.session.add_all([
        teacher_seat_a,
        teacher_seat_b,
        Seat(class_id=class_other.class_id, join_code="HPASS99", role="teacher"),
        ClassMembership(join_code="HPASS01", admin_id=admin.id, role="admin"),
        ClassMembership(join_code="HPASS02", admin_id=admin.id, role="admin"),
        ClassMembership(join_code="HPASS99", admin_id=other_admin.id, role="admin"),
    ])

    from app.models import HallPassLog
    now = datetime.now(timezone.utc)
    db.session.add_all([
        HallPassLog(
            student_id=student_a.id,
            reason="Restroom",
            status="left",
            period="A",
            class_id=class_a.class_id,
            join_code="HPASS01",
            left_time=now,
            request_time=now,
        ),
        HallPassLog(
            student_id=student_a.id,
            reason="Nurse",
            status="returned",
            period="B",
            class_id=class_b.class_id,
            join_code="HPASS02",
            left_time=now - timedelta(minutes=2),
            return_time=now - timedelta(minutes=1),
            request_time=now - timedelta(minutes=3),
        ),
        HallPassLog(
            student_id=student_b.id,
            reason="Office",
            status="left",
            period="A",
            class_id=class_other.class_id,
            join_code="HPASS99",
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
    db.session.add_all([admin_owner, admin_intruder])
    db.session.flush()

    profile_redeem = IdentityProfile(profile_type='student', first_name='Redeem', last_name='S')
    db.session.add(profile_redeem)
    db.session.flush()
    student = Student(identity_profile=profile_redeem, block="A", salt=b"salt")
    db.session.add(student)
    db.session.flush()

    db.session.add(ClassEconomy(join_code="REDEEM1", user_id=admin_owner.id, status="active", created_by_admin_id=admin_owner.id))
    db.session.flush()
    class_row = ClassEconomy.query.filter_by(join_code="REDEEM1").first()
    db.session.add(ClassMembership(class_id=class_row.class_id, admin_id=admin_owner.id, role="admin"))
    # Intruder has NO membership
    
    # Create Item and StudentItem
    seat = Seat(student_id=student.id, class_id=class_row.class_id, join_code=class_row.join_code, block="A", role="student")
    db.session.add(seat)
    db.session.flush()
    item = StoreItem(name="Prize", price=10, teacher_id=admin_owner.id, class_id=class_row.class_id, is_active=True)
    db.session.add(item)
    db.session.flush()
    
    student_item = StudentItem(correlation_id='corr_test', 
        student_id=student.id,
        seat_id=seat.id,
        class_id=class_row.class_id,
        store_item_id=item.id,
        status="processing",
        join_code="REDEEM1"
    )
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
    # Setup: Admin with 2 classes, Student in both.
    admin = make_admin("claim_admin", "secret")
    db.session.add(admin)
    db.session.flush()
    
    profile_claimer = IdentityProfile(profile_type='student', first_name='Claimer', last_name='S')
    db.session.add(profile_claimer)
    db.session.flush()
    student = Student(identity_profile=profile_claimer, block="A", salt=b"salt")
    db.session.add(student)
    db.session.flush()

    # Class A and Class B
    db.session.add_all([
        ClassEconomy(join_code="CLAIM_A", user_id=admin.id, status="active", created_by_admin_id=admin.id),
        ClassEconomy(join_code="CLAIM_B", user_id=admin.id, status="active", created_by_admin_id=admin.id),
        ClassMembership(join_code="CLAIM_A", admin_id=admin.id, role="admin"),
        ClassMembership(join_code="CLAIM_B", admin_id=admin.id, role="admin"),
        ClassMembership(join_code="CLAIM_A", student_id=student.id, role="student"),
        ClassMembership(join_code="CLAIM_B", student_id=student.id, role="student"),
    ])
    db.session.flush()

    class_a = ClassEconomy.query.filter_by(join_code="CLAIM_A").first()
    class_b = ClassEconomy.query.filter_by(join_code="CLAIM_B").first()
    db.session.add_all([
        ClassFeature(class_id=class_a.class_id, feature_name="insurance"),
        ClassFeature(class_id=class_b.class_id, feature_name="insurance"),
    ])
    seat_a = Seat(student_id=student.id, class_id=class_a.class_id, join_code="CLAIM_A", block="A", block_identifier="A", role="student", claimed_at=datetime.now(timezone.utc))
    seat_b = Seat(student_id=student.id, class_id=class_b.class_id, join_code="CLAIM_B", block="B", block_identifier="B", role="student", claimed_at=datetime.now(timezone.utc))
    db.session.add_all([seat_a, seat_b])
    db.session.flush()
    db.session.add_all([
        IdentityProfile(seat_id=seat_a.id, profile_type='student_claimed', first_name="Claimer", last_name="S"),
        IdentityProfile(seat_id=seat_b.id, profile_type='student_claimed', first_name="Claimer", last_name="S"),
    ])

    # Policy in Class A
    from app.models import InsurancePolicy, InsuranceEnrollment
    policy_a = InsurancePolicy(
        teacher_id=admin.id,
        policy_code="POL-A-1",
        tier_category_id=1,
        tier_level=1,
        title="Policy A",
        premium=10,
        # deductible=0,
        # coverage_percent=100,
        claim_type="transaction_monetary",
        join_code="CLAIM_A",
        is_active=True
    )
    db.session.add(policy_a)
    db.session.flush()

    seat = Seat.query.filter_by(student_id=student.id, class_id=class_a.class_id).first()
    assert seat is not None
    enrollment = InsuranceEnrollment(
        policy_id=policy_a.id,
        seat_id=seat.id,
        class_id=seat.class_id,
        status="active",
        coverage_start_date=datetime.now(timezone.utc) - timedelta(days=1),
        join_code="CLAIM_A"
    )
    db.session.add(enrollment)

    # Transaction in Class B (should NOT be claimable under Policy A)
    tx_b = Transaction(
        student_id=student.id,
        seat_id=seat_b.id,
        class_id=class_b.class_id,
        teacher_id=admin.id,
        join_code="CLAIM_B",
        amount=-50,
        status=TransactionStatus.POSTED,
        type="fine",
        description="Fine in Class B",
        timestamp=datetime.now(timezone.utc)
    )
    # Transaction in Class A (Valid)
    tx_a = Transaction(
        student_id=student.id,
        seat_id=seat_a.id,
        class_id=class_a.class_id,
        teacher_id=admin.id,
        join_code="CLAIM_A",
        amount=-50,
        status=TransactionStatus.POSTED,
        type="fine",
        description="Fine in Class A",
        timestamp=datetime.now(timezone.utc)
    )
    db.session.add_all([tx_b, tx_a])
    db.session.commit()

    _login_student(client, student.id)
    # Set class context so get_current_class_context() resolves correctly
    with client.session_transaction() as sess:
        sess["current_join_code"] = "CLAIM_A"
        sess["current_class_id"] = class_a.class_id
    
    # 1. Try to claim Class B transaction on Policy A
    # The form submission takes transaction_id
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
    # Should fail: cross-class transaction is filtered out by strict scoping,
    # so form validation rejects it OR the route explicitly blocks it.
    assert response.status_code == 200  # Re-renders form (no redirect to success)
    assert b"Claim submitted successfully" not in response.data

    # 2. Claim Class A transaction (same class as policy) should not hit cross-class rejection
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
