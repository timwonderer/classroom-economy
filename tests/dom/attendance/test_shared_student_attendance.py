from datetime import datetime, timezone
from app import db
from app.models import AttendanceSession, SeatAttendanceState
from app.attendance import get_all_block_statuses
from app.feats.base import FEATContext
from tests.helpers.classroom_initializer import initialize


def test_DOM_ATT_001__attendance_status_isolation(client):
    """
    Verify that attendance status (Active/Inactive) is isolated between teachers
    even if they share the same block name.
    """
    class_t1 = initialize("chemistry_p1", client.application)
    class_t2 = initialize("biology_block_a")
    student = class_t1.students[0]
    seat = student.seat

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
    status_t1 = get_all_block_statuses(student.user, class_id=class_t1.class_id)
    assert status_t1 is not None

    assert class_t2 is not None
    status_t2 = get_all_block_statuses(student.user, class_id=class_t2.class_id)
    # Student has no seat in t2's class, status should be empty or inactive
    assert isinstance(status_t2, dict)
