from datetime import timedelta
from decimal import Decimal

from app import db
from app.models import User, UserRole, Admin, ClassEconomy, RentPayment, RentSettings, Seat, Student
from app.scheduled_tasks import run_rent_cycle_for_class
from app.utils.time import utc_now
from tests.helpers.v2_fixtures import make_admin


def _make_student() -> Student:
    from app.hash_utils import get_random_salt

    return Student(
        first_name="Rent",
        last_initial="R",
        block="A",
        salt=get_random_salt(),
        first_half_hash=None,
        second_half_hash=None,
    )


def test_rent_cycle_idempotency_same_cycle(monkeypatch, app):
    with app.app_context():
        admin: Admin = make_admin("rent_cycle_teacher", "secret")
        db.session.add(admin)
        db.session.flush()

        class_row = ClassEconomy(
            join_code="RENTCYCLE1",
            user_id=admin.id,
            status="active",
            created_by_admin_id=admin.id,
        )
        db.session.add(class_row)
        db.session.flush()

        student = _make_student()
        db.session.add(student)
        db.session.flush()

        # Auto-injected Canonical User
        student_user = User(username_hash=f"auto_{student.id}", username_lookup_hash=f"auto_l_{student.id}", user_role=UserRole.STUDENT)
        db.session.add(student_user)
        db.session.flush()
        seat = Seat(
            user_id=student_user.id,
            class_id=class_row.class_id,
            join_code=class_row.join_code,
            block="A",
            role="student",
            claimed_at=utc_now() - timedelta(days=45),
            has_received_rent_exemption=True,
        )
        db.session.add(seat)
        db.session.flush()

        configured_at = utc_now() - timedelta(days=60)
        settings = RentSettings(class_id=class_row.class_id,
            join_code=class_row.join_code,
            block="A",
            is_enabled=True,
            rent_amount=Decimal("10.00"),
            cycle_length_days=30,
            rent_configured_at=configured_at,
            rent_effective_at=configured_at + timedelta(days=30),
        )
        db.session.add(settings)
        db.session.commit()

        def _fake_charge(*, seat, settings, class_id, execution_time, idempotency_key):
            payment = RentPayment(
                student_id=seat.student_id,
                seat_id=seat.id,
                class_id=class_id,
                join_code=seat.join_code,
                period=seat.block or "A",
                amount_paid=settings.rent_amount,
                coverage_start_time=execution_time,
                coverage_end_time=execution_time + timedelta(days=int(settings.cycle_length_days)),
                cycle_idempotency_key=idempotency_key,
            )
            db.session.add(payment)

        monkeypatch.setattr("app.feats.rent_cycle_feat.execute_scheduled_rent_charge", _fake_charge)

        first_t = settings.rent_effective_at + timedelta(days=31, seconds=2)
        second_t = settings.rent_effective_at + timedelta(days=31, seconds=58)

        run_rent_cycle_for_class(class_row.class_id, first_t)
        run_rent_cycle_for_class(class_row.class_id, second_t)

        payments = RentPayment.query.filter_by(
            class_id=class_row.class_id,
            seat_id=seat.id,
        ).all()
        assert len(payments) == 1

