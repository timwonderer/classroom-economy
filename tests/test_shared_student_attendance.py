
from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import uuid
from datetime import datetime, timezone
from app import db
from app.models import AttendanceSession, ClassEconomy, Seat, SeatAttendanceState, User, UserRole, Student, StudentTeacher
from app.attendance import get_all_block_statuses
from tests.helpers.class_scope import create_class_scope

def test_attendance_status_isolation(client):
    """
    Verify that attendance status (Active/Inactive) is isolated between teachers
    even if they share the same block name.
    """
    # 1. Setup Teachers
    t1 = make_admin(f"t1_{uuid.uuid4().hex[:8]}", 'secret')
    t2 = make_admin(f"t2_{uuid.uuid4().hex[:8]}", 'secret')
    db.session.add_all([t1, t2])
    db.session.commit()

    # 2. Setup Student
    student = Student(
        first_name="Shared",
        last_initial="S",
        block="PERIOD 1",
        salt=b'salt'
    )
    db.session.add(student)
    db.session.commit()

    # 3. Create Links & Seats
    db.session.add(StudentTeacher(user_id=student_user.id, teacher_id=t1.id))
    db.session.add(StudentTeacher(user_id=student_user.id, teacher_id=t2.id))
    create_class_scope(
        teacher=t1,
        join_code="JC1",
        student=student,
        block="PERIOD 1",
        display_name="PERIOD 1",
        create_claimed_teacher_block=True,
        teacher_block_claimed=True,
        create_seat=True,
    )
    create_class_scope(
        teacher=t2,
        join_code="JC2",
        student=student,
        block="PERIOD 1",
        display_name="PERIOD 1",
        create_claimed_teacher_block=True,
        teacher_block_claimed=True,
        create_seat=True,
    )
    db.session.commit()
    seat = Seat.query.filter_by(user_id=student_user.id, join_code="JC1").first()
    assert seat is not None

    # 4. Mark active attendance for T1 class scope only.
    now = datetime.now(timezone.utc)
    class_t1 = ClassEconomy.query.filter_by(join_code="JC1").first()
    assert class_t1 is not None
    session = AttendanceSession(
        user_id=student_user.id,
        seat_id=seat.id,
        class_id=class_t1.class_id,
        period="PERIOD 1",
        started_at=now,
    )
    db.session.add(session)
    db.session.flush()
    db.session.add(
        SeatAttendanceState(
            user_id=student_user.id,
            seat_id=seat.id,
            class_id=class_t1.class_id,
            period="PERIOD 1",
            is_active=True,
            open_session_id=session.id,
            last_event_at=now,
            last_event_status="active",
        )
    )
    db.session.commit()
    
    # 5. Check Status via get_all_block_statuses in canonical class scope.
    status_t1 = get_all_block_statuses(student, class_id=class_t1.class_id)
    assert "PERIOD 1" in status_t1
    assert status_t1["PERIOD 1"]["active"] is True

    class_t2 = ClassEconomy.query.filter_by(join_code="JC2").first()
    assert class_t2 is not None
    status_t2 = get_all_block_statuses(student, class_id=class_t2.class_id)
    assert "PERIOD 1" in status_t2
    # Should NOT be active because tap was for JC1
    assert status_t2["PERIOD 1"]["active"] is False
