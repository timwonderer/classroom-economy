from flask import session

from app import db
from app.models import User
from app.services.context_resolver import CanonicalContext, resolve_canonical_context
from app.services.tlcp import resolve_actor_context
from tests.helpers.support_domain import initialize_support_student, initialize_support_teacher
from tests.helpers.v2_fixtures import make_sysadmin


def test_DOM_SUP_001__resolve_actor_context_uses_student_canonical_context(app):
    client = app.test_client()
    classroom, student = initialize_support_student("chemistry_p1", client, app)
    canonical_context = CanonicalContext(
        user_id=student.user.id,
        class_id=classroom.class_id,
        seat_id=student.seat.id,
        actor_role="student",
    )
    context = resolve_actor_context(canonical_context)

    assert context is not None
    assert context["actor_type"] == "student"
    assert context["actor_id"] == student.user.id
    assert context["actor_public_id"] == student.seat.public_id
    assert context["class_id"] == classroom.class_id


def test_DOM_SUP_001__resolve_actor_context_uses_teacher_canonical_context(app):
    client = app.test_client()
    classroom = initialize_support_teacher("chemistry_p1", client, app)
    canonical_context = CanonicalContext(
        user_id=classroom.teacher_user.id,
        class_id=classroom.class_id,
        seat_id=classroom.teacher_seat.id,
        actor_role="teacher",
    )
    context = resolve_actor_context(canonical_context)

    assert context is not None
    assert context["actor_type"] == "teacher"
    assert context["actor_id"] == classroom.teacher_user.id
    assert context["actor_public_id"] == classroom.teacher_seat.public_id
    assert context["class_id"] == classroom.class_id


def test_DOM_SUP_001__resolve_actor_context_sysadmin_session_returns_none(app):
    sysadmin = make_sysadmin("tlcp_sysadmin_actor", "secret-sysadmin-actor")
    db.session.flush()
    sysadmin_id = sysadmin.id
    db.session.commit()
    db.session.remove()

    with app.test_request_context("/sysadmin/dashboard", method="GET"):
        session["is_system_admin"] = True
        session["sysadmin_id"] = sysadmin_id
        session["user_id"] = sysadmin_id

        context = resolve_actor_context(None)

    assert context is None


def test_DOM_SUP_001__resolve_actor_context_logs_missing_canonical_context(app):
    from unittest.mock import patch

    with app.test_request_context("/student/help-support/submit-issue", method="POST"):
        with patch("app.services.tlcp.current_app.logger.error") as mock_error:
            context = resolve_actor_context(None)
            logged = [call.args[0] for call in mock_error.call_args_list]

    assert context is None
    assert any("TLCP-INVARIANT-VIOLATION: missing canonical context" in msg for msg in logged)


def test_DOM_SUP_001__resolve_actor_context_ignores_admin_signup_path(app):
    from unittest.mock import patch

    with app.test_request_context("/admin/signup", method="POST"):
        with patch("app.services.tlcp.current_app.logger.error") as mock_error:
            context = resolve_actor_context(None)
            logged = [call.args[0] for call in mock_error.call_args_list]

    assert context is None
    assert logged == []


def test_DOM_SUP_001__resolve_actor_context_logs_missing_canonical_seat(app):
    from unittest.mock import patch
    from app.services.context_resolver import CanonicalContext

    with app.test_request_context("/student/help-support/submit-issue", method="POST"):
        ctx = CanonicalContext(user_id=1, class_id="class-1", seat_id=1, actor_role="student")
        with patch("app.services.tlcp.current_app.logger.error") as mock_error:
            with patch("app.services.tlcp.db.session.get", return_value=None):
                result = resolve_actor_context(ctx)
            logged = [call.args[0] for call in mock_error.call_args_list]

    assert result is None
    assert any("TLCP-INVARIANT-VIOLATION: missing canonical seat" in msg for msg in logged)
