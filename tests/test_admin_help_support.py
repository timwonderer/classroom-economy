from app import db
from app.models import ClassEconomy, Seat, UserReport
from tests.helpers.canonical_session import set_canonical_context
from tests.helpers.v2_fixtures import seed_canonical_admin, seed_class_with_seat
from tests.helpers.admin_context import login_teacher


def _login_admin(client):
    teacher = seed_canonical_admin("teacher_help").user
    db.session.flush()
    class_row = seed_class_with_seat(
        teacher=teacher,
        join_code="ELA123",
        display_name="ELA",
        section="A",
    ).class_row
    login_teacher(client, teacher, class_id=class_row.class_id)
    return teacher, class_row


def test_help_support_page_renders(client):
    _login_admin(client)

    response = client.get("/admin/help-support", follow_redirects=False)

    assert response.status_code == 200
    assert b"Submit Support Ticket" in response.data


def test_teacher_can_submit_class_scoped_support_ticket(client):
    teacher, class_row = _login_admin(client)

    response = client.post(
        "/admin/help-support",
        data={
            "class_id": class_row.class_id,
            "issue_category": "general",
            "title": "Roster sync issue",
            "description": "Student roster did not sync after update.",
            "expected_behavior": "Roster should sync immediately.",
            "page_url": "/admin/students",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"submitted directly to system administration" in response.data

    report = UserReport.query.filter_by(user_type="teacher", title="Roster sync issue").first()
    assert report is not None
    assert report.title == "Roster sync issue"
    assert report.report_type == "comment"
    assert report.description.startswith(f"SUPPORT_SCOPE|class_id={class_row.class_id}|join_code=ELA123|class_label=ELA|category=general")
