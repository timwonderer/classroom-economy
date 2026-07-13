from tests.helpers.v2_fixtures import seed_canonical_admin, make_sysadmin

from app import db
from app.models import Seat, User, UserRole, Transaction, StoreItem, StoreItemBlock, StudentItem, IssueCategory, Issue, ClassFeature
from app.feats.base import FEATContext
from app.hash_utils import get_random_salt, hash_hmac
from tests.helpers.admin_context import login_teacher
from tests.helpers.class_scope import create_class_scope
from tests.helpers.class_scope import make_student_identity


def _create_admin(username: str) -> tuple[str]:
    admin = seed_canonical_admin(username).user
    db.session.commit()
    return admin, "unused"


def _create_student(teacher: User, first_name: str, block: str, join_code: str):
    class_row = create_class_scope(teacher_user=teacher, join_code=join_code, section=block)
    seat = make_student_identity(
        class_id=class_row.class_id,
        first_name=first_name,
        last_name=first_name[0].upper(),
        claimed=True,
    )
    db.session.commit()
    return seat


def _login_admin(client, admin: User, secret: str, *, class_id: str | None = None, seat_id: int | None = None):
    if class_id is not None:
        login_teacher(client, admin, class_id=class_id)
    return None


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


def test_delete_student_removes_transactions(client):
    teacher, secret = _create_admin("teacher-archive-ledger")
    student = _create_student(teacher, "Alice", "A", "ARCHIVE1")

    tx = Transaction(
        seat_id=student.id,
        user_id=student.user_id,
        join_code="ARCHIVE1",
        amount=50,
        account_type="checking",
        description="Seed ledger entry",
    )
    with FEATContext("FEAT-LED-001", idempotency_key="join_code_deletion:archive_tx"):
        db.session.add(tx)
        db.session.flush()
    db.session.commit()
    tx_id = tx.id
    student_id = student.id

    _login_admin(client, teacher, secret, class_id=student.class_id)
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


def test_deactivate_item_does_not_delete_transactions(client):
    teacher, secret = _create_admin("teacher-item-ledger")
    student = _create_student(teacher, "Bob", "A", "ITEMJC1")
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
        db.session.add(StoreItemBlock(store_item_id=item.id, block="A"))

    tx = Transaction(
        seat_id=student.id,
        user_id=student.user_id,
        join_code="ITEMJC1",
        amount=-10,
        account_type="checking",
        type="purchase",
        description="Purchase: Sticker",
    )
    with FEATContext("FEAT-LED-001", idempotency_key="join_code_deletion:item_tx"):
        db.session.add(tx)
        db.session.flush()
    db.session.commit()
    tx_id = tx.id

    _login_admin(client, teacher, secret, class_id=student.class_id)
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


def test_delete_class_removes_only_scoped_records(client):
    teacher, secret = _create_admin("teacher-join-delete")
    student_a = _create_student(teacher, "Cara", "A", "JCDEL1")
    student_b = _create_student(teacher, "Dylan", "B", "JCKEEP2")
    with FEATContext("FEAT-STOR-001", idempotency_key="join_code_deletion:enable_store_scope"):
        _ensure_class_features(student_a.class_id, ["store", "insurance", "payroll", "rent", "hall_pass"])

    with FEATContext("FEAT-LED-001", idempotency_key="join_code_deletion:seed_transactions"):
        tx_a = Transaction(seat_id=student_a.id, user_id=student_a.user_id, join_code="JCDEL1", amount=20, account_type="checking")
        tx_b = Transaction(seat_id=student_b.id, user_id=student_b.user_id, join_code="JCKEEP2", amount=30, account_type="checking")
        db.session.add_all([tx_a, tx_b])
        db.session.flush()

    category = IssueCategory(
        name=f"JoinDeleteCategory-{teacher.id}",
        category_type="transaction",
        is_active=True,
    )
    with FEATContext("FEAT-SUP-001", idempotency_key="join_code_deletion:category"):
        db.session.add(category)
        db.session.flush()

    issue = Issue(
        user_id=student_a.user_id,
        actor_public_id="seat-public-join-delete",
        class_id=student_a.class_id,
        seat_id=student_a.id,
        join_code="JCDEL1",
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
        db.session.add_all([
            StoreItemBlock(store_item_id=item_a.id, block="A"),
            StoreItemBlock(store_item_id=item_b.id, block="B"),
        ])
        db.session.flush()

        purchase = StudentItem(correlation_id='corr_test', seat_id=student_a.id, store_item_id=item_a.id, join_code="JCDEL1", status="purchased")
        db.session.add(purchase)
    db.session.commit()

    tx_a_id = tx_a.id
    tx_b_id = tx_b.id
    issue_id = issue.id
    student_a_id = student_a.id
    student_b_id = student_b.id
    item_a_id = item_a.id
    item_b_id = item_b.id

    _login_admin(client, teacher, secret, class_id=student_a.class_id)
    response = client.post(
        "/admin/join-code/delete",
        json={
            "join_code": "JCDEL1",
            "gate_phrase": "DELETE JOIN CODE JCDEL1",
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
