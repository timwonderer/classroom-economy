from datetime import datetime, timezone
from decimal import Decimal

from tests.helpers.v2_fixtures import make_admin, make_sysadmin
from app import db
from app.hash_utils import hash_username
from app.models import (
    Admin,
    AnalyticsEvent,
    ClassEconomy,
    ClassMembership,
    IdentityProfile,
    RentSettings,
    RentWaiver,
    Seat,
    Student,
    StudentTeacher,
    )
from tests.helpers.admin_context import login_admin


def _make_admin(suffix):
    admin = make_admin(f"admin_arw_{suffix}", "TESTSECRET123456")
    db.session.add(admin)
    db.session.flush()
    return admin


def _make_teacher_block(admin_id, block, join_code):
    economy = ClassEconomy(join_code=join_code, teacher_id=admin_id, created_by_admin_id=admin_id)
    db.session.add(economy)
    db.session.flush()
    db.session.add(ClassMembership(join_code=join_code, admin_id=admin_id, role="admin"))
    seat = Seat(
        class_id=economy.class_id,
        join_code=join_code,
        block=block,
        block_identifier=block,
        role="teacher",
    )
    db.session.add(seat)
    db.session.flush()
    db.session.add(IdentityProfile(seat_id=seat.id, profile_type="student_unclaimed", first_name="Teacher", last_initial="T"))
    db.session.flush()
    return seat


def _make_rent_settings(admin_id, block, first_due, class_id=None, join_code=None, frequency_type="weekly"):
    settings = RentSettings(
        teacher_id=admin_id,
        class_id=class_id,
        join_code=join_code,
        block=block,
        is_enabled=True,
        rent_amount=Decimal("50.00"),
        frequency_type=frequency_type,
        grace_period_days=3,
        late_penalty_amount=Decimal("5.00"),
        late_penalty_type="once",
        first_rent_due_date=first_due,
    )
    db.session.add(settings)
    db.session.flush()
    return settings


def _make_student(suffix, block="A"):
    salt = get_random_salt()
    student = Student(
        first_name="Test",
        last_initial="W",
        block=block,
        salt=salt,
        username_hash=hash_username(f"student_arw_{suffix}", salt),
        pin_hash="test-pin",
    )
    db.session.add(student)
    db.session.flush()
    return student


def _link_student(student, admin):
    db.session.add(StudentTeacher(student_id=student.id, teacher_id=admin.id))
    db.session.flush()


def _login_admin(client, admin_id, join_code):
    login_admin(client, admin_id, join_code)
    with client.session_transaction() as sess:
        sess['is_system_admin'] = False


def test_past_due_scope_creates_one_waiver_per_date(client, app):
    with app.app_context():
        admin = _make_admin("pd1")
        join_code = "ARW_PD1"
        first_due = datetime(2026, 1, 5, tzinfo=timezone.utc)
        tb = _make_teacher_block(admin.id, "A", join_code)
        _make_rent_settings(admin.id, "A", first_due, class_id=tb.class_id, join_code=join_code)
        student = _make_student("pd1_s")
        _link_student(student, admin)
        db.session.commit()

        _login_admin(client, admin.id, join_code)

        date1 = datetime(2026, 1, 5, tzinfo=timezone.utc).isoformat()
        date2 = datetime(2026, 1, 12, tzinfo=timezone.utc).isoformat()

        resp = client.post(
            '/admin/rent-waiver/add',
            data={
                'student_ids': [str(student.id)],
                'waiver_scope': ['past_due'],
                'past_due_dates': [date1, date2],
                'settings_block': 'A',
            },
        )
        assert resp.status_code == 302

        waivers = RentWaiver.query.filter_by(student_id=student.id, join_code=join_code).all()
        assert len(waivers) == 2
        for waiver in waivers:
            assert waiver.waiver_start_date == waiver.waiver_end_date
            assert waiver.periods_count == 1


def test_current_scope_creates_waiver_for_current_period(client, app):
    with app.app_context():
        admin = _make_admin("cur1")
        join_code = "ARW_CUR1"
        first_due = datetime(2026, 1, 5, tzinfo=timezone.utc)
        tb = _make_teacher_block(admin.id, "A", join_code)
        _make_rent_settings(admin.id, "A", first_due, class_id=tb.class_id, join_code=join_code)
        student = _make_student("cur1_s")
        _link_student(student, admin)
        db.session.commit()

        _login_admin(client, admin.id, join_code)

        resp = client.post(
            '/admin/rent-waiver/add',
            data={
                'student_ids': [str(student.id)],
                'waiver_scope': ['current'],
                'settings_block': 'A',
            },
        )
        assert resp.status_code == 302

        waivers = RentWaiver.query.filter_by(student_id=student.id, join_code=join_code).all()
        assert len(waivers) == 1
        assert waivers[0].periods_count == 1


def test_future_scope_creates_waiver_spanning_n_periods(client, app):
    with app.app_context():
        admin = _make_admin("fut1")
        join_code = "ARW_FUT1"
        first_due = datetime(2026, 1, 5, tzinfo=timezone.utc)
        tb = _make_teacher_block(admin.id, "A", join_code)
        _make_rent_settings(admin.id, "A", first_due, class_id=tb.class_id, join_code=join_code)
        student = _make_student("fut1_s")
        _link_student(student, admin)
        db.session.commit()

        _login_admin(client, admin.id, join_code)

        resp = client.post(
            '/admin/rent-waiver/add',
            data={
                'student_ids': [str(student.id)],
                'waiver_scope': ['future'],
                'future_periods_count': '3',
                'settings_block': 'A',
            },
        )
        assert resp.status_code == 302

        waivers = RentWaiver.query.filter_by(student_id=student.id, join_code=join_code).all()
        assert len(waivers) == 1
        assert waivers[0].periods_count == 3
        assert waivers[0].waiver_end_date > waivers[0].waiver_start_date


