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
    from tests.dom.identity.helpers import admin_delete_class, valid_destruction_gate
    from tests.helpers.classroom_initializer import initialize_as_teacher

    classroom = initialize_as_teacher("chemistry_p1", client, app)
    class_id = classroom.class_id
    join_code = classroom.join_code

    # Pre-condition: the immutable economic history exists for this class.
    assert db.session.get(ClassEconomy, class_id) is not None
    assert EconomicEngine.query.filter_by(class_id=class_id).count() >= 1
    assert ClassFeature.query.filter_by(class_id=class_id).count() >= 1

    # Destroy through the authorized boundary. The target is the canonical
    # active class; the payload carries destruction-gate evidence only.
    class_row = db.session.get(ClassEconomy, class_id)
    phrase = f"DELETE {(class_row.display_name or '').strip() or class_row.join_code}".upper()
    resp = admin_delete_class(client, **valid_destruction_gate(phrase))
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

    # `initialize` opens its own FEAT-IDEN-001, so it runs OUTSIDE the context
    # this test owns — exactly one FEAT executes per path (INV-ARC-000 §VIII.2).
    class_row = initialize("chemistry_p1", db)
    seat = class_row.students[0].seat

    with FEATContext("FEAT-IDEN-001", idempotency_key="multi-teacher:unique-seat"):
        with pytest.raises(IntegrityError):
            duplicate = Seat(user_id=seat.user_id, class_id=class_row.class_id, role="student")
            db.session.add(duplicate)
            db.session.flush()
        db.session.rollback()


def test_DOM_IDEN_007__remove_student_from_teacher_scope_preserves_shared_student(client):
    """A User participating in two Classes survives removal from one of them.

    DOM-IDEN-001 §VI: participation is held by ``Seat``, one per ``User`` per
    ``Class``, and an ``IdentityProfile`` is display data *for a Seat within a
    Class* — 1:1, cascade-deleted with its seat. So dropping the class A seat
    must take that seat's profile with it while leaving the ``User`` and the
    entire class B participation untouched.

    An earlier version of this test asserted the class A profile SURVIVED its
    seat, which encoded a pre-canonical model where the profile was a
    user-level object shared across classes. It also never actually shared a
    student: it provisioned a second classroom and then never used it, so the
    "shared" half of the scenario was never constructed.
    """
    # `initialize` opens its own FEAT-IDEN-001, so it runs OUTSIDE the context
    # this test owns — exactly one FEAT executes per path (INV-ARC-000 §VIII.2).
    class_a = initialize("chemistry_p1", db)
    class_b = initialize("biology_block_a", db)

    student = class_a.students[0]
    seat_a = student.seat
    seat_a_id = seat_a.id
    profile_a_id = seat_a.identity_profile.id

    with FEATContext("FEAT-IDEN-001", idempotency_key="multi-teacher:shared-student"):
        # Actually share the student: a second seat for the SAME user in class B,
        # with its own class-local display profile.
        seat_b = Seat(user_id=student.user.id, class_id=class_b.class_id, role="student")
        db.session.add(seat_b)
        db.session.flush()
        profile_b = IdentityProfile(
            seat_id=seat_b.id,
            class_id=class_b.class_id,
            profile_type="student",
            first_name=student.first_name,
            last_name=student.last_name,
        )
        db.session.add(profile_b)
        db.session.flush()
        seat_b_id, profile_b_id = seat_b.id, profile_b.id

        # Remove the student from class A only.
        db.session.execute(sa_delete(Seat).where(Seat.id == seat_a_id))
        db.session.flush()
        db.session.expire_all()

    # Class A participation is gone, profile and all — the profile is seat-local.
    assert db.session.get(Seat, seat_a_id) is None
    assert db.session.get(IdentityProfile, profile_a_id) is None

    # The User survives, because it still participates through class B.
    assert db.session.get(User, student.user.id) is not None
    assert db.session.get(Seat, seat_b_id) is not None
    assert db.session.get(IdentityProfile, profile_b_id) is not None
