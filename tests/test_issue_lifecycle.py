from datetime import datetime, timezone

from tests.helpers.v2_fixtures import seed_canonical_admin, make_sysadmin
from app.feats.base import FEATContext
from tests.helpers.class_scope import create_class_scope, make_student_identity
from tests.helpers.admin_context import login_teacher
from app.extensions import db
from app.models import User, UserRole, Issue, IssueCategory, Seat, ClassEconomy
from app.utils.opaque_refs import make_opaque_ref


def test_teacher_must_close_issue_after_final_review(client):
    with FEATContext("FEAT-IDEN-001", idempotency_key="issue_lifecycle:setup"):
        teacher = seed_canonical_admin("teacher_issue_lifecycle").user
        class_row = create_class_scope(teacher_user=teacher, join_code="JOINLIFE1")
        student = make_student_identity(
            first_name="Casey",
            last_name="Lopez",
            class_id=class_row.class_id,
        )
    with FEATContext("FEAT-ADMN-001", idempotency_key="issue_lifecycle:seed"):
        category = IssueCategory(
            name="Lifecycle Category",
            category_type="general",
            is_active=True,
        )
        db.session.add(category)
        db.session.flush()

        issue = Issue(
            user_id=student.user_id,
            actor_public_id=student.public_id,
            class_id=class_row.class_id,
            seat_id=student.id,
            join_code="JOINLIFE1",
            class_label="Block A",
            category_id=category.id,
            issue_type="general",
            student_explanation="Balance looked incorrect after store purchase.",
            status=Issue.STATUS_TEACHER_REVIEW,
        )
        db.session.add(issue)
        db.session.flush()

    login_teacher(client, teacher, class_id=class_row.class_id)

    issue_ref = make_opaque_ref("issue", issue.id)
    resolve_resp = client.post(
        f"/admin/issues/{issue_ref}/resolve",
        data={
            "action_type": "manual_adjustment",
            "teacher_notes": "Reviewed logs and posted classroom correction separately.",
        },
        follow_redirects=False,
    )
    assert resolve_resp.status_code == 302

    db.session.refresh(issue)
    assert issue.status == Issue.STATUS_TEACHER_FINAL_REVIEW
    assert issue.closed_at is None

    close_resp = client.post(
        f"/admin/issues/{issue_ref}/close",
        data={"resolution_summary": "Ledger verified and student was informed."},
        follow_redirects=False,
    )
    assert close_resp.status_code == 302

    db.session.refresh(issue)
    assert issue.status == Issue.STATUS_CLOSED
    assert issue.closed_at is not None
    assert issue.closed_by_type == "teacher"