def test_invalid_future_periods_count_flashes_error(client, app):
    with app.app_context():
        admin = _make_admin("fp1")
        join_code = "ARW_FP1"
        first_due = datetime(2026, 1, 5, tzinfo=timezone.utc)
        tb = _make_teacher_block(admin.id, "A", join_code)
        _make_rent_settings(admin.id, "A", first_due, class_id=tb.class_id, join_code=join_code)
        student = _make_student("fp1_s")
        _link_student(student, admin)
        db.session.commit()

        _login_admin(client, admin.id, join_code)

        resp = client.post(
            '/admin/rent-waiver/add',
            data={
                'student_ids': [str(student.id)],
                'waiver_scope': ['future'],
                'future_periods_count': 'not_a_number',
                'settings_block': 'A',
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b'positive whole number' in resp.data
        assert RentWaiver.query.filter_by(student_id=student.id).count() == 0


def test_missing_join_code_flashes_error(client, app):
    with app.app_context():
        admin = _make_admin("nojc1")
        first_due = datetime(2026, 1, 5, tzinfo=timezone.utc)
        _make_rent_settings(admin.id, "A", first_due)
        student = _make_student("nojc1_s")
        _link_student(student, admin)
        db.session.commit()

        with client.session_transaction() as sess:
            sess['is_admin'] = True
            sess['admin_id'] = admin.id
            sess['is_system_admin'] = False
            sess['last_activity'] = datetime.now(timezone.utc).isoformat()

        resp = client.post(
            '/admin/rent-waiver/add',
            data={
                'student_ids': [str(student.id)],
                'waiver_scope': ['current'],
                'settings_block': 'A',
            },
        )
        assert resp.status_code == 302
        assert RentWaiver.query.filter_by(student_id=student.id).count() == 0
        with client.session_transaction() as sess:
            flashes = sess.get('_flashes', [])
        assert any('select a class' in message.lower() for _category, message in flashes)


def test_invalid_past_due_dates_skipped_count_reflects_actual(client, app):
    with app.app_context():
        admin = _make_admin("pd2")
        join_code = "ARW_PD2"
        first_due = datetime(2026, 1, 5, tzinfo=timezone.utc)
        tb = _make_teacher_block(admin.id, "A", join_code)
        _make_rent_settings(admin.id, "A", first_due, class_id=tb.class_id, join_code=join_code)
        student = _make_student("pd2_s")
        _link_student(student, admin)
        db.session.commit()

        _login_admin(client, admin.id, join_code)

        valid_date = datetime(2026, 1, 5, tzinfo=timezone.utc).isoformat()

        resp = client.post(
            '/admin/rent-waiver/add',
            data={
                'student_ids': [str(student.id)],
                'waiver_scope': ['past_due'],
                'past_due_dates': [valid_date, 'NOT_A_DATE', ''],
                'settings_block': 'A',
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200

        waivers = RentWaiver.query.filter_by(student_id=student.id, join_code=join_code).all()
        assert len(waivers) == 1
        assert b'1 past-due period' in resp.data


def test_add_rent_waiver_logs_analytics_event(client, app, monkeypatch):
    with app.app_context():
        admin = _make_admin("evt1")
        join_code = "ARW_EVT1"
        first_due = datetime(2026, 1, 5, tzinfo=timezone.utc)
        tb = _make_teacher_block(admin.id, "A", join_code)
        _make_rent_settings(admin.id, "A", first_due, class_id=tb.class_id, join_code=join_code)
        student = _make_student("evt1_s")
        _link_student(student, admin)
        db.session.commit()

        fixed_now = datetime(2026, 2, 1, tzinfo=timezone.utc)
        monkeypatch.setattr('app.routes.admin.utc_now', lambda: fixed_now)
        _login_admin(client, admin.id, join_code)

        resp = client.post(
            '/admin/rent-waiver/add',
            data={
                'student_ids': [str(student.id)],
                'waiver_scope': ['current'],
                'settings_block': 'A',
                'reason': 'Medical absence',
            },
        )
        assert resp.status_code == 302

        events = AnalyticsEvent.query.filter_by(join_code=join_code, event_type='rent_waiver').all()
        assert len(events) == 1
        assert student.full_name in events[0].description
        assert 'Medical absence' in events[0].description


def test_remove_rent_waiver_logs_analytics_event(client, app):
    with app.app_context():
        admin = _make_admin("rem1")
        join_code = "ARW_REM1"
        first_due = datetime(2026, 1, 5, tzinfo=timezone.utc)
        tb = _make_teacher_block(admin.id, "A", join_code)
        _make_rent_settings(admin.id, "A", first_due, class_id=tb.class_id, join_code=join_code)
        student = _make_student("rem1_s")
        _link_student(student, admin)
        waiver = RentWaiver(
            student_id=student.id,
            join_code=join_code,
            waiver_start_date=datetime(2026, 3, 1, tzinfo=timezone.utc),
            waiver_end_date=datetime(2026, 3, 1, tzinfo=timezone.utc),
            periods_count=1,
            created_by_teacher_id=admin.id,
        )
        db.session.add(waiver)
        db.session.commit()

        _login_admin(client, admin.id, join_code)

        resp = client.post(f'/admin/rent-waiver/{waiver.id}/remove')
        assert resp.status_code == 302

        events = AnalyticsEvent.query.filter_by(join_code=join_code, event_type='rent_waiver').all()
        assert len(events) == 1
        assert student.full_name in events[0].description
        assert 'removed' in events[0].description
