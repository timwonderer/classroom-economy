from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import pytest
from app.models import Student, Transaction, StoreItem, StudentItem, Admin, IdentityProfile, Seat, User, ClassMembership, StudentTeacher
from app.utils.analytics_engine import AnalyticsEngine
from app import db
import time
import re
from datetime import datetime, timezone, timedelta

@pytest.fixture
def teacher(app):
    from app.models import Admin
    from app.utils.encryption import encrypt_totp
    import pyotp
    from app.hash_utils import get_random_salt, hash_hmac

    with app.app_context():
        salt = get_random_salt()
        dob_sum_hash = hash_hmac(str(2003).encode(), salt) # 1+1+2001

        t = make_admin("teacher_test", encrypt_totp(pyotp.random_base32()),
            salt=salt,
            dob_sum_hash=dob_sum_hash
        )
        db.session.add(t)
        db.session.commit()
        return t

def test_teacher_student_lifecycle(client, teacher, app):
    """
    Test the full lifecycle of a Teacher Student account:
    1. Automatic creation on class creation/upload.
    2. Claiming process.
    3. Functionality (logging in, viewing dashboard).
    4. Constraints (cannot delete, cannot move).
    5. Exclusion from analytics/goals.
    """
    with app.app_context():
        # Merge teacher into current session
        teacher = db.session.merge(teacher)

        # 1. Verify automatic creation via helper
        from app.routes.admin import _ensure_teacher_student_seat

        # Login as teacher
        client.post('/admin/login', data={'username': "teacher_test", 'totp_code': '000000'})

        join_code = "TEACHER_TEST_CODE"
        block = "Z"
        _ensure_teacher_student_seat(teacher.id, join_code, block)

        # Verify Seat created
        tb = Seat.query.filter_by(join_code=join_code, role='teacher').first()
        assert tb is not None
        assert tb.identity_profile.first_name == "Teacher"
        assert tb.identity_profile.last_initial == "S"

        # 2. Claim the account (Step 1)
        response = client.post('/student/claim-account', data={
            'join_code': join_code,
            'first_name': 'Teacher',
            'last_name': 'Student',
            'dedupe_code': ''
        }, follow_redirects=True)

        assert response.status_code == 200

        # Verify Seat is claimed and linked
        db.session.refresh(tb)
        assert tb.claimed_at is not None
        assert tb.student_id is not None

        student = db.session.get(Student, tb.student_id)
        assert student is not None
        assert student.is_teacher is True
        assert student.block == block
        with client.session_transaction() as sess:
            claimed_user_id = sess.get('claimed_user_id')
            claimed_seat_id = sess.get('claimed_seat_id')
        assert claimed_user_id is not None
        assert claimed_seat_id is not None

        # Step 2: Create Username
        # Note: Form expects 'write_in_word'. Logic: adjective + word + random 4 digits + initials
        response = client.post('/student/create-username', data={
            'write_in_word': 'hero'
        }, follow_redirects=True)
        assert response.status_code == 200

        # Refresh student to get generated username
        db.session.refresh(student)
        # Note: username is hashed in DB, but plaintext is in session['generated_username']
        # We can't access session easily here without mocking secure cookie?
        # Actually client.session works.
        with client.session_transaction() as sess:
            generated_username = sess.get('generated_username')

        assert generated_username is not None
        assert 'hero' in generated_username
        assert re.search(r"\d{4}TS$", generated_username) is not None

        # Step 3: Setup PIN/Passphrase
        response = client.post('/student/setup-pin-passphrase', data={
            'pin': '1234',
            'passphrase': 'secure logic'
        }, follow_redirects=True)
        assert response.status_code == 200

        db.session.refresh(student)
        assert student.has_completed_setup is True

        # 3. Verify Constraints

        # A. Cannot delete via admin
        with client.session_transaction() as sess:
            sess['admin_id'] = teacher.id
            sess['is_admin'] = True

        response = client.post('/admin/student/delete', data={
            'student_id': student.id,
            'confirmation': 'DELETE'
        }, follow_redirects=True)

        assert "Teacher student accounts cannot be deleted directly" in response.get_data(as_text=True)

        db.session.refresh(student)

        # B. Cannot move via edit
        response = client.post('/admin/student/edit', data={
            'student_id': student.id,
            'first_name': 'Teacher',
            'last_name': 'Student',
            'blocks': ['A', 'B']
        }, follow_redirects=True)

        assert "Teacher student accounts cannot be moved" in response.get_data(as_text=True)

        db.session.refresh(student)
        assert student.block == "Z"

        # 4. Analytics Exclusion
        from app.hash_utils import get_random_salt

        regular_student = Student(
            first_name="Regular",
            last_initial="R",
            block="Z",
            is_teacher=False,
            salt=get_random_salt(),
            first_half_hash=b'fakehash',
        )
        db.session.add(regular_student)
        db.session.commit()

        from app.models import ClassEconomy
        class_row = ClassEconomy.query.filter_by(join_code=join_code).first()
        regular_seat = Seat(
            student_id=regular_student.id,
            class_id=class_row.class_id if class_row else None,
            join_code=join_code,
            block="Z",
            block_identifier="Z",
            role="student",
            claimed_at=datetime.now(timezone.utc),
        )
        db.session.add(regular_seat)
        db.session.flush()
        db.session.add(IdentityProfile(seat_id=regular_seat.id, profile_type="student_claimed", first_name="Regular", last_initial="R"))

        # Add StudentTeacher link
        from app.models import StudentTeacher
        st1 = StudentTeacher(student_id=regular_student.id, teacher_id=teacher.id)
        db.session.add(st1)

        db.session.commit()

        now_ts = datetime.now(timezone.utc)

        # Teacher Student transaction
        t1 = Transaction(
            student_id=student.id,
            teacher_id=teacher.id,
            join_code=join_code,
            amount=100,
            type='deposit',
            timestamp=now_ts
        )
        # Regular Student transaction
        t2 = Transaction(
            student_id=regular_student.id,
            teacher_id=teacher.id,
            join_code=join_code,
            amount=100,
            type='deposit',
            timestamp=now_ts
        )
        db.session.add_all([t1, t2])
        db.session.commit()

        # Lazy student (Inactive)
        lazy_student = Student(
            first_name="Lazy",
            last_initial="L",
            block="Z",
            is_teacher=False,
            salt=get_random_salt(),
            first_half_hash=b'fakehash2',
        )
        db.session.add(lazy_student)
        db.session.commit()

        lazy_seat = Seat(
            student_id=lazy_student.id,
            class_id=class_row.class_id if class_row else None,
            join_code=join_code,
            block="Z",
            block_identifier="Z",
            role="student",
            claimed_at=datetime.now(timezone.utc),
        )
        db.session.add(lazy_seat)
        db.session.flush()
        db.session.add(IdentityProfile(seat_id=lazy_seat.id, profile_type="student_claimed", first_name="Lazy", last_initial="L"))

        # Add StudentTeacher link
        st2 = StudentTeacher(student_id=lazy_student.id, teacher_id=teacher.id)
        db.session.add(st2)

        db.session.commit()

        # Instantiate AnalyticsEngine
        engine = AnalyticsEngine(teacher.id, join_code)

        start = now_ts - timedelta(days=1)
        end = now_ts + timedelta(days=1)

        rate, active, total = engine.calculate_participation_rate(start, end)

        # Teacher Student is EXCLUDED.
        # Regular Student is INCLUDED.
        # Lazy Student is INCLUDED.
        # Total Enrolled = 2 (Regular + Lazy).
        # Active = 1 (Regular).
        # Rate = 50.0.

        assert total == 2
        assert active == 1
        assert rate == 50.0

        # 5. Collective Goal Exclusion
        goal_item = StoreItem(
            teacher_id=teacher.id,
            name="Pizza Party",
            price=1000,
            item_type='collective',
            is_active=True
        )
        db.session.add(goal_item)
        db.session.commit()

        # Teacher student buys it (should NOT contribute)
        si_teacher = StudentItem(correlation_id='corr_test', 
            student_id=student.id,
            store_item_id=goal_item.id,
            join_code=join_code,
            status='purchased'
        )
        db.session.add(si_teacher)
        db.session.commit()

        count = StudentItem.query.join(Student).filter(
            StudentItem.store_item_id == goal_item.id,
            Student.is_teacher == False
        ).count()
        assert count == 0

        # Regular student buys it (should contribute)
        si_regular = StudentItem(correlation_id='corr_test', 
            student_id=regular_student.id,
            store_item_id=goal_item.id,
            join_code=join_code,
            status='purchased'
        )
        db.session.add(si_regular)
        db.session.commit()

        count = StudentItem.query.join(Student).filter(
            StudentItem.store_item_id == goal_item.id,
            Student.is_teacher == False
        ).count()
        assert count == 1


