from tests.helpers.v2_fixtures import make_admin
import pytest
from sqlalchemy.exc import IntegrityError

from app import db
from app.hash_utils import hash_username_lookup
from app.models import ClassEconomy, Seat, User


def _create_class(teacher_id: int, join_code: str) -> ClassEconomy:
    economy = ClassEconomy(join_code=join_code, user_id=teacher_id, created_by_user_id=teacher_id)
    db.session.add(economy)
    db.session.flush()
    return economy


def test_user_can_hold_seats_in_multiple_classes(client):
    user = User(username_hash="hash_a", username_lookup_hash=hash_username_lookup("user_a"))
    teacher = make_admin("seat_teacher_a")
    db.session.add(user)
    db.session.flush()
    class_a = _create_class(teacher.id, "JOIN_A")
    class_b = _create_class(teacher.id, "JOIN_B")

    db.session.add(Seat(user_id=user.id, class_id=class_a.class_id))
    db.session.add(Seat(user_id=user.id, class_id=class_b.class_id))
    db.session.commit()

    seats = Seat.query.filter_by(user_id=user.id).order_by(Seat.class_id.asc()).all()
    assert len(seats) == 2
    class_ids = {s.class_id for s in seats}
    assert class_ids == {class_a.class_id, class_b.class_id}


def test_user_cannot_have_duplicate_seat_for_same_class(client):
    user = User(username_hash="hash_b", username_lookup_hash=hash_username_lookup("user_b"))
    teacher = make_admin("seat_teacher_b")
    db.session.add(user)
    db.session.flush()
    class_x = _create_class(teacher.id, "JOIN_X")

    db.session.add(Seat(user_id=user.id, class_id=class_x.class_id))
    db.session.commit()

    db.session.add(Seat(user_id=user.id, class_id=class_x.class_id))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_different_users_can_share_same_class(client):
    user1 = User(username_hash="hash_c1", username_lookup_hash=hash_username_lookup("user_c1"))
    user2 = User(username_hash="hash_c2", username_lookup_hash=hash_username_lookup("user_c2"))
    teacher = make_admin("seat_teacher_c")
    db.session.add_all([user1, user2])
    db.session.flush()
    shared_class = _create_class(teacher.id, "JOIN_SHARED")

    db.session.add(Seat(user_id=user1.id, class_id=shared_class.class_id))
    db.session.add(Seat(user_id=user2.id, class_id=shared_class.class_id))
    db.session.commit()

    shared = Seat.query.filter_by(class_id=shared_class.class_id).all()
    assert len(shared) == 2
