"""Route tests for the admin issues queue (GET /admin/issues).

Regression coverage for a production defect: issues_queue() and view_issue()
previously scoped by the removed Issue.class_id column, producing a deterministic
500. The canonical v2 schema scopes issues by class_public_id.

These tests prove:
  - GET /admin/issues returns 200 for a teacher with an active class.
  - Issues from the teacher's active class are visible.
  - Issues from another class are NOT visible (multi-tenancy isolation).
  - The route does not rely on the removed Issue.class_id column.
"""

from __future__ import annotations

from app.extensions import db
from app.feats.base import FEATContext
from app.models import Issue, IssueCategory
from tests.helpers.classroom_initializer import initialize, initialize_as_teacher


IN_SCOPE_TEXT = "IN-SCOPE issue explanation marker chemistry"
OUT_OF_SCOPE_TEXT = "OUT-OF-SCOPE issue explanation marker biology"


def _make_issue(actor_public_id, class_public_id, explanation, category_id):
    return Issue(
        actor_public_id=actor_public_id,
        class_public_id=class_public_id,
        category_id=category_id,
        issue_type="general",
        student_explanation=explanation,
        status=Issue.STATUS_TEACHER_REVIEW,
    )


def test_admin_issues_queue_scoped_by_class_public_id(client, app):
    """Queue returns 200 and shows only the active class's issues."""
    # Active-class teacher (teacher_alice / chemistry_p1). This establishes the
    # canonical teacher session and last_active_class_id.
    classroom = initialize_as_teacher("chemistry_p1", client, app)

    # Out-of-scope class under a DIFFERENT teacher (teacher_brian / biology_block_a)
    # so provisioning does not repoint teacher_alice's active class.
    other_classroom = initialize("biology_block_a", app)

    with FEATContext("FEAT-TEST-SETUP", idempotency_key="admin_issues_queue:seed"):
        category = IssueCategory(
            name="Queue Scope Category",
            category_type="general",
            is_active=True,
        )
        db.session.add(category)
        db.session.flush()

        in_scope = _make_issue(
            actor_public_id=classroom.students[0].seat.public_id,
            class_public_id=classroom.economy.class_public_id,
            explanation=IN_SCOPE_TEXT,
            category_id=category.id,
        )
        out_of_scope = _make_issue(
            actor_public_id=other_classroom.students[0].seat.public_id,
            class_public_id=other_classroom.economy.class_public_id,
            explanation=OUT_OF_SCOPE_TEXT,
            category_id=category.id,
        )
        db.session.add_all([in_scope, out_of_scope])
        db.session.flush()
    db.session.commit()

    response = client.get("/admin/issues")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert IN_SCOPE_TEXT in body, "In-scope issue should be visible in the queue"
    assert OUT_OF_SCOPE_TEXT not in body, "Out-of-scope issue must not leak across classes"
