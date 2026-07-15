from flask import session

from app import db
from app.models import User
from app.services.context_resolver import resolve_canonical_context
from app.services.tlcp import resolve_actor_context
from tests.helpers.v2_fixtures import seed_canonical_admin, make_sysadmin
from tests.helpers.canonical_session import set_canonical_context
from tests.helpers.class_scope import create_class_scope, make_student_identity


def test_resolve_actor_context_student_session(app):
    teacher_user = seed_canonical_admin("tlcp_student_admin", "secret-admin").user
    db.session.flush()
    class_row = create_class_scope(teacher_user=teacher_user, join_code="TLCP-STU-01")
    seat = make_student_identity(
        class_id=class_row.class_id,
        first_name="TLCP",
        last_name="S",
    )
    seat_id = seat.id
    seat_user_id = seat.user_id
    seat_public_id = seat.public_id
    class_id = class_row.class_id
    db.session.commit()
    db.session.remove()

    with app.test_request_context("/student/help-support/submit-issue", method="POST"):
        set_canonical_context(
            session,
            user_id=seat_user_id,
            class_id=class_id,
            seat_id=seat_id,
            role="student",
        )

        canonical_context = resolve_canonical_context()
        context = resolve_actor_context(canonical_context)

    assert context is not None
    assert context["actor_type"] == "student"
    assert context["actor_id"] == seat_user_id
    assert context["actor_public_id"] == seat_public_id
    assert context["class_id"] == class_id


def test_resolve_actor_context_admin_session(app):
    teacher_user = seed_canonical_admin("tlcp_admin_actor", "secret-admin-actor").user
    db.session.flush()
    class_row = create_class_scope(teacher_user=teacher_user, join_code="TLCP-ADM-01")
    # create_class_scope → create_class creates the teacher seat; fetch it
    from app.models import Seat
    teacher_seat = Seat.query.filter_by(
        user_id=teacher_user.id, class_id=class_row.class_id, role="teacher"
    ).first()
    assert teacher_seat is not None

    user_id = teacher_user.id
    teacher_seat_id = teacher_seat.id
    teacher_public_id = teacher_seat.public_id
    class_id = class_row.class_id
    db.session.commit()
    db.session.remove()

    with app.test_request_context("/admin/dashboard", method="GET"):
        set_canonical_context(
            session,
            user_id=user_id,
            class_id=class_id,
            seat_id=teacher_seat_id,
            role="teacher",
        )

        canonical_context = resolve_canonical_context()
        context = resolve_actor_context(canonical_context)

    assert context is not None
    assert context["actor_type"] == "teacher"
    assert context["actor_id"] == user_id
    assert context["actor_public_id"] == teacher_public_id
    assert context["class_id"] == class_id


def test_resolve_actor_context_sysadmin_session(app):
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


def test_resolve_actor_context_logs_missing_context(app):
    from unittest.mock import patch

    with app.test_request_context("/student/help-support/submit-issue", method="POST"):
        with patch("app.services.tlcp.current_app.logger.error") as mock_error:
            context = resolve_actor_context(None)
            logged = [call.args[0] for call in mock_error.call_args_list]

    assert context is None
    assert any("TLCP-INVARIANT-VIOLATION: missing canonical context" in msg for msg in logged)


def test_resolve_actor_context_logs_missing_seat(app):
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
