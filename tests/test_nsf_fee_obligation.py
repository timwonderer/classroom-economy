"""NSF fee is recorded as an immediate fine obligation, by the business FEAT.

An NSF/overdraft fee is a FINE (SPEC-ECON-003); per DOM-OBL-001 §II.C an
immediately-collected charge is still an obligation; and per DOM-LED-001 §II the
Ledger stays domain-blind — the fine's Economic Context is Obligations-owned.
So the ORIGINATING BUSINESS FEAT, after Ledger posts the fee debit, records an
NSF_FEE obligation (ASSESSMENT + PAYMENT settled by that debit) via
``record_nsf_fee_obligation`` from within its own committing FEAT context.

These tests exercise that orchestrator directly (the unit the business FEATs
call), driving it inside a committing FEAT context exactly as store-purchase /
admin-adjustment do.
"""

from __future__ import annotations

from decimal import Decimal

from app.feats.base import FEATContext
from app.feats.nsf_fee_feat import record_nsf_fee_obligation
from app.models import ObligationAssessment
from app.services import obligations_service
from tests.helpers.classroom_initializer import initialize
from tests.helpers.ledger import create_ledger_idempotent_transaction


def _post_nsf_fee_debit(classroom, seat):
    """Post a fee debit the way Ledger resolution does, returning its id."""
    result = create_ledger_idempotent_transaction(
        idempotency_key=f"nsf-fee:{seat.id}",
        seat_id=seat.id,
        class_id=classroom.class_id,
        user_id=None,  # internal economic action anchors on class_id + seat_id
        amount=Decimal("-5.00"),
        account_type="checking",
        type="overdraft_fee",
        description="Non-sufficient funds fee",
    )
    txn = result[0] if isinstance(result, tuple) else result
    return txn.id


def test_record_nsf_fee_obligation_creates_immediate_fine(app):
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        seat = classroom.students[0].seat

        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"nsf-orch:{seat.id}"):
            fee_txn_id = _post_nsf_fee_debit(classroom, seat)
            correlation = record_nsf_fee_obligation(
                class_id=classroom.class_id,
                seat_id=seat.id,
                fee_transaction_id=fee_txn_id,
            )

        assert correlation == f"nsf-fee:{classroom.class_id}:{seat.id}:txn:{fee_txn_id}"

        # ASSESSMENT: the fine, obligation_type NSF_FEE, no bill cycle (immediate).
        assessment = ObligationAssessment.query.filter_by(
            correlation_id=correlation, event_type="ASSESSMENT"
        ).first()
        assert assessment is not None
        assert assessment.obligation_type == "NSF_FEE"
        assert assessment.seat_id == seat.id
        assert assessment.class_id == classroom.class_id
        assert assessment.bill_cycle_id is None

        # PAYMENT: settled immediately by the very fee debit that was posted.
        payment = ObligationAssessment.query.filter_by(
            correlation_id=correlation, event_type="PAYMENT"
        ).first()
        assert payment is not None
        assert payment.ledger_transaction_id == fee_txn_id

        # The fine reads as satisfied (paid alongside settlement).
        assert obligations_service.check_idempotency_satisfaction(correlation, "PAYMENT")


def test_record_nsf_fee_obligation_is_idempotent(app):
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        seat = classroom.students[0].seat

        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"nsf-orch:{seat.id}"):
            fee_txn_id = _post_nsf_fee_debit(classroom, seat)
            correlation = record_nsf_fee_obligation(
                class_id=classroom.class_id, seat_id=seat.id, fee_transaction_id=fee_txn_id
            )
            # Re-recording the same fee is a no-op (assessment dedupes by
            # correlation; payment dedupes by ledger transaction).
            record_nsf_fee_obligation(
                class_id=classroom.class_id, seat_id=seat.id, fee_transaction_id=fee_txn_id
            )

        assert ObligationAssessment.query.filter_by(
            correlation_id=correlation, event_type="ASSESSMENT"
        ).count() == 1
        assert ObligationAssessment.query.filter_by(
            correlation_id=correlation, event_type="PAYMENT"
        ).count() == 1
