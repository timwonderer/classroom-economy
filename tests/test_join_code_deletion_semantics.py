from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import pyotp
from datetime import datetime, timezone

from app import db
from app.models import Seat, User, UserRole, Transaction, StoreItem, StoreItemBlock, StudentItem, IssueCategory, Issue
from app.hash_utils import get_random_salt, hash_hmac
from tests.helpers.class_scope import create_class_scope
from tests.helpers.class_scope import make_student_identity


def _create_admin(username: str) -> tuple[str]:
    secret = pyotp.random_base32()
    admin = make_admin(username, secret)
    db.session.commit()
    return admin, secret


def _create_student(teacher: User, first_name: str, block: str, join_code: str):
    seat = make_student_identity(first_name=first_name, last_name=first_name[0].upper(), block=block, join_code=join_code)
    db.session.commit()
    return seat


def _login_admin(client, admin: User, secret: str):
    response = client.post(
        "/admin/login",
        data={"username": "teacher1", "totp_code": pyotp.TOTP(secret).now()},
        follow_redirects=True,
    )
    with client.session_transaction() as sess:
        sess.setdefault("is_admin", True)
        sess.setdefault("admin_id", admin.id)
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()
    return response


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
    db.session.add(tx)
    db.session.commit()
    tx_id = tx.id
    student_id = student.id

    _login_admin(client, teacher, secret)
    response = client.post(
        "/admin/student/archive",
        data={"student_id": student_id, "confirmation": "DELETE"},
        follow_redirects=True,
    )
    assert response.status_code == 200

    assert db.session.query(Seat).filter_by(user_id=student_id).first() is None
    assert db.session.get(Transaction, tx_id) is None


def test_deactivate_item_does_not_delete_transactions(client):
    teacher, secret = _create_admin("teacher-item-ledger")
    student = _create_student(teacher, "Bob", "A", "ITEMJC1")

    item = StoreItem(
        user_id=teacher.id,
        name="Sticker",
        price=10,
        item_type="delayed",
        is_active=True,
    )
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
    db.session.add(tx)
    db.session.commit()
    tx_id = tx.id

    _login_admin(client, teacher, secret)
    response = client.post(f"/admin/item/deactivate/{item.id}", follow_redirects=True)
    assert response.status_code == 200

    db.session.refresh(item)
    assert item.is_active is False
    assert db.session.get(Transaction, tx_id) is not None


def test_delete_join_code_removes_only_scoped_records(client):
    teacher, secret = _create_admin("teacher-join-delete")
    student_a = _create_student(teacher, "Cara", "A", "JCDEL1")
    student_b = _create_student(teacher, "Dylan", "B", "JCKEEP2")

    tx_a = Transaction(seat_id=student_a.id, user_id=student_a.user_id, join_code="JCDEL1", amount=20, account_type="checking")
    tx_b = Transaction(seat_id=student_b.id, user_id=student_b.user_id, join_code="JCKEEP2", amount=30, account_type="checking")
    db.session.add_all([tx_a, tx_b])
    db.session.flush()

    category = IssueCategory(
        name=f"JoinDeleteCategory-{teacher.id}",
        category_type="transaction",
        is_active=True,
    )
    db.session.add(category)
    db.session.flush()

    issue = Issue(
        user_id=student_a.user_id,
        actor_public_id="seat-public-join-delete",
        teacher_id=teacher.id,
        join_code="JCDEL1",
        category_id=category.id,
        issue_type="transaction",
        student_explanation="Bad transaction",
        related_transaction_id=tx_a.id,
    )
    db.session.add(issue)

    item_a = StoreItem(
        user_id=teacher.id,
        name="Class A Item",
        price=5,
        item_type="delayed",
        is_active=True,
    )
    item_b = StoreItem(
        user_id=teacher.id,
        name="Class B Item",
        price=5,
        item_type="delayed",
        is_active=True,
    )
    db.session.add_all([item_a, item_b])
    db.session.flush()
    db.session.add_all([
        StoreItemBlock(store_item_id=item_a.id, block="A"),
        StoreItemBlock(store_item_id=item_b.id, block="B"),
    ])
    db.session.flush()

    purchase = StudentItem(correlation_id='corr_test', user_id=student_a.user_id, store_item_id=item_a.id, join_code="JCDEL1", status="purchased")
    db.session.add(purchase)
    db.session.commit()

    tx_a_id = tx_a.id
    tx_b_id = tx_b.id
    issue_id = issue.id
    student_a_id = student_a.id
    student_b_id = student_b.id
    item_a_id = item_a.id
    item_b_id = item_b.id

    _login_admin(client, teacher, secret)
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

    assert db.session.get(Transaction, tx_a_id) is None
    assert db.session.get(Transaction, tx_b_id) is not None
    assert db.session.get(Issue, issue_id) is None

    # Student with only the deleted join_code is removed; student in other class remains.
    assert db.session.query(Seat).filter_by(user_id=student_a_id).first() is None
    assert db.session.query(Seat).filter_by(user_id=student_b_id).first() is not None

    assert db.session.get(StoreItem, item_a_id) is None
    assert db.session.get(StoreItem, item_b_id) is not None
