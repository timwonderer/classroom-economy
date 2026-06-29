from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import pytest
from datetime import datetime, timezone

from app.extensions import db
from app.feats.base import InvariantViolation
from app.models import (
    Admin, IdentityProfile, ClassEconomy, ClassMembership, Transaction, StudentBlock,
    TapEvent, HallPassLog, RedemptionAuditLog, StudentItem, AnalyticsEvent,
    AnalyticsSnapshot, Issue, IssueResolutionAction, InsuranceClaim,
    InsuranceEnrollment, RentPayment, Announcement, StoreItemBlock, StoreItem,
    Seat, Student, StudentTeacher, PayrollSettings, RentSettings,
    IssueCategory, InsurancePolicy, InsurancePolicyBlock
)
from app.utils.deletion import collapse_universe
from tests.helpers.class_scope import create_class_scope

def test_collapse_universe_cascades_and_cleans_up(client):
    admin = make_admin("collapse_admin", "secret")
    db.session.add(admin)
    db.session.flush()

    profile_a = IdentityProfile(profile_type="student", first_name="Collapse", last_name="S")
    db.session.add(profile_a)
    db.session.flush()
    student = Student(identity_profile=profile_a, block="A", salt=b"salt")
    db.session.add(student)
    db.session.flush()
    
    profile_b = IdentityProfile(profile_type="student", first_name="Survive", last_name="B")
    db.session.add(profile_b)
    db.session.flush()
    student_b = Student(identity_profile=profile_b, block="A", salt=b"salt")
    db.session.add(student_b)
    db.session.flush()

    join_code = "COLL01"
    
    economy = create_class_scope(
        teacher=admin,
        join_code=join_code,
        student=student,
        create_claimed_teacher_block=True,
        teacher_block_claimed=True,
    )
    db.session.add(ClassMembership(join_code=join_code, student_id=student_b.id, role="student"))
    db.session.flush()
    # Link student's own identity profile to the seat created by create_class_scope so
    # collapse_universe can find the student via the Seat → IdentityProfile → Student chain.
    student_seat_a = Seat.query.filter_by(join_code=join_code, role="student").first()
    if student_seat_a:
        profile_a.seat_id = student_seat_a.id
    membership = ClassMembership.query.filter_by(join_code=join_code, admin_id=admin.id, role="admin").first()
    
    # Student B has another class
    join_code_survive = "SURV01"
    create_class_scope(
        teacher=admin,
        join_code=join_code_survive,
        create_teacher_membership=False,
        create_student_membership=False,
    )
    db.session.add(ClassMembership(join_code=join_code_survive, student_id=student_b.id, role="student"))
    
    # Bridge row
    db.session.add(StudentTeacher(student_id=student.id, teacher_id=admin.id))
    db.session.add(StudentTeacher(student_id=student_b.id, teacher_id=admin.id))

    # Settings (v2: scoped by class_id, not teacher_id)
    db.session.add(PayrollSettings(class_id=economy.class_id, block="A"))
    db.session.add(RentSettings(class_id=economy.class_id, block="A"))

    # Transaction (v2: seat_id replaces student_id/teacher_id)
    from uuid import uuid4
    from decimal import Decimal
    from app.models import TransactionStatus
    student_seat = Seat.query.filter_by(join_code=join_code, role="student").first()
    assert student_seat is not None, "Student seat must exist from create_class_scope"
    db.session.add(Transaction(
        seat_id=student_seat.id,
        class_id=economy.class_id,
        join_code=join_code,
        amount=Decimal("10.00"),
        amount_cents=1000,
        account_type="checking",
        type="deposit",
        description="Test deposit",
        correlation_id=f"bypass_test_{uuid4().hex}",
        status=TransactionStatus.POSTED,
        is_void=False,
    ))

    # Store Item and Block (v2: user_id replaces teacher_id)
    teacher_user = db.session.query(__import__('app.models', fromlist=['User']).User).filter_by(
        username_lookup_hash=admin.username_lookup_hash
    ).first()
    store_item = StoreItem(user_id=teacher_user.id if teacher_user else 1, join_code=join_code, name="Item", price=10, item_type='immediate')
    db.session.add(store_item)
    db.session.flush()

    db.session.add(StoreItemBlock(store_item_id=store_item.id, block="A"))

    # Issue (v2: user_id replaces teacher_id)
    issue_cat = IssueCategory(name="Issue", category_type="transaction", is_active=True)
    db.session.add(issue_cat)
    db.session.flush()

    issue = Issue(
        student_id=student.id,
        actor_public_id="ref",
        class_label="A",
        user_id=teacher_user.id if teacher_user else 1,
        class_id=economy.class_id,
        join_code=join_code,
        category_id=issue_cat.id,
        issue_type="transaction",
        student_explanation="Test explanation",
        student_first_name="Collapse",
        student_last_initial="S",
    )
    db.session.add(issue)
    
    db.session.commit()

    # Pre-collapse assertions
    assert ClassEconomy.query.filter_by(join_code=join_code).first() is not None
    assert db.session.query(Transaction).filter_by(join_code=join_code).count() == 1
    assert db.session.query(StoreItemBlock).filter_by(store_item_id=store_item.id).count() == 1
    assert db.session.query(StoreItem).filter_by(id=store_item.id).count() == 1
    assert db.session.get(Student, student.id) is not None
    assert db.session.get(Student, student_b.id) is not None

    store_item_id_val = store_item.id
    student_id_val = student.id
    student_b_id_val = student_b.id
    admin_id_val = admin.id

    # Do the collapse
    success = collapse_universe(economy.class_id, reason="Test collapse", actor_membership_id=membership.id)
    assert success is True

    # Post-collapse assertions
    assert ClassEconomy.query.filter_by(join_code=join_code).first() is None
    assert db.session.query(ClassMembership).filter_by(join_code=join_code).count() == 0
    assert db.session.query(Transaction).filter_by(join_code=join_code).count() == 0
    assert db.session.query(Seat).filter_by(join_code=join_code).count() == 0
    assert db.session.query(Issue).filter_by(join_code=join_code).count() == 0
    
    # Store settings cleanup
    assert db.session.query(StoreItemBlock).filter_by(store_item_id=store_item_id_val).count() == 0
    # Store item should be deleted because it has no remaining visibility blocks
    assert db.session.query(StoreItem).filter_by(id=store_item_id_val).count() == 0
    
    # Settings Cleanup
    assert db.session.query(PayrollSettings).filter_by(class_id=economy.class_id, block="A").count() == 0
    assert db.session.query(RentSettings).filter_by(class_id=economy.class_id, block="A").count() == 0

    db.session.expire_all()
    # Student A should be entirely deleted because they have no other classes
    assert db.session.get(Student, student_id_val) is None
    
    # Student B should survive because they have another class
    assert db.session.get(Student, student_b_id_val) is not None


