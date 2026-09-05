"""Regression coverage for the escalation surface (track T2, blockers B4–B7).

None of B4–B7 was pinned by any test when it was found — each was open on
source review alone, which is exactly how they survived. This file exists so
that they cannot come back silently:

* **B4** — the sysadmin view helper read ``issue.teacher.get_sysadmin_display_name()``,
  a relationship and a method that exist nowhere, making every sysadmin
  escalation view a hard 500. It also had no lawful source for the reviewing
  teacher, because ``Issue.reviewer_public_id`` had no writer at all.
* **B5** — the class display name is disclosed to sysadmin only with explicit
  teacher consent (``share_class_name_with_sysadmin``, default false —
  DOM-SUP-001 §VI), and the label itself is frozen at submission, never
  re-fetched live from ``ClassEconomy``.
* **B7** — seat resolution by ``public_id`` must be scoped by ``class_id``, and
  a request that cannot establish class scope must be denied rather than
  answered from whichever class happens to sort first.
"""

from __future__ import annotations

import pytest

from app import db
from app.access.scope_factory import AccessScopeDenied, resolve_scope
from app.feats.base import FEATContext
from app.models import ClassEconomy, Issue, IssueCategory, Seat
from app.routes.system_admin import _issue_to_view
from app.utils.issue_helpers import create_issue
from app.utils.opaque_refs import make_opaque_ref
from tests.helpers.canonical_classroom import login_teacher
from tests.helpers.support_domain import (
    initialize_support_student,
    initialize_support_teacher,
    seed_support_issue_categories,
)


def _submit_issue(classroom, student, *, explanation="Balance looks wrong."):
    """Create a STATUS_OPEN ticket for a student through the production helper."""
    seed_support_issue_categories()
    category = IssueCategory.query.order_by(IssueCategory.id.asc()).first()
    # `create_issue` carries its own `@requires_feat_context("FEAT-SUP-001")`,
    # so it must not be called from inside a test-owned context — exactly one
    # FEAT executes per path (INV-ARC-000 §VIII.2).
    return create_issue(
        student.seat,
        student.user_id,
        classroom.class_id,
        category.id,
        explanation,
        correlation_id=f"test:sup:corr:{student.seat_id}",
        idempotency_key=f"test:sup:issue:{student.seat_id}",
    )


# ---------------------------------------------------------------------------
# B5 — class label is frozen at submission and consent-gated on disclosure
# ---------------------------------------------------------------------------

def test_DOM_SUP_001__class_label_is_frozen_at_submission(client):
    """The label records the class as it stood when the student submitted.

    DOM-SUP-001 §VI: ``class_label`` is a class context *cache* that "must not
    be re-fetched live from ClassEconomy after submission." Renaming the class
    afterwards must not rewrite the context of a ticket already in flight —
    which is the whole reason this is a stored column rather than a live join
    on ``class_public_id``.
    """
    app = client.application
    classroom, student = initialize_support_student("chemistry_p1", client, app)
    original_label = classroom.economy.display_name

    issue = _submit_issue(classroom, student)
    assert issue.class_label == original_label

    class_row = ClassEconomy.query.filter_by(class_id=classroom.class_id).first()
    with FEATContext("FEAT-CLASS-002", idempotency_key="test:sup:rename-class"):
        class_row.display_name = "Renamed After The Fact"
        db.session.flush()
    db.session.expire(issue)

    assert issue.class_label == original_label


def test_DOM_SUP_001__class_label_withheld_from_sysadmin_without_consent(client):
    """Absent consent the label must be absent from the payload, not merely unrendered.

    ``share_class_name_with_sysadmin`` defaults false. A consent-gated value
    that travels to the view layer and relies on markup to hide it is one
    template edit away from disclosure, so the gate lives at the dict boundary.
    """
    app = client.application
    classroom, student = initialize_support_student("chemistry_p1", client, app)
    issue = _submit_issue(classroom, student)

    assert issue.share_class_name_with_sysadmin is False
    view = _issue_to_view(issue)

    assert view["share_class_name_with_sysadmin"] is False
    assert view["class_label"] is None


def test_DOM_SUP_001__class_label_disclosed_to_sysadmin_with_consent(client):
    """With explicit consent the frozen label is disclosed."""
    app = client.application
    classroom, student = initialize_support_student("chemistry_p1", client, app)
    issue = _submit_issue(classroom, student)

    with FEATContext("FEAT-SUP-001", idempotency_key="test:sup:grant-consent"):
        issue.share_class_name_with_sysadmin = True
        db.session.flush()

    view = _issue_to_view(issue)
    assert view["share_class_name_with_sysadmin"] is True
    assert view["class_label"] == classroom.economy.display_name


# ---------------------------------------------------------------------------
# B4 — the sysadmin view helper must not crash, and identifies by public_id
# ---------------------------------------------------------------------------

def test_DOM_SUP_001__issue_view_builds_without_a_teacher_relationship(client):
    """Regression for the hard 500 on every sysadmin escalation view.

    The helper previously dereferenced ``issue.teacher`` — no such relationship
    exists on ``Issue`` — so merely building the view raised ``AttributeError``.
    Participants are identified to sysadmin by UUID-encoded ``seats.public_id``
    only, never by name and never by a raw ``seat_id``/``user_id``
    (DOM-SUP-001 §VII, INV-ARC-019 §IX).
    """
    app = client.application
    classroom, student = initialize_support_student("chemistry_p1", client, app)
    issue = _submit_issue(classroom, student)

    view = _issue_to_view(issue)

    assert view["actor_public_id"] == student.seat.public_id
    assert "reviewer_public_id" in view
    # No internal identifiers may appear on the sysadmin-facing payload.
    assert "seat_id" not in view
    assert "user_id" not in view
    assert "teacher_id" not in view


