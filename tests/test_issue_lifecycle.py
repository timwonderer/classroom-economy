from datetime import datetime, timezone

from tests.helpers.v2_fixtures import make_admin, make_sysadmin
from app.extensions import db
from app.models import User, UserRole, Admin, Issue, IssueCategory, Student, Seat, IdentityProfile, ClassEconomy, StudentTeacher
from app.utils.opaque_refs import make_opaque_ref


def test_teacher_must_close_issue_after_final_review(client):
    teacher = make_admin("teacher_issue_lifecycle", "secret")
    db.session.add(teacher)
    db.session.flush()
    class_row = ClassEconomy(
        join_code="JOINLIFE1",
        user_id=teacher.id,
        created_by_admin_id=teacher.id,
        section="A",
        display_name="A",
    )
    db.session.add(class_row)
    db.session.flush()
    profile = IdentityProfile(profile_type="student", first_name="Casey", last_name="Lopez")
    student = Student(identity_profile=profile, block="A", join_code="JOINLIFE1", class_id=class_row.class_id, salt=b"salt")
    category = IssueCategory(
        name="Lifecycle Category",
        category_type="general",
        is_active=True,
    )
    db.session.add_all([student, category])
    db.session.flush()
    db.session.add(StudentTeacher(user_id=student_user.id, teacher_id=teacher.id, class_id=class_row.class_id, join_code="JOINLIFE1"))
    # Auto-injected Canonical User
    student_user = User(username_hash=f"auto_{student.id}", username_lookup_hash=f"auto_l_{student.id}", user_role=UserRole.STUDENT)
    db.session.add(student_user)
    db.session.flush()
    seat = Seat(user_id=student_user.id, class_id=class_row.class_id, join_code="JOINLIFE1", block="A", block_identifier="A", role="student")
    db.session.add(seat)
    db.session.flush()
    profile.seat_id = seat.id

    issue = Issue(
        user_id=student_user.id,
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
