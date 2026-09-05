"""Payroll policy definitions are immutable and append-only (DOM-POL-001 §VI.0/§VI.1).

Regression coverage for blocker **B2**.

``payroll_settings`` was a mutable singleton: ``upsert_payroll_settings`` fetched
the class's one row and reassigned fields on it via ``setattr``, which is exactly
the "singleton mutable settings blob" DOM-CLASS-003 §XI.4 prohibits. The table had
no ``policy_uuid`` at all, so there was nothing for a downstream record to address.

That made ``PayrollEvent``'s policy freeze decorative. A payroll run pays out all
attendance accrued since the seat's last payroll event, and
``_resolve_pay_rate_per_second`` prices it from the class's current policy row —
so rewriting that row rewrote the terms under which already-recorded work was
priced, and left no surviving record of what the terms had been. DOM-CLASS-003
("Pending Next-Cycle Payroll-Governing Changes") is explicit that a
payroll-governing change MUST NOT mutate the policy governing the open cycle
(INV-ARC-015 §VI.7).

These tests fail against the pre-fix commit: there, raising the rate from 0.25 to
2.00 leaves exactly one ``payroll_settings`` row for the class, saying 2.00, with
no version that remembers 0.25.

The invariant under test, stated positively: *a payroll submission is a new
contract, and the contract that priced work already done stays readable and
unchanged.*
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.extensions import db
from app.feats.base import FEATContext
from app.feats.prod import record_attendance_session
from app.models import AttendanceReasonCode, PayrollEvent, PayrollSettings, PolicyVersion, Transaction
from app.services.class_configuration_query_service import get_payroll_settings
from app.services.context_resolver import CanonicalContext
from app.services.payroll_settings_service import upsert_payroll_settings
from tests.helpers.class_domain import enable_class_feature
from tests.helpers.classroom_initializer import initialize, initialize_as_teacher


def _submit(class_id, **settings_data) -> PayrollSettings:
    """Submit a payroll policy the way the admin handler does."""
    with FEATContext(
        "FEAT-TEST-SETUP",
        idempotency_key=f"payroll:submit:{class_id}:{sorted(settings_data.items())}",
    ):
        setting = upsert_payroll_settings(class_id=class_id, settings_data=settings_data)
        db.session.flush()
    return setting


def _in_use_rows(class_id):
    return PayrollSettings.query.filter_by(
        class_id=class_id, availability_state="IN_USE"
    ).all()


class TestPayrollPolicyIsAppendOnly:
    """The repository accumulates versions; it does not overwrite them."""

    def test_submission_mints_a_new_row_and_retires_the_predecessor(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            original = _submit(classroom.class_id, pay_rate=Decimal("0.25"))
            original_uuid = original.policy_uuid
            assert original_uuid, "every payroll policy row carries its own version id"

            successor = _submit(classroom.class_id, pay_rate=Decimal("2.00"))

            # A new version, not an edit.
            assert successor.policy_uuid != original_uuid
            assert Decimal(successor.pay_rate) == Decimal("2.00")

            # The predecessor is still there, still saying 0.25.
            db.session.refresh(original)
            assert Decimal(original.pay_rate) == Decimal("0.25")
            assert original.availability_state == "RETIRED"
            assert successor.availability_state == "IN_USE"

            # Exactly one row is selectable for new work, and it is the newest.
            in_use = _in_use_rows(classroom.class_id)
            assert len(in_use) == 1
            assert in_use[0].policy_uuid == successor.policy_uuid
            assert get_payroll_settings(classroom.class_id).policy_uuid == successor.policy_uuid

    def test_a_superseded_policy_stays_readable_by_its_uuid(self, app):
        """DOM-POL-001 §VII: retirement removes selectability, not the record."""
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            original = _submit(classroom.class_id, pay_rate=Decimal("0.25"))
            original_uuid = original.policy_uuid

            _submit(classroom.class_id, pay_rate=Decimal("2.00"))

            frozen = PayrollSettings.query.filter_by(policy_uuid=original_uuid).first()
            assert frozen is not None, "a superseded payroll policy must remain addressable"
            assert Decimal(frozen.pay_rate) == Decimal("0.25")

    def test_unspecified_terms_carry_forward_rather_than_reverting(self, app):
        """A partial submission must not silently reset the rest of the contract.

        The simple-mode form posts only a handful of fields. If the successor were
        built from column defaults, the overtime and rounding terms would quietly
        change for every future run.
        """
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            _submit(
                classroom.class_id,
                pay_rate=Decimal("0.25"),
                settings_mode="advanced",
                overtime_enabled=True,
                overtime_threshold=6.0,
                overtime_threshold_unit="hours",
                overtime_multiplier=1.5,
                rounding_mode="up",
                daily_limit_hours=4.0,
            )

            successor = _submit(classroom.class_id, pay_rate=Decimal("2.00"))

            assert Decimal(successor.pay_rate) == Decimal("2.00")
            assert successor.settings_mode == "advanced"
            assert successor.overtime_enabled is True
            assert successor.overtime_threshold == 6.0
            assert successor.overtime_threshold_unit == "hours"
            assert successor.overtime_multiplier == 1.5
            assert successor.rounding_mode == "up"
            assert successor.daily_limit_hours == 4.0

    def test_unknown_submission_field_is_rejected(self, app):
        """Silently dropping an unrecognized field would lose part of a contract."""
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            with pytest.raises(ValueError, match="Unknown payroll settings field"):
                _submit(classroom.class_id, pay_rate=Decimal("1.00"), is_active=True)
            db.session.rollback()

    def test_in_place_payload_edit_is_rejected(self, app):
        """The model guard must refuse a write path that skipped the command.

        This failure mode is silent and retroactive, so a missed call site has to
        raise rather than quietly rewrite the terms of recorded work.
        """
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            settings = _submit(classroom.class_id, pay_rate=Decimal("0.25"))

            with pytest.raises(ValueError, match="immutable"):
                with FEATContext("FEAT-TEST-SETUP", idempotency_key="payroll:illegal"):
                    settings.pay_rate = Decimal("2.00")
                    db.session.flush()

            db.session.rollback()

    def test_availability_state_may_still_change_on_an_existing_row(self, app):
        """Availability is a projection over the row, not part of the payload."""
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            settings = _submit(classroom.class_id, pay_rate=Decimal("0.25"))

            with FEATContext("FEAT-TEST-SETUP", idempotency_key="payroll:hide"):
                settings.availability_state = "HIDDEN"
                db.session.flush()

            db.session.refresh(settings)
            assert settings.availability_state == "HIDDEN"
            # Hidden rows are not selectable for new work.
            assert get_payroll_settings(classroom.class_id) is None

    def test_next_payroll_date_remains_mutable(self, app):
        """The schedule cursor is operational state, not part of the definition.

        ``run_automatic_payroll_job`` advances it after each completed run; freezing
        it would break the recurring schedule.
        """
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            settings = _submit(classroom.class_id, pay_rate=Decimal("0.25"))
            next_run = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)

            with FEATContext("FEAT-TEST-SETUP", idempotency_key="payroll:cursor"):
                settings.next_payroll_date = next_run
                db.session.flush()

            db.session.refresh(settings)
            assert settings.next_payroll_date == next_run
            assert settings.policy_uuid  # still the same row, same version


class TestRecordedPayrollKeepsItsTerms:
    """The B2 defect proper: a raise must not rewrite what already-paid work cost."""

    def test_rate_change_leaves_the_policy_that_priced_a_run_intact(self, client):
        app = client.application
        classroom = initialize_as_teacher("chemistry_p1", client, app)
        student = classroom.students[0]

        enable_class_feature(class_id=classroom.class_id, feature="payroll")
        governing = _submit(classroom.class_id, pay_rate=Decimal("0.25"))
        governing_uuid = governing.policy_uuid

        now = datetime.now(timezone.utc)
        ctx = CanonicalContext(
            user_id=student.user.id,
            class_id=classroom.class_id,
            seat_id=student.seat.id,
            actor_role="student",
        )
        record_attendance_session(
            ctx=ctx,
            status="active",
            idempotency_key=f"test:payroll-immut:active:{student.seat.id}",
            reference_time_utc=now - timedelta(minutes=20),
        )
        record_attendance_session(
            ctx=ctx,
            status="inactive",
            reason_code=AttendanceReasonCode.DONE_FOR_DAY,
            idempotency_key=f"test:payroll-immut:inactive:{student.seat.id}",
            reference_time_utc=now - timedelta(minutes=5),
        )

        response = client.post("/admin/run_payroll")
        assert response.status_code in (200, 302), response.data

        event = PayrollEvent.query.filter_by(
            class_id=classroom.class_id,
            target_seat_id=student.seat.id,
            payroll_event_type="payroll",
        ).first()
        assert event is not None, "the run must have recorded a payroll event"
        paid = Transaction.query.filter_by(
            class_id=classroom.class_id,
            target_seat_id=student.seat.id,
            type="payroll",
        ).first()
        assert paid is not None
        amount_paid = Decimal(paid.amount)

        # The teacher grants an eightfold raise AFTER that work was paid.
        successor = _submit(classroom.class_id, pay_rate=Decimal("2.00"))

        # New work is priced at the new rate ...
        assert Decimal(get_payroll_settings(classroom.class_id).pay_rate) == Decimal("2.00")
        assert successor.policy_uuid != governing_uuid

        # ... and the policy that priced the completed run is still on file,
        # still saying 0.25. Pre-fix this row *was* the row that was rewritten.
        frozen = PayrollSettings.query.filter_by(policy_uuid=governing_uuid).first()
        assert frozen is not None
        assert Decimal(frozen.pay_rate) == Decimal("0.25")
        assert frozen.availability_state == "RETIRED"

        # The recorded event and its ledger entry are untouched by the raise.
        db.session.refresh(paid)
        assert Decimal(paid.amount) == amount_paid

    def test_the_policy_version_snapshot_a_payroll_event_froze_is_not_reactivated(self, app):
        """Each submission activates a fresh payroll ``PolicyVersion`` snapshot.

        The version an event froze must stay deactivated-but-readable, so the
        event can still be explained after the terms move on.
        """
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            _submit(classroom.class_id, pay_rate=Decimal("0.25"))
            first = PolicyVersion.query.filter_by(
                class_id=classroom.class_id, domain="payroll", is_active=True
            ).one()

            _submit(classroom.class_id, pay_rate=Decimal("2.00"))

            db.session.refresh(first)
            assert first.is_active is False
            assert '"0.25"' in first.policy_payload_json or "0.25" in first.policy_payload_json

            active = PolicyVersion.query.filter_by(
                class_id=classroom.class_id, domain="payroll", is_active=True
            ).one()
            assert active.id != first.id
            assert active.version_number == first.version_number + 1
