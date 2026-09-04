"""B3 — a ``users`` row must not outlive its last seat.

A ``User`` is the auth principal *behind* a seat; it has no standalone
existence (DOM-IDEN-001 §VI). When the last seat referencing it is removed the
principal must be removed too — INV-CORE-000 §III.5, and, because ``users``
carries credential and recovery material, PII retention.

Before this fix ``hard_delete_student_if_orphaned`` deleted seats and left the
parent ``User``; ``_delete_orphan_students`` (the class-teardown path) computed
a tautologically-empty orphan set and deleted nothing at all.
"""

from __future__ import annotations

import pytest

from app import db
from app.feats.base import FEATContext
from app.models import ClassEconomy, PasskeyCredential, Seat, User
from app.utils.student_deletion import (
    delete_orphaned_users,
    delete_user_if_orphaned,
    remove_student_from_teacher_scope,
)
from tests.dom.identity.helpers import admin_delete_class, valid_destruction_gate
from tests.helpers.classroom_initializer import initialize, initialize_as_teacher


def _class_delete_phrase(class_id: str) -> str:
    class_row = db.session.get(ClassEconomy, class_id)
    label = (class_row.display_name or "").strip() or class_row.join_code
    return f"DELETE {label}".upper()


def test_B3__user_with_no_remaining_seat_is_deleted(client):
    """The principal does not survive the removal of its last seat."""
    classroom = initialize("chemistry_p1", db)
    seat = classroom.students[0].seat
    user_id = seat.user_id
    assert db.session.get(User, user_id) is not None

    with FEATContext("FEAT-IDEN-007", idempotency_key="b3:last-seat"):
        db.session.delete(seat)
        db.session.flush()
        assert delete_user_if_orphaned(user_id) is True
    db.session.expire_all()

    assert db.session.get(User, user_id) is None


def test_B3__user_still_seated_elsewhere_is_preserved(client):
    """A principal with a seat in any other class is untouched."""
    class_a = initialize("chemistry_p1", db)
    class_b = initialize("biology_block_a", db)

    seat_a = class_a.students[0].seat
    user_id = seat_a.user_id

    # Give the same principal a seat in the second class, then drop the first.
    with FEATContext("FEAT-IDEN-007", idempotency_key="b3:shared-principal"):
        db.session.add(Seat(user_id=user_id, class_id=class_b.class_id, role="student"))
        db.session.flush()
        db.session.delete(seat_a)
        db.session.flush()
        assert delete_user_if_orphaned(user_id) is False
    db.session.expire_all()
    assert db.session.get(User, user_id) is not None


def test_B3__teacher_principal_is_never_swept_as_an_orphan(client):
    """Class owners are destroyed only through FEAT-IDEN-007, never the sweep."""
    classroom = initialize("chemistry_p1", db)
    teacher_user_id = classroom.teacher_user.id

    # Strip every seat the teacher holds so only class ownership protects them.
    with FEATContext("FEAT-IDEN-007", idempotency_key="b3:teacher-exempt"):
        Seat.query.filter(Seat.user_id == teacher_user_id).delete(synchronize_session=False)
        db.session.flush()
        assert delete_orphaned_users([teacher_user_id]) == []
    db.session.expire_all()
    assert db.session.get(User, teacher_user_id) is not None


def test_B3__detaching_a_students_only_seat_deletes_the_principal(client):
    """The production detach path removes the principal, not just the link."""
    classroom = initialize("chemistry_p1", db)
    seat = classroom.students[0].seat
    seat_id = seat.id
    user_id = seat.user_id

    with FEATContext("FEAT-IDEN-007", idempotency_key="b3:detach"):
        assert remove_student_from_teacher_scope(seat_id, classroom.teacher_user.id) is True
        db.session.flush()
    db.session.expire_all()

    assert db.session.get(User, user_id) is None
    # The seat survives as an unclaimed roster slot owned by the class.
    surviving = db.session.get(Seat, seat_id)
    assert surviving is not None
    assert surviving.user_id is None


def test_B3__class_destruction_deletes_principals_it_orphans(client, app):
    """Class teardown must not leave a field of parentless users behind."""
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    class_id = classroom.class_id

    student_user_ids = [s.seat.user_id for s in classroom.students]
    assert student_user_ids
    assert all(db.session.get(User, uid) is not None for uid in student_user_ids)

    resp = admin_delete_class(
        client, **valid_destruction_gate(_class_delete_phrase(class_id))
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)

    db.session.expire_all()
    assert db.session.get(ClassEconomy, class_id) is None
    for uid in student_user_ids:
        assert db.session.get(User, uid) is None, f"user {uid} outlived its last seat"


def test_B3__orphan_sweep_removes_credential_material(client):
    """Credential rows must not survive the principal (PII retention)."""
    classroom = initialize("chemistry_p1", db)
    seat = classroom.students[0].seat
    user_id = seat.user_id

    with FEATContext("FEAT-IDEN-007", idempotency_key="b3:credentials"):
        db.session.add(
            PasskeyCredential(
                user_id=user_id,
                credential_id=f"cred-{user_id}",
                authenticator_name="test-key",
            )
        )
        db.session.flush()
        assert PasskeyCredential.query.filter_by(user_id=user_id).count() == 1

        db.session.delete(seat)
        db.session.flush()
        delete_user_if_orphaned(user_id)
        db.session.flush()
    db.session.expire_all()

    assert db.session.get(User, user_id) is None
    assert PasskeyCredential.query.filter_by(user_id=user_id).count() == 0
