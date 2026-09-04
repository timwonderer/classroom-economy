"""Destruction authority / presentation boundary (INV-CORE-000 §III.1, §III.4).

Both teacher-facing destruction surfaces resolve their target *exclusively*
from the canonical context:

    canonical user_id  -> account deletion authority
    canonical class_id -> class deletion authority

Display values (``identity_profiles`` names, ``ClassEconomy.display_name``,
``join_code``) exist only to render a human-readable confirmation phrase. They
must never select, switch, or authorize a deletion target.

These tests pin that boundary, plus the destruction gate itself, which must
fail closed and has no alias-echo bypass.
"""

from __future__ import annotations

import pytest

from app.extensions import db
from app.feats.base import FEATContext
from app.models import ClassEconomy, IdentityProfile, Seat, User
from tests.dom.identity.helpers import admin_delete_class, valid_destruction_gate
from tests.helpers.canonical_session import set_canonical_context
from tests.helpers.classroom_initializer import initialize, initialize_as_teacher


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _teacher_seat(classroom):
    return Seat.query.filter_by(class_id=classroom.class_id, role="teacher").first()


def _login(client, classroom):
    seat = _teacher_seat(classroom)
    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=classroom.teacher_user.id,
            class_id=classroom.class_id,
            seat_id=seat.id,
            role="admin",
        )
    return seat


def _class_phrase(class_id: str) -> str:
    """Mirror the route's lawful Class display read."""
    row = ClassEconomy.query.filter_by(class_id=class_id).first()
    return f"DELETE {(row.display_name or '').strip() or row.join_code}".upper()


def _account_form(phrase: str) -> dict:
    return {
        "request_type": "account",
        "gate_phrase": phrase,
        "gate_countdown_seconds": 30,
        "gate_hold_seconds": 10,
    }


def _give_teacher_profile(classroom, first_name="Dana", last_name="Okonkwo"):
    seat = _teacher_seat(classroom)
    with FEATContext("FEAT-IDEN-001", idempotency_key=f"destruction-boundary:profile:{seat.id}"):
        db.session.add(IdentityProfile(
            seat_id=seat.id,
            class_id=classroom.class_id,
            profile_type="teacher",
            first_name=first_name,
            last_name=last_name,
        ))
        db.session.flush()
    return f"DELETE {first_name} {last_name}'S ACCOUNT".upper()


# ---------------------------------------------------------------------------
# Account deletion — target is the canonical user_id, display is presentation
# ---------------------------------------------------------------------------

def test_account_delete_page_never_exposes_internal_user_id(client, app):
    """The confirmation phrase must not leak ``users.id`` (the old USER_<id>)."""
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    user_id = classroom.teacher_user.id

    response = client.get("/admin/account-delete")
    assert response.status_code == 200

    body = response.get_data(as_text=True)
    assert f"USER_{user_id}" not in body.upper()


def test_account_delete_gate_is_bound_to_the_rendered_form(client, app):
    """Regression: the gate script must bind to the form that actually exists.

    The template previously looked up ``deletion-request-form`` while the form
    was rendered as ``account-delete-form``. ``getElementById`` returned null,
    the submit listener threw, and the page posted natively with an empty
    ``gate_phrase`` — the modal never fired and the server rejected the phrase.
    """
    initialize_as_teacher("chemistry_p1", client, app)

    body = client.get("/admin/account-delete").get_data(as_text=True)

    assert 'id="account-delete-form"' in body
    assert "getElementById('account-delete-form')" in body
    assert "deletion-request-form" not in body
    # The phrase the script types into the gate is server-rendered, not
    # reconstructed client-side from an identity value.
    assert "data-confirmation-phrase=" in body
    assert "dataset.confirmationPhrase" in body


def test_account_delete_uses_identity_profile_display_name(client, app):
    """Phrase comes from the lawful Identity display read."""
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    expected = _give_teacher_profile(classroom)

    body = client.get("/admin/account-delete").get_data(as_text=True)
    # Jinja escapes the apostrophe in the rendered attribute.
    assert expected.replace("'", "&#39;") in body


def test_account_delete_falls_back_to_non_identity_phrase(client, app):
    """No display identity -> safe fallback, never ``users.id``."""
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    seat = _teacher_seat(classroom)
    IdentityProfile.query.filter_by(seat_id=seat.id).delete(synchronize_session=False)
    db.session.flush()

    body = client.get("/admin/account-delete").get_data(as_text=True)
    assert "DELETE MY ACCOUNT" in body
    assert f"USER_{classroom.teacher_user.id}" not in body.upper()


