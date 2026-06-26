from flask import session

from app import db
from app.models import ClassEconomy, Seat, Student, User, UserRole
from app.services.context_resolver import resolve_canonical_context
from app.services.tlcp import resolve_actor_context
from app.utils.time import utc_now
from tests.helpers.v2_fixtures import make_admin, make_sysadmin


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
    class_row = ClassEconomy(join_code="TLCP-STUDENT", teacher_id=teacher_user.id)
    db.session.add(class_row)
    db.session.flush()
    student_user = User(
        user_role=UserRole.STUDENT,
        username_hash="student-tlcp",
        username_lookup_hash="student-tlcp",
    )
    db.session.add(student_user)
    db.session.flush()
    student = Student(
        first_name="TLCP",
        last_initial="S",
        block="A",
        join_code=class_row.join_code,
        class_id=class_row.class_id,
        salt=b"1234567890123456",
        pin_hash="pin",
    )
    db.session.add(student)
    db.session.flush()
    student_id = student.id
    seat = Seat(
        user_id=student_user.id,
        class_id=class_row.class_id,
        join_code=class_row.join_code,
        role="student",
        claimed_at=utc_now(),
    )
    db.session.add(seat)
    db.session.flush()
    seat_id = seat.id
    seat_user_id = seat.user_id
    seat_public_id = seat.public_id
    class_id = class_row.class_id
    db.session.commit()
    db.session.remove()

    with app.test_request_context("/student/help-support/submit-issue", method="POST"):
        session["student_id"] = student_id
        session["user_id"] = seat_user_id
        session["current_class_id"] = class_id
        session["current_seat_id"] = seat_id

        canonical_context = resolve_canonical_context()
        context = resolve_actor_context(canonical_context)

    assert context is not None
    assert context["actor_type"] == "student"
    assert context["actor_id"] == seat_user_id
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
    class_row = ClassEconomy(join_code="TLCP-ADMIN", teacher_id=user.id)
    db.session.add(class_row)
    db.session.flush()
    teacher_seat = Seat(
        user_id=user.id,
        class_id=class_row.class_id,
        join_code=class_row.join_code,
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
        session["is_admin"] = True
        session["admin_id"] = admin_id
        session["user_id"] = user_id
        session["current_class_id"] = class_id
        session["current_seat_id"] = teacher_seat_id

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
