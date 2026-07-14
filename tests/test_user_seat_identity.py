from tests.helpers.v2_fixtures import seed_canonical_admin
import pytest
from sqlalchemy.exc import IntegrityError

from app import db
from app.feats.base import FEATContext
from app.hash_utils import hash_username_lookup
from app.models import ClassEconomy, Seat, User
from tests.helpers.class_scope import create_class_scope, make_student_identity


def _create_class(teacher_id: int, join_code: str) -> ClassEconomy:
    economy = ClassEconomy(join_code=join_code, user_id=teacher_id, created_by_user_id=teacher_id)
    db.session.add(economy)
    db.session.flush()
    return economy


def test_user_can_hold_seats_in_multiple_classes(client):
    with FEATContext("FEAT-IDEN-001", idempotency_key="user-seat-identity:multi-class"):
        user = User(username_hash="hash_a", username_lookup_hash=hash_username_lookup("user_a"))
        teacher = seed_canonical_admin("seat_teacher_a").user
        db.session.add(user)
        db.session.flush()
        class_a = create_class_scope(teacher_user=teacher)
        class_b = create_class_scope(teacher_user=teacher)

        db.session.add_all([
            Seat(user_id=user.id, class_id=class_a.class_id),
            Seat(user_id=user.id, class_id=class_b.class_id),
        ])
        db.session.flush()

        seats = Seat.query.filter_by(user_id=user.id).order_by(Seat.class_id.asc()).all()
        assert len(seats) == 2
        class_ids = {s.class_id for s in seats}
        assert class_ids == {class_a.class_id, class_b.class_id}


def test_user_cannot_have_duplicate_seat_for_same_class(client):
    with FEATContext("FEAT-IDEN-001", idempotency_key="user-seat-identity:duplicate"):
        user = User(username_hash="hash_b", username_lookup_hash=hash_username_lookup("user_b"))
        teacher = seed_canonical_admin("seat_teacher_b").user
        db.session.add(user)
        db.session.flush()
        class_x = create_class_scope(teacher_user=teacher)

        db.session.add(Seat(user_id=user.id, class_id=class_x.class_id))
        db.session.flush()

        db.session.add(Seat(user_id=user.id, class_id=class_x.class_id))
        with pytest.raises(IntegrityError):
            db.session.flush()
        db.session.rollback()


def test_different_users_can_share_same_class(client):
    with FEATContext("FEAT-IDEN-001", idempotency_key="user-seat-identity:shared"):
        user1 = User(username_hash="hash_c1", username_lookup_hash=hash_username_lookup("user_c1"))
        user2 = User(username_hash="hash_c2", username_lookup_hash=hash_username_lookup("user_c2"))
        teacher = seed_canonical_admin("seat_teacher_c").user
        db.session.add_all([user1, user2])
        db.session.flush()
        shared_class = create_class_scope(teacher_user=teacher)

        db.session.add_all([
            Seat(user_id=user1.id, class_id=shared_class.class_id),
            Seat(user_id=user2.id, class_id=shared_class.class_id),
        ])
        db.session.flush()

        shared = Seat.query.filter_by(class_id=shared_class.class_id).all()
        assert len(shared) == 3
        student_seats = Seat.query.filter_by(class_id=shared_class.class_id, role="student").all()
        assert len(student_seats) == 2
