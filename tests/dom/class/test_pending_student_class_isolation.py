"""Same-teacher/two-class isolation regression tests for pending-student deletion.

Guards the P0 class-isolation invariant on the repaired
``bulk_delete_pending_students`` admin route: the operation must act on exactly
the single active canonical class (``g.canonical_context.class_id``) and must
never reach a sibling class owned by the same teacher.

``chemistry_p1`` and ``ap_csp_p3`` are both owned by ``teacher_alice`` in the
canonical fixtures, so provisioning both yields one teacher owning two classes —
the precise scenario a class-isolation violation would leak across.
"""

from app.extensions import db
from app.feats.base import FEATContext
from app.hash_utils import hash_username_lookup
from app.models import IdentityProfile, Seat
from tests.helpers.classroom_initializer import initialize, initialize_as_teacher


def _add_pending_seat(class_id: str, first_name: str, last_name: str) -> int:
    """Create one unclaimed (pending) roster seat in ``class_id`` via the setup FEAT boundary."""
    with FEATContext(
        "FEAT-TEST-SETUP",
        idempotency_key=f"pending-seat:{class_id}:{first_name}:{last_name}",
    ):
        seat = Seat(
            class_id=class_id,
            role="student",
            claimed_at=None,
            user_id=None,
            claim_first_name_hash=hash_username_lookup(first_name.lower()),
            claim_last_name_hash=hash_username_lookup(last_name.lower()),
            roster_fingerprint=hash_username_lookup(
                f"{class_id}|{first_name.lower()}|{last_name.lower()}"
            ),
        )
        db.session.add(seat)
        db.session.flush()
        db.session.add(
            IdentityProfile(
                seat_id=seat.id,
                class_id=class_id,
                profile_type="student",
                first_name=first_name,
                last_name=last_name,
            )
        )
        db.session.flush()
        seat_id = seat.id
    return seat_id


def test_DOM_CLASS_001__bulk_delete_all_pending_never_crosses_class(client):
    """`all_pending: true` removes only the active class's pending seats.

    A sibling class owned by the same teacher must be untouched.
    """
    # Provision the sibling class FIRST so that initialize_as_teacher runs last
    # and leaves chemistry_p1 as the active class (both session + last_active).
    other = initialize("ap_csp_p3", client.application)
    active = initialize_as_teacher("chemistry_p1", client, client.application)
    # Same teacher, two distinct classes — the isolation boundary under test.
    assert active.teacher_user.id == other.teacher_user.id
    assert active.class_id != other.class_id

    active_pending = _add_pending_seat(active.class_id, "Penny", "Active")
    other_pending = _add_pending_seat(other.class_id, "Otto", "Outsider")

    response = client.post(
        "/admin/pending-students/bulk-delete",
        json={"all_pending": True},
    )
    assert response.status_code == 200

    db.session.expire_all()
    # Active-class pending seat is gone.
    assert db.session.get(Seat, active_pending) is None
    # Sibling-class pending seat survives — no teacher-wide fan-out.
    assert db.session.get(Seat, other_pending) is not None


def test_DOM_CLASS_001__bulk_delete_rejects_foreign_seat_id(client):
    """An explicit seat_id from a sibling class is refused, not deleted."""
    other = initialize("ap_csp_p3", client.application)
    initialize_as_teacher("chemistry_p1", client, client.application)

    other_pending = _add_pending_seat(other.class_id, "Otto", "Outsider")

    response = client.post(
        "/admin/pending-students/bulk-delete",
        json={"seat_ids": [other_pending]},
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["deleted_count"] == 0

    db.session.expire_all()
    assert db.session.get(Seat, other_pending) is not None