def test_account_delete_display_name_is_not_an_authority_key(client, app):
    """Submitting someone else's display name deletes nothing."""
    victim = initialize("chemistry_p1", client.application)
    attacker = initialize("biology_block_a", client.application)
    _give_teacher_profile(victim, "Victim", "Teacher")
    _login(client, attacker)

    response = client.post(
        "/admin/account-delete",
        data=_account_form("DELETE VICTIM TEACHER'S ACCOUNT"),
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"confirmation phrase did not match" in response.data
    assert db.session.get(User, victim.teacher_user.id) is not None
    assert db.session.get(User, attacker.teacher_user.id) is not None


def test_account_delete_targets_only_the_canonical_user(client, app):
    """Correct gate evidence deletes the authenticated account and no other."""
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    bystander = initialize("biology_block_a", client.application)
    phrase = _give_teacher_profile(classroom)
    acting_user_id = classroom.teacher_user.id
    bystander_user_id = bystander.teacher_user.id
    assert acting_user_id != bystander_user_id

    response = client.post(
        "/admin/account-delete", data=_account_form(phrase), follow_redirects=False
    )
    assert response.status_code == 302

    db.session.expire_all()
    assert db.session.get(User, acting_user_id) is None
    assert db.session.get(User, bystander_user_id) is not None
    assert ClassEconomy.query.filter_by(class_id=bystander.class_id).first() is not None


@pytest.mark.parametrize(
    "overrides",
    [
        {"gate_phrase": ""},
        {"gate_countdown_seconds": 0},
        {"gate_countdown_seconds": 29},
        {"gate_hold_seconds": 0},
        {"gate_hold_seconds": 9},
    ],
)
def test_account_delete_gate_fails_closed(client, app, overrides):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    phrase = _give_teacher_profile(classroom)
    user_id = classroom.teacher_user.id

    payload = _account_form(phrase)
    payload.update(overrides)
    client.post("/admin/account-delete", data=payload, follow_redirects=True)

    db.session.expire_all()
    assert db.session.get(User, user_id) is not None


# ---------------------------------------------------------------------------
# Class deletion — target is the canonical class_id, alias is inert
# ---------------------------------------------------------------------------

def test_class_delete_targets_only_the_canonical_class(client, app):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    class_id = classroom.class_id

    response = admin_delete_class(client, **valid_destruction_gate(_class_phrase(class_id)))

    assert response.status_code == 200, response.get_data(as_text=True)
    db.session.expire_all()
    assert ClassEconomy.query.filter_by(class_id=class_id).first() is None


def test_class_delete_ignores_a_supplied_join_code(client, app):
    """A foreign join code cannot switch the target; only the active class dies."""
    active = initialize_as_teacher("chemistry_p1", client, app)
    other = initialize("biology_block_a", client.application)

    response = admin_delete_class(
        client,
        join_code=other.join_code,
        **valid_destruction_gate(_class_phrase(active.class_id)),
    )

    assert response.status_code == 200, response.get_data(as_text=True)
    db.session.expire_all()
    assert ClassEconomy.query.filter_by(class_id=active.class_id).first() is None
    assert ClassEconomy.query.filter_by(class_id=other.class_id).first() is not None


def test_class_delete_cannot_reach_another_teachers_class(client, app):
    """Cross-tenant: another teacher's join code destroys nothing."""
    active = initialize_as_teacher("chemistry_p1", client, app)
    foreign = initialize("biology_block_a", client.application)

    response = admin_delete_class(
        client,
        join_code=foreign.join_code,
        **valid_destruction_gate(_class_phrase(foreign.class_id)),
    )

    assert response.status_code == 400
    db.session.expire_all()
    assert ClassEconomy.query.filter_by(class_id=foreign.class_id).first() is not None
    assert ClassEconomy.query.filter_by(class_id=active.class_id).first() is not None


def test_class_delete_confirm_join_code_bypass_is_gone(client, app):
    """Echoing the public join code must not satisfy the destruction gate."""
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    class_id = classroom.class_id

    response = admin_delete_class(client, confirm_join_code=classroom.join_code)

    assert response.status_code == 400
    assert b"Confirmation failed" in response.data
    db.session.expire_all()
    assert ClassEconomy.query.filter_by(class_id=class_id).first() is not None


def test_class_delete_class_display_name_is_not_an_authority_key(client, app):
    """Display name selects nothing — a matching name on another class is inert."""
    active = initialize_as_teacher("chemistry_p1", client, app)
    other = initialize("biology_block_a", client.application)

    with FEATContext("FEAT-IDEN-001", idempotency_key="destruction-boundary:dup-display-name"):
        other_row = ClassEconomy.query.filter_by(class_id=other.class_id).first()
        active_row = ClassEconomy.query.filter_by(class_id=active.class_id).first()
        other_row.display_name = active_row.display_name
        db.session.flush()

    response = admin_delete_class(client, **valid_destruction_gate(_class_phrase(active.class_id)))

    assert response.status_code == 200, response.get_data(as_text=True)
    db.session.expire_all()
    assert ClassEconomy.query.filter_by(class_id=active.class_id).first() is None
    assert ClassEconomy.query.filter_by(class_id=other.class_id).first() is not None


@pytest.mark.parametrize(
    "overrides",
    [
        {"gate_phrase": "WRONG"},
        {"gate_phrase": ""},
        {"gate_countdown_seconds": 29},
        {"gate_hold_seconds": 9},
    ],
)
def test_class_delete_gate_fails_closed(client, app, overrides):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    class_id = classroom.class_id

    payload = valid_destruction_gate(_class_phrase(class_id))
    payload.update(overrides)
    response = admin_delete_class(client, **payload)

    assert response.status_code == 400
    db.session.expire_all()
    assert ClassEconomy.query.filter_by(class_id=class_id).first() is not None


def test_class_delete_clears_the_destroyed_canonical_pointer(client, app):
    """INV-ARC-012 §V: the destroyed class must not survive as a pointer."""
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    class_id = classroom.class_id
    user_id = classroom.teacher_user.id

    admin_delete_class(client, **valid_destruction_gate(_class_phrase(class_id)))

    db.session.expire_all()
    teacher = db.session.get(User, user_id)
    assert teacher.last_active_class_id is None
    assert teacher.last_active_seat_id is None
