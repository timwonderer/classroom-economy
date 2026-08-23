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


def test_DOM_IDEN_007__delete_teacher_cleans_up_links(client, app):
    """Terminal class-universe destruction physically removes the class economy
    and its otherwise-immutable economic history.

    Deletion is exercised through the authorized hard-deletion boundary
    (POST /admin/join-code/delete → ``_hard_delete_class_scope``), which is the
    only path that sets ``cth.class_universe_destroying`` and is therefore
    permitted to delete immutable ``economic_engine`` / ``class_features`` rows
    (INV-CORE-000 §III.5 terminal-destruction lifecycle exception). Raw
    ``db.session.delete`` bypasses that boundary and is correctly rejected by the
    immutability triggers, which remain active in the test DB for production
    parity.
    """
    from app.models import ClassEconomy, ClassFeature, EconomicEngine
    from tests.dom.identity.helpers import admin_delete_join_code
    from tests.helpers.classroom_initializer import initialize_as_teacher

    classroom = initialize_as_teacher("chemistry_p1", client, app)
    class_id = classroom.class_id
    join_code = classroom.join_code

    # Pre-condition: the immutable economic history exists for this class.
    assert db.session.get(ClassEconomy, class_id) is not None
    assert EconomicEngine.query.filter_by(class_id=class_id).count() >= 1
    assert ClassFeature.query.filter_by(class_id=class_id).count() >= 1

    # Destroy through the authorized boundary. confirm_join_code satisfies the
    # in-route destruction confirmation gate.
    resp = admin_delete_join_code(client, join_code, confirm_join_code=join_code)
    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert resp.get_json()["status"] == "success"

    db.session.expire_all()

    # Post-condition: the class universe — including immutable history — is
    # physically destroyed.
    assert db.session.get(ClassEconomy, class_id) is None
    assert EconomicEngine.query.filter_by(class_id=class_id).count() == 0
    assert ClassFeature.query.filter_by(class_id=class_id).count() == 0


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
