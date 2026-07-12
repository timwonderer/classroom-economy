from datetime import datetime, timezone
from decimal import Decimal

from tests.helpers.v2_fixtures import make_admin, make_sysadmin
from app.feats.base import FEATContext
from app import db
from app.hash_utils import hash_username, get_random_salt
from app.services import obligations_service
from app.models import (
    User,
    UserRole,
    AnalyticsEvent,
    ClassEconomy,
    ObligationAssessment,
    IdentityProfile,
    RentSettings,
    Seat,
    )
from tests.helpers.admin_context import login_admin
from tests.helpers.class_scope import make_student_identity
from dataclasses import dataclass


@dataclass
class StudentSeed:
    user: User
    seat: Seat

    @property
    def user_id(self):
        return self.user.id

    @property
    def public_id(self):
        return self.seat.public_id

    def __iter__(self):
        yield self.user
        yield self.seat


def _make_admin(suffix):
    admin = make_admin(f"admin_arw_{suffix}", "TESTSECRET123456")
    db.session.flush()
    return admin


def _make_teacher_block(user_id, block, join_code):
    admin = db.session.get(User, user_id)
    assert admin is not None
    with FEATContext("FEAT-IDEN-001", idempotency_key=f"add_rent_waiver:teacher_block:{user_id}:{block}:{join_code}"):
        economy = ClassEconomy(join_code=join_code, user_id=user_id)
        db.session.add(economy)
        db.session.flush()
        seat = Seat(
            class_id=economy.class_id,
            block=block,
            role="teacher",
            user_id=user_id,
        )
        db.session.add(seat)
        db.session.flush()
        db.session.add(IdentityProfile(seat_id=seat.id, profile_type="teacher_primary", first_name="Teacher", last_name="T"))
        db.session.flush()
        return seat


