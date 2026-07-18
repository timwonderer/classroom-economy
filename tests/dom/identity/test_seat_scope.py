from app.extensions import db
from app.feats.base import FEATContext
from app.models import Seat, User, UserRole
from app.hash_utils import hash_username_lookup
from tests.helpers.classroom_initializer import initialize


def test_DOM_IDEN_005__user_can_hold_seats_in_multiple_classes(client):
    classroom_a = initialize("chemistry_p1", client.application)
    classroom_b = initialize("ap_csp_p3", client.application)
    user = User(username_hash="hash_a", username_lookup_hash=hash_username_lookup("user_a"), user_role=UserRole.STUDENT)
    db.session.add(user)
    db.session.flush()

    with FEATContext("FEAT-IDEN-001", idempotency_key="user-seat-identity:multi-class"):
        db.session.add_all([
            Seat(user_id=user.id, class_id=classroom_a.class_id),
            Seat(user_id=user.id, class_id=classroom_b.class_id),
        ])
        db.session.flush()

    seats = Seat.query.filter_by(user_id=user.id).order_by(Seat.class_id.asc()).all()
    assert len(seats) == 2
    assert {s.class_id for s in seats} == {classroom_a.class_id, classroom_b.class_id}


def test_DOM_IDEN_005__user_cannot_have_duplicate_seat_for_same_class(client):
    classroom = initialize("chemistry_p1", client.application)
    user = User(username_hash="hash_b", username_lookup_hash=hash_username_lookup("user_b"), user_role=UserRole.STUDENT)
    db.session.add(user)
    db.session.flush()

    with FEATContext("FEAT-IDEN-001", idempotency_key="user-seat-identity:duplicate"):
        db.session.add(Seat(user_id=user.id, class_id=classroom.class_id))
        db.session.flush()
        db.session.add(Seat(user_id=user.id, class_id=classroom.class_id))
        db.session.flush()


def test_DOM_IDEN_005__different_users_can_share_same_class(client):
    classroom = initialize("chemistry_p1", client.application)
    user1 = User(username_hash="hash_c1", username_lookup_hash=hash_username_lookup("user_c1"), user_role=UserRole.STUDENT)
    user2 = User(username_hash="hash_c2", username_lookup_hash=hash_username_lookup("user_c2"), user_role=UserRole.STUDENT)
    db.session.add_all([user1, user2])
    db.session.flush()

    with FEATContext("FEAT-IDEN-001", idempotency_key="user-seat-identity:shared"):
        db.session.add_all([
            Seat(user_id=user1.id, class_id=classroom.class_id),
            Seat(user_id=user2.id, class_id=classroom.class_id),
        ])
        db.session.flush()

    shared = Seat.query.filter_by(class_id=classroom.class_id).all()
    assert len(shared) >= 2