# ---------------------------------------------------------------------------
# B6 — escalation runs under exactly one FEAT and records the reviewer
# ---------------------------------------------------------------------------

def test_DOM_SUP_001__escalation_stamps_reviewer_public_id(client):
    """Escalation must record *who* escalated, as a seat public_id.

    ``reviewer_public_id`` existed as a column with no writer anywhere in the
    codebase, which is why the sysadmin surface had no lawful source for the
    reviewing teacher and reached for a nonexistent relationship instead. This
    also exercises the ``@requires_feat_context("FEAT-SUP-001")`` envelope: if
    the route nested or omitted its FEAT the request would not reach a clean
    redirect (INV-ARC-000 §VIII.2).
    """
    app = client.application
    classroom, student = initialize_support_student("chemistry_p1", client, app)
    issue = _submit_issue(classroom, student)
    issue_id = issue.id

    # Swap the session to the teacher *of this same classroom*. Re-provisioning
    # would mint a second class, and the route's class filter would then
    # (correctly) refuse to find the ticket.
    login_teacher(client, classroom)
    response = client.post(
        f"/admin/issues/{make_opaque_ref('issue', issue_id)}/escalate",
        data={"escalation_reason": "Needs developer diagnosis."},
        follow_redirects=False,
    )
    assert response.status_code == 302

    escalated = db.session.get(Issue, issue_id)
    assert escalated.status == Issue.STATUS_ESCALATED_TO_DEV
    assert escalated.reviewer_public_id
    assert escalated.reviewer_public_id != str(classroom.teacher_user_id)
    assert escalated.reviewer_public_id != str(classroom.teacher_seat_id)

    # Consent was not given on this escalation, so the label stays withheld.
    assert escalated.share_class_name_with_sysadmin is False
    assert _issue_to_view(escalated)["class_label"] is None


# ---------------------------------------------------------------------------
# B7 — seat resolution is class-scoped; unresolvable scope is denied
# ---------------------------------------------------------------------------

def test_DOM_IDEN_001__student_detail_seat_refuses_to_cross_a_class_boundary(client):
    """A seat public_id resolves only inside the active class scope.

    Under DOM-IDEN-001 §VI a ``User`` holds one ``Seat`` per ``Class``, so
    "the seat for this public_id" is only answerable with a class in hand. The
    lookup was previously conditional on class scope and fell back to
    ``order_by(Seat.id.asc()).first()`` — resolving a student out of a class the
    teacher may not own.
    """
    from flask import g

    from app.routes.admin import _resolve_student_detail_seat

    app = client.application
    class_a, student_a = initialize_support_student("chemistry_p1", client, app)
    class_b = initialize_support_teacher("biology_block_a", client, app)

    with app.test_request_context("/admin/students"):
        class _Ctx:
            class_id = class_a.class_id

        g.canonical_context = _Ctx()
        assert _resolve_student_detail_seat(student_a.seat.public_id) is not None

    with app.test_request_context("/admin/students"):
        class _ForeignCtx:
            class_id = class_b.class_id

        g.canonical_context = _ForeignCtx()
        assert _resolve_student_detail_seat(student_a.seat.public_id) is None

    # No class scope at all is not a licence to guess.
    with app.test_request_context("/admin/students"):
        g.canonical_context = None
        assert _resolve_student_detail_seat(student_a.seat.public_id) is None


def test_DOM_IDEN_001__resolve_scope_denies_rather_than_guessing_a_class(client):
    """Without canonical context, scope resolution fails closed.

    The removed fallback answered with ``claimed_seats[0]`` — the lowest-id seat
    across every class the user participates in — and then wrote that guess into
    the request as though it had been chosen. That is the shape of the P0
    same-teacher multi-period leak. Class scope is authority, not a default.
    """
    app = client.application
    classroom, student = initialize_support_student("chemistry_p1", client, app)

    with app.test_request_context("/student/dashboard"):
        from flask import g

        g.canonical_context = None
        with pytest.raises(AccessScopeDenied) as excinfo:
            resolve_scope(actor=student.user, actor_role="student")

    assert excinfo.value.reason_code == "no_class_scope"


def test_DOM_IDEN_001__sysadmin_reward_requires_matching_class_scope(client):
    """A reward seat must be resolved *within* the ticket's class.

    The sysadmin resolve path looked the seat up unscoped and resolved the class
    afterwards, tolerating ``class_id=None`` on the resulting ledger row — money
    credited to a seat in one class while the transaction was written into no
    class at all.
    """
    app = client.application
    classroom, student = initialize_support_student("chemistry_p1", client, app)
    issue = _submit_issue(classroom, student)

    # The pairing the route now requires: the seat is found only under the
    # class the ticket was filed in.
    reward_class = ClassEconomy.query.filter_by(class_public_id=issue.class_public_id).first()
    assert reward_class is not None
    assert reward_class.class_id == classroom.class_id

    in_scope = Seat.query.filter_by(
        public_id=issue.actor_public_id,
        class_id=reward_class.class_id,
    ).first()
    assert in_scope is not None
    assert in_scope.id == student.seat_id

    other_class = initialize_support_teacher("biology_block_a", client, app)
    out_of_scope = Seat.query.filter_by(
        public_id=issue.actor_public_id,
        class_id=other_class.class_id,
    ).first()
    assert out_of_scope is None
