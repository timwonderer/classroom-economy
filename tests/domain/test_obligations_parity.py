"""Wave 7-C — Canonical obligation service tests.

These tests verify the obligations service writes and reads exclusively through
canonical tables (assessment_events, obligation_lifecycle, obligation_satisfaction,
obligation_reversal). No legacy table references.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app import db
from app.models import (
    InsuranceEnrollment,
    InsurancePolicy,
    ObligationAssessment,
    RentSettings,
    Seat,
    StudentTeacher,
    User,
)
from app.hash_utils import get_random_salt
from app.services import obligations_service
from tests.helpers.class_scope import create_class_scope
from tests.helpers.class_scope import make_student_identity
from tests.helpers.v2_fixtures import make_admin

_counter = 0


def _make_env(client):
    global _counter
    _counter += 1
    tag = f"obl-{_counter}"

    admin = make_admin(f"{tag}-teacher", "secret")
    db.session.add(admin)
    db.session.flush()

    student = make_student_identity(first_name="Canonical", last_name="T", block="A")
    db.session.add(StudentTeacher(user_id=student.user_id, teacher_id=admin.id))

    class_row = create_class_scope(
        teacher=admin,
        join_code=f"OBL-{_counter}",
        student=student,
        create_seat=True,
    )
    db.session.flush()

    teacher_seat = Seat.query.filter_by(class_id=class_row.class_id, role="teacher").first()
    seat = Seat.query.filter_by(class_id=class_row.class_id, role="student").first()
    assert seat is not None
    assert teacher_seat is not None

    rent_settings = RentSettings(
        class_id=class_row.class_id,
        block="A",
        is_enabled=True,
        rent_amount=Decimal("25.00"),
    )
    db.session.add(rent_settings)
    db.session.flush()
    rent_policy_version = obligations_service.create_and_schedule_rent_policy_version(class_row.class_id)
    assert rent_policy_version is not None

    return admin, user, student, class_row, seat, teacher_seat, rent_policy_version


class TestRentPaymentCanonical:
    def test_record_produces_assessment_lifecycle_satisfaction(self, client):
        admin, user, student, class_row, seat, teacher_seat, rent_policy_version = _make_env(client)

        assessment = obligations_service.record_rent_payment(
            seat_id=seat.id,
            class_id=class_row.class_id,
            period="A",
            amount_paid=Decimal("25.00"),
            period_month=6,
            period_year=2026,
            coverage_month=7,
            coverage_year=2026,
            was_late=False,
            late_fee_charged=Decimal("0.00"),
            cycle_idempotency_key="rent:test:2026-07",
            rent_policy_version_id=rent_policy_version.id,
        )
        db.session.commit()

        assert assessment.obligation_type == "RENT"
        assert assessment.amount_snap == rent_policy_version.rent_amount
        assert assessment.coverage_month == 7
        assert assessment.coverage_year == 2026
        assert assessment.lifecycle is not None
        assert assessment.lifecycle.status == "PAID"
        assert assessment.satisfaction is not None
        assert assessment.satisfaction.amount_paid == Decimal("25.00")
        assert assessment.satisfaction.was_late is False

    def test_has_rent_coverage(self, client):
        admin, user, student, class_row, seat, teacher_seat, rent_policy_version = _make_env(client)

        obligations_service.record_rent_payment(
            seat_id=seat.id,
            class_id=class_row.class_id,
            period="A",
            amount_paid=Decimal("20.00"),
            period_month=5,
            period_year=2026,
            coverage_month=6,
            coverage_year=2026,
            was_late=False,
            late_fee_charged=Decimal("0.00"),
            rent_policy_version_id=rent_policy_version.id,
        )
        db.session.commit()

        assert obligations_service.has_rent_coverage(seat.id, class_row.class_id, 6, 2026) is True
        assert obligations_service.has_rent_coverage(seat.id, class_row.class_id, 7, 2026) is False

    def test_get_rent_payments_for_cycle(self, client):
        admin, user, student, class_row, seat, teacher_seat, rent_policy_version = _make_env(client)

        obligations_service.record_rent_payment(
            seat_id=seat.id,
            class_id=class_row.class_id,
            period="A",
            amount_paid=Decimal("15.00"),
            period_month=4,
            period_year=2026,
            coverage_month=5,
            coverage_year=2026,
            was_late=True,
            late_fee_charged=Decimal("2.00"),
            rent_policy_version_id=rent_policy_version.id,
        )
        db.session.commit()

        results = obligations_service.get_rent_payments_for_cycle(class_row.class_id, 5, 2026)
        assert len(results) == 1
        assert results[0].satisfaction.was_late is True
        assert results[0].satisfaction.late_fee_charged == Decimal("2.00")

    def test_get_rent_payment_history_newest_first(self, client):
        admin, user, student, class_row, seat, teacher_seat, rent_policy_version = _make_env(client)

        for month in (3, 4, 5):
            obligations_service.record_rent_payment(
                seat_id=seat.id,
                class_id=class_row.class_id,
                period="A",
                amount_paid=Decimal("10.00"),
                period_month=month,
                period_year=2026,
                coverage_month=month + 1,
                coverage_year=2026,
                was_late=False,
                late_fee_charged=Decimal("0.00"),
                rent_policy_version_id=rent_policy_version.id,
            )
        db.session.commit()

        history = obligations_service.get_rent_payment_history(seat.id, class_row.class_id)
        assert len(history) == 3
        assert history[0].assessed_at >= history[1].assessed_at >= history[2].assessed_at


class TestRentWaiverCanonical:
    def test_record_produces_assessment_reversal(self, client):
        admin, user, student, class_row, seat, teacher_seat, rent_policy_version = _make_env(client)

        now = datetime.now(timezone.utc)
        assessment = obligations_service.record_rent_waiver(
            seat_id=seat.id,
            class_id=class_row.class_id,
            waiver_start_date=now - timedelta(days=5),
            waiver_end_date=now + timedelta(days=25),
            periods_count=1,
            reason="Test waiver",
            created_by_seat_id=teacher_seat.id,
        )
        db.session.commit()

        assert assessment.obligation_type == "RENT_WAIVER"
        assert assessment.lifecycle is not None
        assert assessment.lifecycle.status == "REVERSED"
        assert assessment.reversal is not None
        assert assessment.reversal.reason == "Test waiver"
        assert assessment.reversal.reversed_by_seat_id == teacher_seat.id

    def test_has_active_rent_waiver(self, client):
        admin, user, student, class_row, seat, teacher_seat, rent_policy_version = _make_env(client)

        now = datetime.now(timezone.utc)
        obligations_service.record_rent_waiver(
            seat_id=seat.id,
            class_id=class_row.class_id,
            waiver_start_date=now - timedelta(days=5),
            waiver_end_date=now + timedelta(days=25),
            periods_count=1,
        )
        db.session.commit()

        assert obligations_service.has_active_rent_waiver(seat.id, class_row.class_id, now) is True
        assert obligations_service.has_active_rent_waiver(seat.id, class_row.class_id, now + timedelta(days=60)) is False


class TestInsuranceEnrollmentCanonical:
    def test_enrollment_creates_canonical_rows(self, client):
        admin, user, student, class_row, seat, teacher_seat, rent_policy_version = _make_env(client)

        policy = InsurancePolicy(
            policy_code=f"POL-ENR-{_counter}",
            teacher_id=admin.id,
            class_id=class_row.class_id,
            title="Enrollment Policy",
            description="Test",
            premium=Decimal("5.00"),
            claim_type="transaction_monetary",
            is_monetary=True,
            max_claim_amount=Decimal("100.00"),
            is_active=True,
        )
        db.session.add(policy)
        db.session.flush()

        enrollment = obligations_service.record_insurance_enrollment(
            seat_id=seat.id,
            class_id=class_row.class_id,
            policy=policy,
            purchase_date=datetime.now(timezone.utc),
            next_payment_due=datetime.now(timezone.utc) + timedelta(days=30),
            coverage_start_date=datetime.now(timezone.utc) + timedelta(days=7),
        )
        db.session.commit()

        assert isinstance(enrollment, InsuranceEnrollment)
        assert enrollment.seat_id == seat.id
        assert enrollment.class_id == class_row.class_id
        assert enrollment.frozen_policy_title == "Enrollment Policy"

        assessment = ObligationAssessment.query.filter_by(
            seat_id=seat.id,
            class_id=class_row.class_id,
            obligation_type="INSURANCE_ENROLLMENT",
        ).one()
        assert assessment.lifecycle is not None
        assert assessment.lifecycle.status == "DUE"


class TestInsuranceClaimCanonical:

    def test_claim_lifecycle_through_resolution(self, client):
        admin, user, student, class_row, seat, teacher_seat, rent_policy_version = _make_env(client)

        policy = InsurancePolicy(
            policy_code=f"POL-OBL-{_counter}",
            teacher_id=admin.id,
            class_id=class_row.class_id,
            title="Canonical Policy",
            description="Test",
            premium=Decimal("5.00"),
            claim_type="transaction_monetary",
            is_monetary=True,
            max_claim_amount=Decimal("100.00"),
            is_active=True,
        )
        db.session.add(policy)
        db.session.flush()

        enrollment = obligations_service.record_insurance_enrollment(
            seat_id=seat.id,
            class_id=class_row.class_id,
            policy=policy,
            purchase_date=datetime.now(timezone.utc),
            next_payment_due=datetime.now(timezone.utc) + timedelta(days=30),
            coverage_start_date=datetime.now(timezone.utc) + timedelta(days=7),
        )
        db.session.flush()

        claim = obligations_service.record_insurance_claim(
            enrollment_id=enrollment.id,
            policy_id=policy.id,
            seat_id=seat.id,
            class_id=class_row.class_id,
            incident_date=datetime.now(timezone.utc),
            description="Canonical claim",
            claim_amount=Decimal("30.00"),
            claim_item=None,
            comments=None,
            transaction_id=None,
        )
        db.session.commit()

        assert obligations_service.get_claim_status(claim.id) == "DUE"

        obligations_service.apply_claim_resolution(
            claim,
            status="approved",
            teacher_notes="Approved",
            rejection_reason=None,
            processed_by_user_id=user.id,
            processed_by_seat_id=teacher_seat.id,
            processed_at=datetime.now(timezone.utc),
            approved_amount=Decimal("30.00"),
        )
        db.session.commit()

        assert obligations_service.get_claim_status(claim.id) == "PAID"

    def test_claim_rejection_produces_reversal(self, client):
        admin, user, student, class_row, seat, teacher_seat, rent_policy_version = _make_env(client)

        policy = InsurancePolicy(
            policy_code=f"POL-REJ-{_counter}",
            teacher_id=admin.id,
            class_id=class_row.class_id,
            title="Reject Policy",
            description="Test",
            premium=Decimal("5.00"),
            claim_type="transaction_monetary",
            is_monetary=True,
            max_claim_amount=Decimal("100.00"),
            is_active=True,
        )
        db.session.add(policy)
        db.session.flush()

        enrollment = obligations_service.record_insurance_enrollment(
            seat_id=seat.id,
            class_id=class_row.class_id,
            policy=policy,
            purchase_date=datetime.now(timezone.utc),
            next_payment_due=datetime.now(timezone.utc) + timedelta(days=30),
            coverage_start_date=datetime.now(timezone.utc) + timedelta(days=7),
        )
        db.session.flush()

        claim = obligations_service.record_insurance_claim(
            enrollment_id=enrollment.id,
            policy_id=policy.id,
            seat_id=seat.id,
            class_id=class_row.class_id,
            incident_date=datetime.now(timezone.utc),
            description="Will be rejected",
            claim_amount=Decimal("50.00"),
            claim_item=None,
            comments=None,
            transaction_id=None,
        )
        db.session.commit()

        obligations_service.apply_claim_resolution(
            claim,
            status="rejected",
            teacher_notes=None,
            rejection_reason="Insufficient evidence",
            processed_by_user_id=user.id,
            processed_by_seat_id=teacher_seat.id,
            processed_at=datetime.now(timezone.utc),
        )
        db.session.commit()

        assert obligations_service.get_claim_status(claim.id) == "REVERSED"
        assessment = ObligationAssessment.query.filter_by(
            cycle_idempotency_key=f"insurance-claim:{claim.id}",
        ).one()
        assert assessment.reversal is not None
        assert assessment.reversal.reason == "Insufficient evidence"
        assert assessment.reversal.reversed_by_seat_id == teacher_seat.id
