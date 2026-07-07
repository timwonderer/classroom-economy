from flask import session

from app import db
from app.models import ClassEconomy, Seat, User, UserRole
from app.services.context_resolver import resolve_canonical_context
from app.services.tlcp import resolve_actor_context
from app.utils.time import utc_now
from tests.helpers.v2_fixtures import make_admin, make_sysadmin
from tests.helpers.canonical_session import set_canonical_context
from tests.helpers.class_scope import make_student_identity


def test_resolve_actor_context_student_session(app):
    admin = make_admin("tlcp_student_admin", "secret-admin")
    db.session.add(admin)
    db.session.flush()
    teacher_user = User(
        user_role=UserRole.TEACHER,
        username_hash=admin.username_hash,
        username_lookup_hash=admin.username_lookup_hash,
        totp_secret_encrypted=getattr(admin, "totp_secret", None),
    )
    db.session.add(teacher_user)
    db.session.flush()
    class_row = ClassEconomy(user_id=teacher_user.id)
    db.session.add(class_row)
    db.session.flush()
    student_user = User(
        user_role=UserRole.STUDENT,
        username_hash="student-tlcp",
        username_lookup_hash="student-tlcp",
    )
    db.session.add(student_user)
    db.session.flush()
    seat = make_student_identity(
        class_id=class_row.class_id,
        block="A",
        user_id=student_user.id,
        first_name="TLCP",
        last_name="S",
    )
    seat_public_id = seat.public_id
    class_id = class_row.class_id
    db.session.commit()
    db.session.remove()

    with app.test_request_context("/student/help-support/submit-issue", method="POST"):
        set_canonical_context(
            session,
            user_id=seat.user_id,
            class_id=class_id,
            seat_id=seat.id,
            role="student",
        )

        canonical_context = resolve_canonical_context()
        context = resolve_actor_context(canonical_context)

    assert context is not None
    assert context["actor_type"] == "student"
    assert context["actor_id"] == seat.user_id
    assert context["actor_public_id"] == seat_public_id
    assert context["class_id"] == class_id


def test_resolve_actor_context_admin_session(app):
    admin = make_admin("tlcp_admin_actor", "secret-admin-actor")
    db.session.add(admin)
    db.session.flush()
    user = User(
        user_role=UserRole.TEACHER,
        username_hash=admin.username_hash,
        username_lookup_hash=admin.username_lookup_hash,
        totp_secret_encrypted=getattr(admin, "totp_secret", None),
    )
    db.session.add(user)
    db.session.flush()
    class_row = ClassEconomy(user_id=user.id)
    db.session.add(class_row)
    db.session.flush()
    teacher_seat = Seat(
        user_id=user.id,
        class_id=class_row.class_id,
        role="teacher",
    )
    db.session.add(teacher_seat)
    db.session.flush()
    admin_id = admin.id
    user_id = user.id
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
    db.session.add(sysadmin)
    db.session.flush()
    sysadmin_id = sysadmin.id
    user = User(
        user_role=UserRole.SYSADMIN,
        username_hash=sysadmin.username_hash,
        username_lookup_hash=sysadmin.username_lookup_hash,
        totp_secret_encrypted=getattr(sysadmin, "totp_secret", None),
    )
    db.session.add(user)
    db.session.flush()
    user_id = user.id
    db.session.commit()
    db.session.remove()

    with app.test_request_context("/sysadmin/dashboard", method="GET"):
        session["is_system_admin"] = True
        session["sysadmin_id"] = sysadmin_id
        session["user_id"] = user_id

        context = resolve_actor_context(None)

    assert context is None


def test_resolve_actor_context_logs_missing_context(app, caplog):
    with app.test_request_context("/student/help-support/submit-issue", method="POST"):
        with caplog.at_level("ERROR"):
            context = resolve_actor_context(None)

    assert context is None
    assert any("TLCP-INVARIANT-VIOLATION: missing canonical context" in record.message for record in caplog.records)


def test_resolve_actor_context_logs_missing_seat(app, caplog):
    from unittest.mock import patch
    from app.services.context_resolver import CanonicalContext

    with app.test_request_context("/student/help-support/submit-issue", method="POST"):
        context = CanonicalContext(user_id=1, class_id="class-1", seat_id=1, actor_role="student")
        with patch("app.services.tlcp.db.session.get", return_value=None):
            with caplog.at_level("ERROR"):
                result = resolve_actor_context(context)

    assert result is None
    assert any("TLCP-INVARIANT-VIOLATION: missing canonical seat" in record.message for record in caplog.records)
