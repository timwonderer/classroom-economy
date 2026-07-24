from __future__ import annotations

from datetime import timedelta
import json
from decimal import Decimal

from app.extensions import db
from app.feats.base import FEATContext
from app.models import ObligationAssessment, PolicyVersion, Transaction
from app.scheduled_tasks import run_insurance_cycle_for_class
from app.utils.time import utc_now
from tests.helpers.classroom_initializer import initialize


def test_DOM_OBL_003__insurance_cycle_charges_each_student_seat(app):
    classroom = initialize("chemistry_p1", app)
    now = utc_now()

    with app.app_context(), FEATContext("FEAT-TEST-INS-001", idempotency_key=f"test-insurance:{classroom.class_id}"):
        policy_version = PolicyVersion(
            class_id=classroom.class_id,
            domain="insurance",
            version_number=1,
            policy_payload_json=json.dumps(
                {
                    "premium": "12.50",
                    "charge_frequency": "weekly",
                    "waiting_period_days": 5,
                    "cycle_length_days": 7,
                }
            ),
            created_at=now,
            activated_at=now,
            is_active=True,
        )
        db.session.add(policy_version)
        db.session.flush()

        result = run_insurance_cycle_for_class(classroom.class_id, now)
        db.session.expire_all()

        student_seats = [student.seat.id for student in classroom.students]
        assessments = (
            ObligationAssessment.query.filter_by(
                class_id=classroom.class_id,
                obligation_type="INSURANCE_PREMIUM",
            )
            .order_by(ObligationAssessment.seat_id.asc())
            .all()
        )

        assert result["status"] == "ok"
        assert result["charged"] == len(student_seats)
        assert result["skipped_existing"] == 0
        assert result["cycle_length_days"] == 7
        assert [row.seat_id for row in assessments] == student_seats

        for event in assessments:
            # Per DOM-OBL-001, verify canonical event structure
            # Insurance cycle creates PAYMENT events (charges recorded in Ledger)
            assert event.obligation_type == "INSURANCE_PREMIUM"
            assert event.policy_version_id == policy_version.id

            # Amounts are stored in Ledger domain via ledger_transaction_id
            # The event type should be either ASSESSMENT (for the charge) or PAYMENT (if auto-settled)
            assert event.event_type in ['ASSESSMENT', 'PAYMENT'], f"Unexpected event_type: {event.event_type}"

        teacher_assessment = (
            ObligationAssessment.query.filter_by(
                class_id=classroom.class_id,
                seat_id=classroom.teacher_seat.id,
                obligation_type="INSURANCE_PREMIUM",
            ).first()
        )
        assert teacher_assessment is None
