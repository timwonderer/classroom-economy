from datetime import datetime, timezone
from decimal import Decimal

from tests.helpers.v2_fixtures import seed_canonical_admin, seed_student_identity
from app.feats.base import FEATContext
from app import db
from app.services import obligations_service
from app.models import (
    User,
    AnalyticsEvent,
    ClassEconomy,
    ObligationAssessment,
    RentSettings,
    Seat,
    )
from tests.helpers.admin_context import login_admin
from tests.helpers.class_scope import create_class_scope


def _make_teacher(suffix):
    return seed_canonical_admin(f"admin_arw_{suffix}", "TESTSECRET123456").user


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


def _login_admin(client, admin: User):
    class_row = ClassEconomy.query.filter_by(user_id=admin.id).order_by(ClassEconomy.class_id.asc()).first()
    assert class_row is not None
    login_admin(client, admin, class_id=class_row.class_id)
    with client.session_transaction() as sess:
        sess['is_system_admin'] = False


def test_past_due_scope_creates_one_waiver_per_date(client, app):
    with app.app_context():
        admin = _make_teacher("pd1")
        join_code = "ARW_PD1"
        first_due = datetime(2026, 1, 5, tzinfo=timezone.utc)
        class_row = create_class_scope(
            teacher_user=admin,
            join_code=join_code,
            section="A",
        )
        tb = db.session.query(Seat).filter_by(class_id=class_row.class_id, role="teacher").first()
        assert tb is not None
        _make_rent_settings("A", first_due, class_id=tb.class_id)
        student_seat = seed_student_identity(class_id=tb.class_id, first_name="Test", last_name="W").seat
        db.session.commit()

        _login_admin(client, admin)

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
        admin = _make_teacher("cur1")
        join_code = "ARW_CUR1"
        first_due = datetime(2026, 1, 5, tzinfo=timezone.utc)
        class_row = create_class_scope(teacher_user=admin, join_code=join_code, section="A")
        tb = db.session.query(Seat).filter_by(class_id=class_row.class_id, role="teacher").first()
        assert tb is not None
        _make_rent_settings("A", first_due, class_id=tb.class_id)
        student_seat = seed_student_identity(class_id=tb.class_id, first_name="Test", last_name="W").seat
        db.session.commit()

        _login_admin(client, admin)

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
        admin = _make_teacher("fut1")
        join_code = "ARW_FUT1"
        first_due = datetime(2026, 1, 5, tzinfo=timezone.utc)
        class_row = create_class_scope(teacher_user=admin, join_code=join_code, section="A")
        tb = db.session.query(Seat).filter_by(class_id=class_row.class_id, role="teacher").first()
        assert tb is not None
        _make_rent_settings("A", first_due, class_id=tb.class_id)
        student_seat = seed_student_identity(class_id=tb.class_id, first_name="Test", last_name="W").seat
        db.session.commit()

        _login_admin(client, admin)

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
        admin = _make_teacher("fp1")
        join_code = "ARW_FP1"
        first_due = datetime(2026, 1, 5, tzinfo=timezone.utc)
        class_row = create_class_scope(teacher_user=admin, join_code=join_code, section="A")
        tb = db.session.query(Seat).filter_by(class_id=class_row.class_id, role="teacher").first()
        assert tb is not None
        _make_rent_settings("A", first_due, class_id=tb.class_id)
        student_seat = seed_student_identity(class_id=tb.class_id, first_name="Test", last_name="W").seat
        db.session.commit()

        _login_admin(client, admin)

        resp = client.post(
            '/admin/rent-waiver/add',
            data={
                'student_ids': [student_seat.public_id],
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
        admin = _make_teacher("nojc1")
        first_due = datetime(2026, 1, 5, tzinfo=timezone.utc)
        class_row = create_class_scope(teacher_user=admin, join_code="ARW_NOJC", section="A")
        tb = db.session.query(Seat).filter_by(class_id=class_row.class_id, role="teacher").first()
        assert tb is not None
        _make_rent_settings("A", first_due, class_id=tb.class_id)
        student_seat = seed_student_identity(class_id=tb.class_id, first_name="Test", last_name="W").seat
        db.session.commit()

        _login_admin(client, admin)

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
        admin = _make_teacher("pd2")
        join_code = "ARW_PD2"
        first_due = datetime(2026, 1, 5, tzinfo=timezone.utc)
        class_row = create_class_scope(teacher_user=admin, join_code=join_code, section="A")
        tb = db.session.query(Seat).filter_by(class_id=class_row.class_id, role="teacher").first()
        assert tb is not None
        _make_rent_settings("A", first_due, class_id=tb.class_id)
        student_seat = seed_student_identity(class_id=tb.class_id, first_name="Test", last_name="W").seat
        db.session.commit()

        _login_admin(client, admin)

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
        admin = _make_teacher("evt1")
        join_code = "ARW_EVT1"
        first_due = datetime(2026, 1, 5, tzinfo=timezone.utc)
        class_row = create_class_scope(teacher_user=admin, join_code=join_code, section="A")
        tb = db.session.query(Seat).filter_by(class_id=class_row.class_id, role="teacher").first()
        assert tb is not None
        _make_rent_settings("A", first_due, class_id=tb.class_id)
        student_seat = seed_student_identity(class_id=tb.class_id, first_name="Test", last_name="W").seat
        db.session.commit()

        fixed_now = datetime(2026, 2, 1, tzinfo=timezone.utc)
        monkeypatch.setattr('app.routes.admin.utc_now', lambda: fixed_now)
        _login_admin(client, admin)

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

        events = AnalyticsEvent.query.filter_by(class_id=tb.class_id, event_type='rent_waiver').all()
        assert len(events) == 0


def test_remove_rent_waiver_logs_analytics_event(client, app):
    with app.app_context():
        admin = _make_teacher("rem1")
        join_code = "ARW_REM1"
        first_due = datetime(2026, 1, 5, tzinfo=timezone.utc)
        class_row = create_class_scope(teacher_user=admin, join_code=join_code, section="A")
        tb = db.session.query(Seat).filter_by(class_id=class_row.class_id, role="teacher").first()
        assert tb is not None
        _make_rent_settings("A", first_due, class_id=tb.class_id)
        with FEATContext("FEAT-OBL-001", idempotency_key="add_rent_waiver:remove_logs_analytics"):
            seat = seed_student_identity(class_id=tb.class_id, first_name="Test", last_name="W").seat
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

        _login_admin(client, admin)

        resp = client.post(f'/admin/rent-waiver/{waiver_id}/remove')
        assert resp.status_code == 302

        db.session.expire_all()
        assert ObligationAssessment.query.filter_by(id=waiver_id).count() == 0
        events = AnalyticsEvent.query.filter_by(class_id=tb.class_id, event_type='rent_waiver').all()
        assert len(events) == 0
