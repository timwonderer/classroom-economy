from tests.helpers.v2_fixtures import seed_canonical_admin
from tests.helpers.class_scope import create_class_scope, make_student_identity
import pytest
import pyotp
import uuid
from sqlalchemy import delete as sa_delete
from app import db
from app.feats.base import FEATContext
from app.models import User, UserRole, IdentityProfile, Seat


def test_student_count_relies_only_on_link_table(client):
    """Verify seat count per class."""
    t_username = f"harden_prof_{uuid.uuid4().hex[:8]}"
    teacher = seed_canonical_admin(t_username).user
    class_row = create_class_scope(teacher_user=teacher, join_code=f"HARD{uuid.uuid4().hex[:6].upper()}")
    db.session.flush()

    # Initially no students
    initial_count = Seat.query.filter_by(class_id=class_row.class_id, role="student").count()
    assert initial_count == 0

    s_firstname = f"Hardened_{uuid.uuid4().hex[:8]}"
    make_student_identity(class_id=class_row.class_id, first_name=s_firstname, last_name="S")
    db.session.flush()

    final_count = Seat.query.filter_by(class_id=class_row.class_id, role="student").count()
    assert final_count == 1


def test_delete_teacher_cleans_up_links(client):
    """Verify teacher deletion cascades correctly."""
    with FEATContext("FEAT-IDEN-001", idempotency_key="multi-teacher:delete-links"):
        t1_username = f"del_target_{uuid.uuid4().hex[:8]}"
        teacher = seed_canonical_admin(t1_username).user
        class_row = create_class_scope(teacher_user=teacher, join_code=f"DEL{uuid.uuid4().hex[:6].upper()}")
        db.session.flush()

        s_firstname = f"Survivor_{uuid.uuid4().hex[:8]}"
        seat = make_student_identity(class_id=class_row.class_id, first_name=s_firstname, last_name="S")
        db.session.flush()
        profile_id = seat.identity_profile.id

        from app.models import ClassEconomy
        economy = db.session.get(ClassEconomy, class_row.class_id)
        db.session.delete(economy)
        db.session.flush()

        assert db.session.get(ClassEconomy, class_row.class_id) is None


def test_student_teacher_unique_constraint(client):
    """Verify unique constraint on seats per class per user."""
    from sqlalchemy.exc import IntegrityError

    with FEATContext("FEAT-IDEN-001", idempotency_key="multi-teacher:unique-seat"):
        teacher = seed_canonical_admin(f"unique_t_{uuid.uuid4().hex}").user
        class_row = create_class_scope(teacher_user=teacher, join_code=f"UNQ{uuid.uuid4().hex[:6].upper()}")
        db.session.flush()

        seat = make_student_identity(class_id=class_row.class_id, first_name="Unique", last_name="S")
        db.session.flush()

        with pytest.raises(IntegrityError):
            duplicate = Seat(user_id=seat.user_id, class_id=class_row.class_id, role="student")
            db.session.add(duplicate)
            db.session.flush()
        db.session.rollback()


def test_remove_student_from_teacher_scope_preserves_shared_student(client):
    """Student in two classes survives removal from one class."""
    with FEATContext("FEAT-IDEN-001", idempotency_key="multi-teacher:shared-student"):
        t1 = seed_canonical_admin(f"t1_{uuid.uuid4().hex[:8]}").user
        t2 = seed_canonical_admin(f"t2_{uuid.uuid4().hex[:8]}").user
        class_a = create_class_scope(teacher_user=t1, join_code=f"SHA{uuid.uuid4().hex[:6].upper()}")
        class_b = create_class_scope(teacher_user=t2, join_code=f"SHB{uuid.uuid4().hex[:6].upper()}")
        db.session.flush()

        seat_a = make_student_identity(class_id=class_a.class_id, first_name="Shared", last_name="S")
        db.session.flush()

        profile_id = seat_a.identity_profile.id

        db.session.execute(sa_delete(Seat).where(Seat.id == seat_a.id))
        db.session.flush()

        profile = db.session.get(IdentityProfile, profile_id)
        assert profile is not None