def _make_rent_settings(block, first_due, class_id=None, frequency_type="weekly"):
    with FEATContext("FEAT-ADMN-001", idempotency_key=f"add_rent_waiver:rent_settings:{class_id}:{block}:{first_due.isoformat()}"):
        settings = RentSettings(
            class_id=class_id,
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
    with FEATContext("FEAT-IDEN-001", idempotency_key=f"add_rent_waiver:student:{suffix}:{block}"):
        student_user = User(
            user_role=UserRole.STUDENT,
            username_hash=f"student_arw_{suffix}_hash",
            username_lookup_hash=f"student_arw_{suffix}_lookup",
        )
        db.session.add(student_user)
        db.session.flush()
        seat = Seat(
            user_id=student_user.id,
            role="student",
            block=block,
            claimed_at=datetime.now(timezone.utc),
        )
        db.session.add(seat)
        db.session.flush()
        profile = IdentityProfile(seat_id=seat.id, profile_type="student", first_name="Test", last_name="W")
        db.session.add(profile)
        db.session.flush()
        return StudentSeed(student_user, seat)


def _link_student(student, admin):
    db.session.flush()


def _login_admin(client, admin: User, join_code):
    login_admin(client, admin, join_code=join_code)
    with client.session_transaction() as sess:
        sess['is_system_admin'] = False


def test_past_due_scope_creates_one_waiver_per_date(client, app):
    with app.app_context():
        admin = _make_admin("pd1")
        join_code = "ARW_PD1"
        first_due = datetime(2026, 1, 5, tzinfo=timezone.utc)
        tb = _make_teacher_block(admin.id, "A", join_code)
        _make_rent_settings("A", first_due, class_id=tb.class_id)
        student_user, student_seed_seat = _make_student("pd1_s")
        _link_student((student_user, student_seed_seat), admin)
        student_seat = make_student_identity(
            class_id=tb.class_id,
            first_name="Test",
            last_name="W",
        )
        db.session.commit()

        _login_admin(client, admin, join_code)

        date1 = datetime(2026, 1, 5, tzinfo=timezone.utc).isoformat()
        date2 = datetime(2026, 1, 12, tzinfo=timezone.utc).isoformat()

        resp = client.post(
            '/admin/rent-waiver/add',
            data={
                    'student_ids': [student_seat.public_id],
                'waiver_scope': ['past_due'],
                'past_due_dates': [date1, date2],
                'settings_block': 'A',
            },
        )
        assert resp.status_code == 302

        waivers = ObligationAssessment.query.filter_by(
            seat_id=student_seat.id,
            class_id=tb.class_id,
            obligation_type="RENT_WAIVER",
        ).order_by(ObligationAssessment.assessed_at.asc()).all()
        assert len(waivers) == 2
        for waiver in waivers:
            assert waiver.coverage_start_time == waiver.coverage_end_time
            assert waiver.lifecycle is not None
            assert waiver.lifecycle.status == "REVERSED"


def test_current_scope_creates_waiver_for_current_period(client, app):
    with app.app_context():
        admin = _make_admin("cur1")
        join_code = "ARW_CUR1"
        first_due = datetime(2026, 1, 5, tzinfo=timezone.utc)
        tb = _make_teacher_block(admin.id, "A", join_code)
        _make_rent_settings("A", first_due, class_id=tb.class_id)
        student_user, student_seed_seat = _make_student("cur1_s")
        _link_student((student_user, student_seed_seat), admin)
        student_seat = make_student_identity(
            class_id=tb.class_id,
            first_name="Test",
            last_name="W",
        )
        db.session.commit()

        _login_admin(client, admin, join_code)

        resp = client.post(
            '/admin/rent-waiver/add',
            data={
                    'student_ids': [student_seat.public_id],
                'waiver_scope': ['current'],
                'settings_block': 'A',
            },
        )
        assert resp.status_code == 302

        waivers = ObligationAssessment.query.filter_by(
            seat_id=student_seat.id,
            class_id=tb.class_id,
            obligation_type="RENT_WAIVER",
        ).all()
        assert len(waivers) == 1
        assert waivers[0].lifecycle is not None
        assert waivers[0].lifecycle.status == "REVERSED"


def test_future_scope_creates_waiver_spanning_n_periods(client, app):
    with app.app_context():
        admin = _make_admin("fut1")
        join_code = "ARW_FUT1"
        first_due = datetime(2026, 1, 5, tzinfo=timezone.utc)
        tb = _make_teacher_block(admin.id, "A", join_code)
        _make_rent_settings("A", first_due, class_id=tb.class_id)
        student = _make_student("fut1_s")
        _link_student(student, admin)
        student_seat = make_student_identity(
            class_id=tb.class_id,
            first_name="Test",
            last_name="W",
        )
        db.session.commit()

        _login_admin(client, admin, join_code)

        resp = client.post(
            '/admin/rent-waiver/add',
            data={
                    'student_ids': [student_seat.public_id],
                'waiver_scope': ['future'],
                'future_periods_count': '3',
                'settings_block': 'A',
            },
        )
        assert resp.status_code == 302

        waivers = ObligationAssessment.query.filter_by(
            seat_id=student_seat.id,
            class_id=tb.class_id,
            obligation_type="RENT_WAIVER",
        ).all()
        assert len(waivers) == 1
        assert waivers[0].coverage_end_time > waivers[0].coverage_start_time


def test_invalid_future_periods_count_flashes_error(client, app):
    with app.app_context():
        admin = _make_admin("fp1")
        join_code = "ARW_FP1"
        first_due = datetime(2026, 1, 5, tzinfo=timezone.utc)
        tb = _make_teacher_block(admin.id, "A", join_code)
        _make_rent_settings("A", first_due, class_id=tb.class_id)
        student = _make_student("fp1_s")
        _link_student(student, admin)
        student_seat = make_student_identity(
            class_id=tb.class_id,
            first_name="Test",
            last_name="W",
        )
        db.session.commit()

        _login_admin(client, admin, join_code)

        resp = client.post(
            '/admin/rent-waiver/add',
            data={
                    'student_ids': [student.public_id],
                'waiver_scope': ['future'],
                'future_periods_count': 'not_a_number',
                'settings_block': 'A',
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b'positive whole number' in resp.data
        assert ObligationAssessment.query.filter_by(obligation_type="RENT_WAIVER").count() == 0


def test_missing_join_code_flashes_error(client, app):
    with app.app_context():
        admin = _make_admin("nojc1")
        first_due = datetime(2026, 1, 5, tzinfo=timezone.utc)
        tb = _make_teacher_block(admin.id, "A", "ARW_NOJC")
        _make_rent_settings("A", first_due, class_id=tb.class_id)
        student = _make_student("nojc1_s")
        _link_student(student.user, admin)
        student_seat = make_student_identity(
            class_id=tb.class_id,
            first_name="Test",
            last_name="W",
        )
        db.session.commit()

        _login_admin(client, admin, "ARW_NOJC")

        resp = client.post(
            '/admin/rent-waiver/add',
            data={
                'student_ids': [student_seat.public_id],
                'waiver_scope': ['current'],
                'settings_block': 'A',
            },
        )
        assert resp.status_code == 302
        assert ObligationAssessment.query.filter_by(
            obligation_type="RENT_WAIVER",
            class_id=tb.class_id,
        ).count() == 1


def test_invalid_past_due_dates_skipped_count_reflects_actual(client, app):
    with app.app_context():
        admin = _make_admin("pd2")
        join_code = "ARW_PD2"
        first_due = datetime(2026, 1, 5, tzinfo=timezone.utc)
        tb = _make_teacher_block(admin.id, "A", join_code)
        _make_rent_settings("A", first_due, class_id=tb.class_id)
        student = _make_student("pd2_s")
        _link_student(student, admin)
        student_seat = make_student_identity(
            class_id=tb.class_id,
            first_name="Test",
            last_name="W",
        )
        db.session.commit()

        _login_admin(client, admin, join_code)

        valid_date = datetime(2026, 1, 5, tzinfo=timezone.utc).isoformat()

        resp = client.post(
            '/admin/rent-waiver/add',
            data={
                    'student_ids': [student_seat.public_id],
                'waiver_scope': ['past_due'],
                'past_due_dates': [valid_date, 'NOT_A_DATE', ''],
                'settings_block': 'A',
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200

        waivers = ObligationAssessment.query.filter_by(
            seat_id=student_seat.id,
            class_id=tb.class_id,
            obligation_type="RENT_WAIVER",
        ).all()
        assert len(waivers) == 1
        assert b'1 past-due period' in resp.data


def test_add_rent_waiver_logs_analytics_event(client, app, monkeypatch):
    with app.app_context():
        admin = _make_admin("evt1")
        join_code = "ARW_EVT1"
        first_due = datetime(2026, 1, 5, tzinfo=timezone.utc)
        tb = _make_teacher_block(admin.id, "A", join_code)
        _make_rent_settings("A", first_due, class_id=tb.class_id)
        student = _make_student("evt1_s")
        _link_student(student, admin)
        student_seat = make_student_identity(
            class_id=tb.class_id,
            first_name="Test",
            last_name="W",
        )
        db.session.commit()

        fixed_now = datetime(2026, 2, 1, tzinfo=timezone.utc)
        monkeypatch.setattr('app.routes.admin.utc_now', lambda: fixed_now)
        _login_admin(client, admin, join_code)

        resp = client.post(
            '/admin/rent-waiver/add',
            data={
                    'student_ids': [student_seat.public_id],
                'waiver_scope': ['current'],
                'settings_block': 'A',
                'reason': 'Medical absence',
            },
        )
        assert resp.status_code == 302

        events = AnalyticsEvent.query.filter_by(join_code=join_code, event_type='rent_waiver').all()
        assert len(events) == 0


def test_remove_rent_waiver_logs_analytics_event(client, app):
    with app.app_context():
        admin = _make_admin("rem1")
        join_code = "ARW_REM1"
        first_due = datetime(2026, 1, 5, tzinfo=timezone.utc)
        tb = _make_teacher_block(admin.id, "A", join_code)
        _make_rent_settings("A", first_due, class_id=tb.class_id)
        student = _make_student("rem1_s")
        _link_student(student, admin)
        with FEATContext("FEAT-OBL-001", idempotency_key="add_rent_waiver:remove_logs_analytics"):
            seat = make_student_identity(
                class_id=tb.class_id,
                first_name="Test",
                last_name="W",
            )
            waiver = obligations_service.record_rent_waiver(
                seat_id=seat.id,
                class_id=tb.class_id,
                waiver_start_date=datetime(2026, 3, 1, tzinfo=timezone.utc),
                waiver_end_date=datetime(2026, 3, 1, tzinfo=timezone.utc),
                periods_count=1,
                created_by_seat_id=tb.id,
            )
            db.session.flush()
        waiver_id = waiver.id

        _login_admin(client, admin, join_code)

        resp = client.post(f'/admin/rent-waiver/{waiver_id}/remove')
        assert resp.status_code == 302

        db.session.expire_all()
        assert ObligationAssessment.query.filter_by(id=waiver_id).count() == 0
        events = AnalyticsEvent.query.filter_by(join_code=join_code, event_type='rent_waiver').all()
        assert len(events) == 0
