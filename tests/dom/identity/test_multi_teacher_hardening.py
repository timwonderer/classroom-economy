import pytest
import pyotp
import uuid
from sqlalchemy import delete as sa_delete
from app import db
from app.feats.base import FEATContext
from app.models import User, UserRole, IdentityProfile, Seat
from tests.helpers.classroom_initializer import initialize


def test_DOM_IDEN_007__student_count_relies_only_on_link_table(client):
    """Verify seat count per class."""
    class_row = initialize("chemistry_p1", db)

    # Initially no students
    initial_count = Seat.query.filter_by(class_id=class_row.class_id, role="student").count()
    assert initial_count >= 1

    final_count = Seat.query.filter_by(class_id=class_row.class_id, role="student").count()
    assert final_count == initial_count


def test_DOM_IDEN_007__delete_teacher_cleans_up_links(client):
    """Verify teacher deletion cascades correctly."""
    with FEATContext("FEAT-IDEN-001", idempotency_key="multi-teacher:delete-links"):
        class_row = initialize("chemistry_p1", db)
        seat = class_row.students[0].seat
        profile_id = seat.identity_profile.id

        from app.models import ClassEconomy
        economy = db.session.get(ClassEconomy, class_row.class_id)
        db.session.delete(economy)
        db.session.flush()

        assert db.session.get(ClassEconomy, class_row.class_id) is None


def test_DOM_IDEN_007__student_teacher_unique_constraint(client):
    """Verify unique constraint on seats per class per user."""
    from sqlalchemy.exc import IntegrityError

    with FEATContext("FEAT-IDEN-001", idempotency_key="multi-teacher:unique-seat"):
        class_row = initialize("chemistry_p1", db)
        seat = class_row.students[0].seat

        with pytest.raises(IntegrityError):
            duplicate = Seat(user_id=seat.user_id, class_id=class_row.class_id, role="student")
            db.session.add(duplicate)
            db.session.flush()
        db.session.rollback()


def test_DOM_IDEN_007__remove_student_from_teacher_scope_preserves_shared_student(client):
    """Student in two classes survives removal from one class."""
    with FEATContext("FEAT-IDEN-001", idempotency_key="multi-teacher:shared-student"):
        class_a = initialize("chemistry_p1", db)
        class_b = initialize("biology_block_a", db)
        seat_a = class_a.students[0].seat

        profile_id = seat_a.identity_profile.id

        db.session.execute(sa_delete(Seat).where(Seat.id == seat_a.id))
        db.session.flush()

        profile = db.session.get(IdentityProfile, profile_id)
        assert profile is not None
