from app.models import Issue
from app.utils.helpers import generate_anonymous_code
from tests.helpers.support_domain import (
    initialize_support_teacher,
    seed_support_issue_categories,
    submit_support_ticket,
)


def test_DOM_SUP_001__help_support_page_renders_support_ticket_form(client):
    initialize_support_teacher("chemistry_p1", client, client.application)

    response = client.get("/admin/help-support", follow_redirects=False)

    assert response.status_code == 200
    assert b"Submit Support Ticket" in response.data


def test_DOM_SUP_001__teacher_can_submit_class_scoped_support_ticket_via_admin_route(client):
    classroom = initialize_support_teacher("chemistry_p1", client, client.application)
    seed_support_issue_categories()

    response = submit_support_ticket(
        client,
        issue_category="general",
        title="Roster sync issue",
        description="Student roster did not sync after update.",
        expected_behavior="Roster should sync immediately.",
        page_url="/admin/students",
    )

    assert response.status_code == 200
    assert b"submitted directly to system administration" in response.data

    report = Issue.query.filter_by(
        actor_public_id=generate_anonymous_code(f"admin:{classroom.teacher_user.id}"),
        student_expected_outcome="Roster should sync immediately.",
    ).first()
    assert report is not None
    assert report.student_expected_outcome == "Roster should sync immediately."
    assert report.issue_type == "general"
    assert report.student_explanation.startswith(
        f"SUPPORT_SCOPE|class_id={classroom.class_id}|class_label={classroom.economy.display_name}|category=general"
    )
