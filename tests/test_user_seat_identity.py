from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import pytest
from sqlalchemy.exc import IntegrityError

from app import db
from app.hash_utils import hash_username_lookup
from app.models import Admin, ClassEconomy, Seat, User


def _create_class(teacher_id: int, join_code: str) -> ClassEconomy:
    economy = ClassEconomy(join_code=join_code, user_id=teacher_id, created_by_admin_id=teacher_id)
    db.session.add(economy)
    db.session.flush()
    return economy


def test_user_can_hold_multiple_join_code_seats(client):
    user = User(username_hash=hash_username_lookup("user_a"), password_hash="hash_a")
    teacher = make_admin("seat_teacher_a", "secret_a")
    db.session.add_all([user, teacher])
    db.session.flush()
    class_a = _create_class(teacher.id, "JOIN_A")
    class_b = _create_class(teacher.id, "JOIN_B")

    db.session.add(Seat(user_id=user.id, class_id=class_a.class_id, join_code="JOIN_A", block="A"))
    db.session.add(Seat(user_id=user.id, class_id=class_b.class_id, join_code="JOIN_B", block="B"))
    db.session.commit()

    seats = Seat.query.filter_by(user_id=user.id).order_by(Seat.join_code.asc()).all()
    assert [s.join_code for s in seats] == ["JOIN_A", "JOIN_B"]


def test_user_cannot_have_duplicate_seat_for_same_class(client):
    user = User(username_hash=hash_username_lookup("user_b"), password_hash="hash_b")
    teacher = make_admin("seat_teacher_b", "secret_b")
    db.session.add_all([user, teacher])
    db.session.flush()
    class_x = _create_class(teacher.id, "JOIN_X")

    db.session.add(Seat(user_id=user.id, class_id=class_x.class_id, join_code="JOIN_X", block="X"))
    db.session.commit()

    db.session.add(Seat(user_id=user.id, class_id=class_x.class_id, join_code="JOIN_X", block="X"))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_different_users_can_share_same_join_code(client):
    user1 = User(username_hash=hash_username_lookup("user_c1"), password_hash="hash_c1")
    user2 = User(username_hash=hash_username_lookup("user_c2"), password_hash="hash_c2")
    teacher = make_admin("seat_teacher_c", "secret_c")
    db.session.add_all([user1, user2, teacher])
    db.session.flush()
    shared_class = _create_class(teacher.id, "JOIN_SHARED")

    db.session.add(Seat(user_id=user1.id, class_id=shared_class.class_id, join_code="JOIN_SHARED", block="A"))
    db.session.add(Seat(user_id=user2.id, class_id=shared_class.class_id, join_code="JOIN_SHARED", block="A"))
    db.session.commit()

    shared = Seat.query.filter_by(join_code="JOIN_SHARED").all()
    assert len(shared) == 2