def test_teacher_student_reuses_identity_across_join_codes(client, teacher, app):
    """
    Verify that a teacher claiming seats in two different classes
    reuses one credential identity and adds a seat per class.
    """
    with app.app_context():
        teacher = db.session.merge(teacher)
        from app.routes.admin import _ensure_teacher_student_seat

        join_code_a = "TEACHER_CLASS_A"
        join_code_b = "TEACHER_CLASS_B"

        _ensure_teacher_student_seat(teacher.id, join_code_a, "A")
        _ensure_teacher_student_seat(teacher.id, join_code_b, "B")
        db.session.commit()

        # Claim seat in class A
        response = client.post('/student/claim-account', data={
            'join_code': join_code_a,
            'first_name': 'Teacher',
            'last_name': 'Student',
            'dedupe_code': ''
        }, follow_redirects=True)
        assert response.status_code == 200

        tb_a = Seat.query.filter_by(
            join_code=join_code_a, role='teacher'
        ).first()
        assert tb_a.claimed_at is not None
        student_a = db.session.get(Student, tb_a.student_id)
        assert student_a is not None
        assert student_a.is_teacher is True

        # Complete setup for student A so it has completed_setup
        client.post('/student/create-username', data={'write_in_word': 'alpha'})
        client.post('/student/setup-pin-passphrase', data={
            'pin': '1234', 'passphrase': 'secure alpha'
        })

        student_link_count_after_a = StudentTeacher.query.filter_by(
            student_id=student_a.id,
            teacher_id=teacher.id,
        ).count()
        membership_count_after_a = ClassMembership.query.filter_by(
            student_id=student_a.id,
        ).count()
        user_a = (
            User.query.join(Seat, Seat.user_id == User.id)
            .filter(Seat.student_id == student_a.id)
            .first()
        )
        assert user_a is not None

        # Claim seat in class B (should reuse the existing teacher-shadow identity)
        response = client.post('/student/claim-account', data={
            'join_code': join_code_b,
            'first_name': 'Teacher',
            'last_name': 'Student',
            'dedupe_code': ''
        }, follow_redirects=True)
        assert response.status_code == 200

        tb_b = Seat.query.filter_by(
            join_code=join_code_b, role='teacher'
        ).first()
        assert tb_b.claimed_at is not None
        student_b = db.session.get(Student, tb_b.student_id)
        assert student_b is not None
        assert student_b.is_teacher is True

        user_b = (
            User.query.join(Seat, Seat.user_id == User.id)
            .filter(Seat.student_id == student_b.id)
            .first()
        )
        assert user_b is not None

        # V2 invariant: one teacher-shadow identity, many class-local seats
        assert student_a.id == student_b.id
        assert user_a.id == user_b.id
        assert StudentTeacher.query.filter_by(
            student_id=student_a.id,
            teacher_id=teacher.id,
        ).count() == student_link_count_after_a
        assert ClassMembership.query.filter_by(
            student_id=student_a.id,
        ).count() == membership_count_after_a + 1

        teacher_seats = (
            Seat.query.filter_by(student_id=student_a.id, user_id=user_a.id)
            .order_by(Seat.join_code.asc())
            .all()
        )
        assert len(teacher_seats) == 2
        assert {seat.join_code for seat in teacher_seats} == {join_code_a, join_code_b}