def test_admin_join_code_delete_route(client):
    from tests.helpers.admin_context import login_admin
    admin = make_admin("route_admin", "secret")
    db.session.add(admin)
    db.session.flush()

    join_code = "ROUT01"
    class_row = create_class_scope(teacher=admin, join_code=join_code)
    db.session.commit()

    login_admin(client, admin.id, join_code, class_id=class_row.class_id)

    # Valid deletion
    response = client.post("/admin/join-code/delete", json={
        "join_code": join_code,
        "confirm_join_code": join_code
    })
    
    assert response.status_code == 200
    assert ClassEconomy.query.filter_by(join_code=join_code).first() is None


def test_collapse_universe_raises_on_null_class_id_scope_rows(client):
    admin = make_admin("collapse_invalid_admin", "secret")
    db.session.add(admin)
    db.session.flush()

    profile = IdentityProfile(profile_type="student", first_name="Invalid", last_name="S")
    db.session.add(profile)
    db.session.flush()
    student = Student(identity_profile=profile, block="A", salt=b"salt")
    db.session.add(student)
    db.session.flush()

    economy = create_class_scope(
        teacher=admin,
        join_code="INV001",
        student=student,
        create_claimed_teacher_block=True,
        teacher_block_claimed=True,
    )
    membership = ClassMembership.query.filter_by(
        join_code="INV001",
        admin_id=admin.id,
        role="admin",
    ).first()
    db.session.add(
        StudentBlock(
            student_id=student.id,
            period="A",
            join_code="INV001",
            class_id=None,
            tap_enabled=True,
        )
    )
    db.session.commit()

    with pytest.raises(InvariantViolation):
        collapse_universe(economy.class_id, reason="Invariant test", actor_membership_id=membership.id)
