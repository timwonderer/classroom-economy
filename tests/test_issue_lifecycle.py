from datetime import datetime, timezone

from tests.helpers.v2_fixtures import make_admin, make_sysadmin
from app.extensions import db
from app.models import User, UserRole, Admin, Issue, IssueCategory, Seat, ClassEconomy
from app.utils.opaque_refs import make_opaque_ref
from tests.helpers.class_scope import make_student_identity


def test_teacher_must_close_issue_after_final_review(client):
    teacher = make_admin("teacher_issue_lifecycle", "secret")
    db.session.add(teacher)
    db.session.flush()
    class_row = ClassEconomy(
        join_code="JOINLIFE1",
        user_id=teacher.id,
        section="A",
        display_name="A",
    )
    db.session.add(class_row)
    db.session.flush()
    student = make_student_identity(block="A", first_name="Casey", last_name="Lopez", join_code="JOINLIFE1", class_id=class_row.class_id)
    category = IssueCategory(
        name="Lifecycle Category",
        category_type="general",
        is_active=True,
    )
    db.session.add_all([student, category])
    db.session.flush()
    seat = db.session.get(Seat, student.id)

    issue = Issue(
        user_id=student.user_id,
        actor_public_id="seat-public-issue-1",
        teacher_id=teacher.id,
        class_id=class_row.class_id,
        seat_id=seat.id,
        join_code="JOINLIFE1",
        class_label="Block A",
        category_id=category.id,
        issue_type="general",
        student_explanation="Balance looked incorrect after store purchase.",
        status=Issue.STATUS_TEACHER_REVIEW,
    )
    db.session.add(issue)
    db.session.commit()

    with client.session_transaction() as sess:
        sess["is_admin"] = True
        sess["admin_id"] = teacher.id
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()

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
