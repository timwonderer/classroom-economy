import pyotp

from app import db
from app.models import Admin, ClassEconomy, Seat, User, UserReport, UserRole
from app.utils.auth_username import build_hashed_username_fields
from tests.helpers.canonical_session import set_canonical_context


def _login_admin(client):
    auth_username = "teacher_help"
    salt, username_hash, username_lookup_hash = build_hashed_username_fields(auth_username)
    admin = Admin(
        username_hash=username_hash,
        username_lookup_hash=username_lookup_hash,
        salt=salt,
        totp_secret=pyotp.random_base32(),
    )
    db.session.add(admin)
    db.session.flush()
    user = User(
        user_role=UserRole.TEACHER,
        username_hash=username_hash,
        username_lookup_hash=username_lookup_hash,
    )
    db.session.add(user)
    db.session.flush()
    admin.user_id = user.id

    db.session.add(ClassEconomy(
        class_id="help-support-class",
        user_id=admin.id,
        join_code="ELA123",
        display_name="ELA",
        section="A",
        status="active",
    ))
    teacher_seat = Seat(
        user_id=user.id,
        class_id="help-support-class",
        role="teacher",
        block="A",
        block_identifier="A",
        claimed_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    )
    db.session.add(teacher_seat)
    db.session.commit()
    with client.session_transaction() as sess:
        sess["admin_id"] = admin.id
        sess["is_admin"] = True
        set_canonical_context(
            sess,
            user_id=user.id,
            class_id="help-support-class",
            seat_id=teacher_seat.id,
            role="teacher",
            join_code="ELA123",
        )


def test_help_support_page_renders(client):
    _login_admin(client)

    response = client.get("/admin/help-support", follow_redirects=False)

    assert response.status_code == 200
    assert b"Submit Support Ticket" in response.data


def test_teacher_can_submit_class_scoped_support_ticket(client):
    _login_admin(client)

    response = client.post(
        "/admin/help-support",
        data={
            "join_code": "ELA123",
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
    assert report.description.startswith("SUPPORT_SCOPE|class_id=help-support-class|join_code=ELA123|class_label=ELA|category=general")
