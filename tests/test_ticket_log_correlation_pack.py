from datetime import datetime, timedelta, timezone

from tests.helpers.v2_fixtures import make_admin
from app import db
from app.models import Seat, User, UserRole, ActorRequestTrace, ErrorEvent, IssueCategory, ClassEconomy
from app.utils.issue_helpers import create_issue
from app.utils.time import utc_now
from tests.helpers.class_scope import make_student_identity, create_class_scope


def _create_student_issue_context():
    admin = make_admin("teacher", "base32secret3232")
    db.session.flush()

    class_row = create_class_scope(teacher_user=admin, join_code="TLCP-JOIN")
    db.session.flush()

    seat = make_student_identity(class_id=class_row.class_id, first_name="Student", last_name="S")
    actor_public_id = seat.public_id

    category = IssueCategory(name="General TLCP", category_type="general", is_active=True)
    db.session.add(category)
    db.session.flush()

    return admin, seat, class_row, category, actor_public_id


def test_create_issue_attaches_correlation_pack_with_trace_and_error(app):
    admin, student, join_code_row, category, actor_public_id = _create_student_issue_context()

    db.session.add(
        ActorRequestTrace(
            actor_type="student",
            actor_public_id=actor_public_id,
            class_id=join_code_row.class_id,
            request_id="req-test-1",
            method="POST",
            endpoint="/store/buy",
            status_code=500,
            created_at=utc_now() - timedelta(minutes=20),
        )
    )
    db.session.add(
        ErrorEvent(
            request_id="req-test-1",
            actor_type="student",
            actor_public_id=actor_public_id,
            class_id=join_code_row.class_id,
            endpoint="/store/buy",
            method="POST",
            error_class="RuntimeError",
            error_message="purchase failed",
            correlation_version=1,
            created_at=utc_now() - timedelta(minutes=15),
        )
    )
    db.session.flush()

    with app.test_request_context("/student/help-support/submit-issue", method="POST"):
        issue = create_issue(
            student=student,
            teacher_id=admin.id,
            join_code=join_code_row.join_code,
            category_id=category.id,
            explanation="Something broke",
            expected_outcome="It should work",
            include_recent_error=True,
        )

    assert issue.correlation_pack is not None
    assert issue.correlation_pack.actor_public_id == actor_public_id
    assert len(issue.correlation_pack.request_trace_json) == 1
    assert issue.correlation_pack.request_trace_json[0]["request_id"] == "req-test-1"
    assert len(issue.correlation_pack.error_refs_json) == 1
    assert issue.correlation_pack.error_refs_json[0]["error_class"] == "RuntimeError"


def test_create_issue_can_skip_recent_error_refs(app):
    admin, student, join_code_row, category, actor_public_id = _create_student_issue_context()

    db.session.add(
        ErrorEvent(
            request_id="req-test-2",
            actor_type="student",
            actor_public_id=actor_public_id,
            class_id=join_code_row.class_id,
            endpoint="/store/buy",
            method="POST",
            error_class="RuntimeError",
            error_message="purchase failed",
            correlation_version=1,
            created_at=utc_now() - timedelta(minutes=5),
        )
    )
    db.session.flush()

    with app.test_request_context("/student/help-support/submit-issue", method="POST"):
        issue = create_issue(
            student=student,
            teacher_id=admin.id,
            join_code=join_code_row.join_code,
            category_id=category.id,
            explanation="Something broke",
            include_recent_error=False,
        )

    assert issue.correlation_pack is not None
    assert issue.correlation_pack.error_refs_json == []


def test_authenticated_request_writes_trace_row(app, client):
    from sqlalchemy.orm import Session as OrmSession
    import uuid

    from app.services.tlcp import persist_request_trace

    admin = make_admin("tlcp_teacher", "base32secret9999")
    db.session.flush()
    class_row = create_class_scope(teacher_user=admin, join_code="TLCP-TRC")
    db.session.flush()
    student = make_student_identity(class_id=class_row.class_id, first_name="Trace", last_name="S")
    db.session.flush()

    request_id = uuid.uuid4().hex
    context = {
        "actor_type": "student",
        "actor_id": student.user_id,
        "actor_public_id": "seat-public-trace-test",
        "class_id": None,
        "endpoint": "/_tlcp_ping",
        "method": "GET",
    }

    with OrmSession(db.engine) as tlcp_session:
        with tlcp_session.begin():
            persist_request_trace(
                context=context,
                request_id=request_id,
                status_code=200,
                _session=tlcp_session,
            )

    trace = (
        ActorRequestTrace.query.filter_by(
            actor_type="student",
            actor_public_id="seat-public-trace-test",
            endpoint="/_tlcp_ping",
        )
        .order_by(ActorRequestTrace.id.desc())
        .first()
    )
    assert trace is not None
    assert trace.method == "GET"
    assert trace.status_code == 200
    assert trace.request_id
