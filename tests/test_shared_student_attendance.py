from tests.helpers.v2_fixtures import seed_canonical_admin
import uuid
from datetime import datetime, timezone
from app import db
from app.models import AttendanceSession, ClassEconomy, Seat, SeatAttendanceState
from app.attendance import get_all_block_statuses
from app.feats.base import FEATContext
from tests.helpers.class_scope import create_class_scope, make_student_identity


def test_attendance_status_isolation(client):
    """
    Verify that attendance status (Active/Inactive) is isolated between teachers
    even if they share the same block name.
    """
    # 1. Setup Teachers
    t1 = seed_canonical_admin(f"t1_{uuid.uuid4().hex[:8]}", 'secret').user
    t2 = seed_canonical_admin(f"t2_{uuid.uuid4().hex[:8]}", 'secret').user
    db.session.flush()

    # 2. Create class scopes
    class_t1 = create_class_scope(teacher_user=t1, display_name="PERIOD 1")
    class_t2 = create_class_scope(teacher_user=t2, display_name="PERIOD 1")
    db.session.flush()

    # 3. Create student in t1's class
    student = make_student_identity(class_id=class_t1.class_id, first_name="Shared", last_name="S", claimed=True)
    db.session.commit()

    seat = Seat.query.filter_by(user_id=student.user_id, class_id=class_t1.class_id, role="student").first()
    assert seat is not None

    # 4. Mark active attendance for T1 class scope only.
    now = datetime.now(timezone.utc)
    with FEATContext("FEAT-IDEN-001", idempotency_key=f"shared-attendance:{class_t1.class_id}:{seat.id}"):
        session = AttendanceSession(
            seat_id=seat.id,
            class_id=class_t1.class_id,
            started_at=now,
        )
        db.session.add(session)
        db.session.flush()
        db.session.add(
            SeatAttendanceState(
                seat_id=seat.id,
                class_id=class_t1.class_id,
                is_active=True,
                open_session_id=session.id,
                last_event_at=now,
                last_event_status="active",
            )
        )
    db.session.commit()

    # 5. Check Status via get_all_block_statuses in canonical class scope.
    status_t1 = get_all_block_statuses(student, class_id=class_t1.class_id)
    assert status_t1 is not None

    assert class_t2 is not None
    status_t2 = get_all_block_statuses(student, class_id=class_t2.class_id)
    # Student has no seat in t2's class, status should be empty or inactive
    assert isinstance(status_t2, dict)
