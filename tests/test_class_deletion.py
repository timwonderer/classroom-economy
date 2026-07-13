from tests.helpers.v2_fixtures import seed_canonical_admin, make_sysadmin, seed_purchase
from tests.helpers.class_scope import make_student_identity
import pytest
from datetime import datetime, timezone

from app.extensions import db
from app.feats.base import InvariantViolation
from app.models import (
    User,
    UserRole,
    ClassEconomy, Transaction,
    TapEvent, HallPassLog, RedemptionAuditLog, StudentItem, AnalyticsEvent,
    AnalyticsSnapshot, Issue, IssueResolutionAction, InsuranceClaim,
    InsuranceEnrollment, RentPayment, Announcement, StoreItemBlock, StoreItem,
    Seat, PayrollSettings, RentSettings,
    IssueCategory, InsurancePolicy, InsurancePolicyBlock
)
from app.utils.deletion import collapse_universe
from tests.helpers.class_scope import create_class_scope

def test_collapse_universe_cascades_and_cleans_up(client):
    admin = seed_canonical_admin("collapse_admin", "secret").user
    db.session.flush()

    join_code = "COLL01"
    economy = create_class_scope(teacher_user=admin, join_code=join_code)
    db.session.flush()

    student = make_student_identity(class_id=economy.class_id, first_name="Collapse", last_name="S")
    db.session.flush()

    # Student B has another class - create separately
    join_code_survive = "SURV01"
    economy_b = create_class_scope(teacher_user=admin, join_code=join_code_survive)
    db.session.flush()
    student_b = make_student_identity(class_id=economy_b.class_id, first_name="Survive", last_name="B")
    db.session.flush()

    student_user = db.session.get(User, student.user_id)
    student_b_user = db.session.get(User, student_b.user_id)
    assert student_user is not None
    assert student_b_user is not None

    # Settings
    db.session.add(PayrollSettings(block="A", class_id=economy.class_id))
    db.session.add(RentSettings(class_id=economy.class_id))

    # Transaction
    seed_purchase(
        seat_id=Seat.query.filter_by(class_id=economy.class_id, user_id=student_user.id).first().id,
        class_id=economy.class_id,
        user_id=student_user.id,
        amount="10.00",
        description="Test deposit",
        transaction_type="deposit",
    )

    # Store Item and Block
    store_item = StoreItem(user_id=admin.id, join_code=join_code, name="Item", price=10, item_type='immediate')
    db.session.add(store_item)
    db.session.flush()

    db.session.add(StoreItemBlock(store_item_id=store_item.id, block="A"))

    # Issue
    issue_cat = IssueCategory(name="Issue", category_type="transaction", is_active=True)
    db.session.add(issue_cat)
    db.session.flush()

    issue = Issue(
        user_id=admin.id,
        student_first_name="Collapse",
        student_last_initial="S",
        actor_public_id="ref",
        class_label="A",
        class_id=economy.class_id,
        join_code=join_code,
        category_id=issue_cat.id,
        issue_type="transaction",
        student_explanation="Test explanation"
    )
    db.session.add(issue)

    db.session.commit()

    # Pre-collapse assertions
    assert ClassEconomy.query.filter_by(class_id=economy.class_id).first() is not None
    assert db.session.query(Transaction).filter_by(class_id=economy.class_id).count() == 1
    assert db.session.query(StoreItemBlock).filter_by(store_item_id=store_item.id).count() == 1
    assert db.session.query(StoreItem).filter_by(id=store_item.id).count() == 1
    assert db.session.query(Seat).filter_by(user_id=student_user.id).first() is not None
    assert db.session.query(Seat).filter_by(user_id=student_b_user.id).first() is not None

    store_item_id_val = store_item.id
    student_user_id_val = student_user.id
    student_b_user_id_val = student_b_user.id
    admin_id_val = admin.id

    # Do the collapse
    success = collapse_universe(economy.class_id, reason="Test collapse", actor_membership_id=admin.id)
    assert success is True

    # Post-collapse assertions
    assert ClassEconomy.query.filter_by(class_id=economy.class_id).first() is None
    assert Seat.query.filter_by(class_id=economy.class_id).count() == 0
    assert db.session.query(Transaction).filter_by(class_id=economy.class_id).count() == 0
    assert db.session.query(Seat).filter_by(class_id=economy.class_id).count() == 0
    assert db.session.query(Issue).filter_by(class_id=economy.class_id).count() == 0

    # Store settings cleanup
    assert db.session.query(StoreItemBlock).filter_by(store_item_id=store_item_id_val).count() == 0
    # Store item should be deleted because it has no remaining visibility blocks
    assert db.session.query(StoreItem).filter_by(id=store_item_id_val).count() == 0

    # Settings Cleanup
    assert db.session.query(PayrollSettings).filter_by(class_id=economy.class_id).count() == 0
    assert db.session.query(RentSettings).filter_by(class_id=economy.class_id).count() == 0

    db.session.expire_all()
    # Student A should be entirely deleted because they have no other classes
    assert db.session.query(Seat).filter_by(user_id=student_user_id_val).first() is None

    # Student B should survive because they have another class
    assert db.session.query(Seat).filter_by(user_id=student_b_user_id_val).first() is not None


def test_admin_class_delete_route(client):
    admin = seed_canonical_admin("route_admin", "secret").user
    db.session.flush()

    join_code = "ROUT01"
    create_class_scope(
        teacher_user=admin, join_code=join_code)
    db.session.commit()

    with client.session_transaction() as sess:
        sess["user_id"] = admin.id
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()

    # Valid deletion
    response = client.post("/admin/join-code/delete", json={
        "join_code": join_code,
        "confirm_join_code": join_code
    })

    assert response.status_code == 200
    assert ClassEconomy.query.filter_by(class_id=economy.class_id).first() is None


def test_collapse_universe_raises_on_null_class_id_scope_rows(client):
    admin = seed_canonical_admin("collapse_invalid_admin", "secret").user
    db.session.flush()

    economy = create_class_scope(teacher_user=admin, join_code="INV001")
    db.session.flush()

    student = make_student_identity(class_id=economy.class_id, first_name="Invalid", last_name="S")
    db.session.flush()

    membership = Seat.query.filter_by(class_id=economy.class_id, role="teacher").first()
    db.session.add(
        TapEvent(
            seat_id=Seat.query.filter_by(user_id=student.user_id, class_id=economy.class_id).first().id,
            period="A",
            join_code="INV001",
            class_id=None,
            status="active",
        )
    )
    db.session.commit()

    success = collapse_universe(
        economy.class_id,
        reason="Invariant test",
        actor_membership_id=membership.id if membership else admin.id,
    )
    assert success is True
