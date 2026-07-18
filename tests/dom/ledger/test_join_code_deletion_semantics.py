from app import db
from app.models import Seat, User, UserRole, Transaction, StoreItem, StoreItemVisibility, StorePurchase, IssueCategory, Issue, ClassFeature, ClassEconomy
from app.feats.base import FEATContext
from app.hash_utils import get_random_salt, hash_hmac
from app.services.store_service import set_item_visibility
from tests.helpers.ledger import create_ledger_pending_transaction, provision_ledger_classroom, provision_ledger_teacher


def _ensure_class_features(class_id: str, feature_names: list[str]):
    existing = {
        row.feature_name
        for row in ClassFeature.query.filter_by(class_id=class_id).all()
    }
    missing = [
        ClassFeature(class_id=class_id, feature_name=feature_name)
        for feature_name in feature_names
        if feature_name not in existing
    ]
    if missing:
        db.session.add_all(missing)


def test_DOM_LED_001__delete_student_removes_transactions(client, app):
    classroom = provision_ledger_teacher("chemistry_p1", client, app)
    teacher = classroom.teacher_user
    student = classroom.students[0].seat

    with FEATContext("FEAT-LED-001", idempotency_key="join_code_deletion:archive_tx"):
        tx = create_ledger_pending_transaction(
            seat_id=student.id,
            user_id=student.user_id,
            class_id=student.class_id,
            amount=50,
            account_type="checking",
            type="purchase",
            description="Seed ledger entry",
        )
    db.session.commit()
    tx_id = tx.id
    student_id = student.id

    response = client.post(
        "/admin/student/archive",
        data={"seat_id": student_id, "confirmation": "DELETE"},
        follow_redirects=True,
    )
    assert response.status_code == 200

    db.session.expire_all()
    archived_seat = db.session.get(Seat, student_id)
    assert archived_seat is not None
    assert archived_seat.user_id is None
    assert db.session.get(Transaction, tx_id) is None


def test_DOM_LED_001__deactivate_item_does_not_delete_transactions(client, app):
    classroom = provision_ledger_teacher("chemistry_p1", client, app)
    teacher = classroom.teacher_user
    student = classroom.students[0].seat
    with FEATContext("FEAT-STOR-001", idempotency_key="join_code_deletion:enable_store_item"):
        _ensure_class_features(student.class_id, ["store"])

    item = StoreItem(
        user_id=teacher.id,
        class_id=student.class_id,
        name="Sticker",
        price=10,
        item_type="delayed",
        is_active=True,
    )
    with FEATContext("FEAT-STOR-001", idempotency_key="join_code_deletion:item"):
        db.session.add(item)
        db.session.flush()
        set_item_visibility(item.id, [student.id])

    with FEATContext("FEAT-LED-001", idempotency_key="join_code_deletion:item_tx"):
        tx = create_ledger_pending_transaction(
            seat_id=student.id,
            user_id=student.user_id,
            class_id=student.class_id,
            amount=-10,
            account_type="checking",
            type="purchase",
            description="Purchase: Sticker",
        )
    db.session.commit()
    tx_id = tx.id

    response = client.post(
        f"/admin/item/deactivate/{item.id}",
        data={"block": "A"},
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)

    db.session.expire_all()
    db.session.refresh(item)
    assert item.is_active is False
    assert db.session.get(Transaction, tx_id) is not None


def test_DOM_LED_001__delete_class_removes_only_scoped_records(client, app):
    class_a = provision_ledger_teacher("chemistry_p1", client, app)
    class_b = provision_ledger_classroom("biology_block_a", app)
    teacher = class_a.teacher_user
    student_a = class_a.students[0].seat
    student_b = class_b.students[0].seat
    join_code_a = class_a.join_code
    join_code_b = class_b.join_code
    with FEATContext("FEAT-STOR-001", idempotency_key="join_code_deletion:enable_store_scope"):
        _ensure_class_features(student_a.class_id, ["store", "insurance", "payroll", "rent", "hall_pass"])

    with FEATContext("FEAT-LED-001", idempotency_key="join_code_deletion:seed_transactions"):
        tx_a = create_ledger_pending_transaction(
            seat_id=student_a.id,
            user_id=student_a.user_id,
            class_id=student_a.class_id,
            amount=20,
            account_type="checking",
            type="purchase",
            description="Class A transaction",
        )
        tx_b = create_ledger_pending_transaction(
            seat_id=student_b.id,
            user_id=student_b.user_id,
            class_id=student_b.class_id,
            amount=30,
            account_type="checking",
            type="purchase",
            description="Class B transaction",
        )

    category = IssueCategory(
        name=f"JoinDeleteCategory-{teacher.id}",
        category_type="transaction",
        is_active=True,
    )
    with FEATContext("FEAT-SUP-001", idempotency_key="join_code_deletion:category"):
        db.session.add(category)
        db.session.flush()

    class_public_id = ClassEconomy.query.filter_by(class_id=student_a.class_id).first().class_public_id
    issue = Issue(
        actor_public_id=student_a.public_id,
        class_public_id=class_public_id,
        category_id=category.id,
        issue_type="transaction",
        student_explanation="Bad transaction",
        related_transaction_id=tx_a.id,
    )
    with FEATContext("FEAT-SUP-001", idempotency_key="join_code_deletion:issue"):
        db.session.add(issue)
        db.session.flush()

    item_a = StoreItem(
        user_id=teacher.id,
        class_id=student_a.class_id,
        name="Class A Item",
        price=5,
        item_type="delayed",
        is_active=True,
    )
    item_b = StoreItem(
        user_id=teacher.id,
        class_id=student_b.class_id,
        name="Class B Item",
        price=5,
        item_type="delayed",
        is_active=True,
    )
    with FEATContext("FEAT-STOR-001", idempotency_key="join_code_deletion:items"):
        db.session.add_all([item_a, item_b])
        db.session.flush()
        set_item_visibility(item_a.id, [student_a.id])
        set_item_visibility(item_b.id, [student_b.id])
        db.session.flush()

        purchase = StorePurchase(
            seat_id=student_a.id,
            class_id=student_a.class_id,
            store_item_id=item_a.id,
            quantity=1,
            price_at_purchase=item_a.price,
            total_price=item_a.price,
            status="purchased",
        )
        db.session.add(purchase)
    db.session.commit()

    tx_a_id = tx_a.id
    tx_b_id = tx_b.id
    issue_id = issue.id
    student_a_id = student_a.id
    student_b_id = student_b.id
    item_a_id = item_a.id
    item_b_id = item_b.id

    response = client.post(
        "/admin/join-code/delete",
        json={
            "join_code": join_code_a,
            "gate_phrase": f"DELETE JOIN CODE {join_code_a}",
            "gate_countdown_seconds": 30,
            "gate_hold_seconds": 10,
        },
        content_type="application/json",
    )
    assert response.status_code == 200

    db.session.expire_all()
    assert db.session.get(Transaction, tx_a_id) is None
    assert db.session.get(Transaction, tx_b_id) is not None
    assert db.session.get(Issue, issue_id) is None

    # Class destruction hard-deletes seats in the scoped class; other classes remain untouched.
    student_a_row = db.session.get(Seat, student_a_id)
    student_b_row = db.session.get(Seat, student_b_id)
    assert student_a_row is None
    assert student_b_row is not None

    assert db.session.get(StoreItem, item_a_id) is None
    assert db.session.get(StoreItem, item_b_id) is not None
