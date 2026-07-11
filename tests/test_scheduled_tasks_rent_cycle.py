from datetime import timedelta
from decimal import Decimal

from app import db
from app.models import User, UserRole, ClassEconomy, RentPayment, RentSettings, Seat, IdentityProfile
from app.scheduled_tasks import run_rent_cycle_for_class
from app.utils.time import utc_now
from tests.helpers.v2_fixtures import make_admin


def _make_student() -> Seat:
    student_user = User(
        user_role=UserRole.STUDENT,
        username_hash="rent_cycle_student_hash",
        username_lookup_hash="rent_cycle_student_lookup",
    )
    db.session.add(student_user)
    db.session.flush()
    # TODO: seat needs class_id set from the ClassEconomy for join_code RENTCYCLE1
    seat = Seat(
        user_id=student_user.id,
        block="A",
        role="student",
        claimed_at=utc_now() - timedelta(days=45),
        has_received_rent_exemption=True,
    )
    db.session.add(seat)
    db.session.flush()
    db.session.add(IdentityProfile(seat_id=seat.id, profile_type="student", first_name="Rent", last_name="R"))
    return seat


def test_rent_cycle_idempotency_same_cycle(monkeypatch, app):
    with app.app_context():
        admin = make_admin("rent_cycle_teacher")
        db.session.flush()

        class_row = ClassEconomy(
            join_code="RENTCYCLE1",
            user_id=admin.id,
            status="active",
        )
        db.session.add(class_row)
        db.session.flush()

        seat = _make_student()
        seat.class_id = class_row.class_id
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
            from app.models import ClassEconomy as _CE
            _class_row = _CE.query.filter_by(class_id=class_id).first()
            payment = RentPayment(
                student_id=seat.user_id,
                seat_id=seat.id,
                class_id=class_id,
                join_code=_class_row.join_code if _class_row else None,
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
