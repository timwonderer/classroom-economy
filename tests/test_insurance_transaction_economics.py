"""Regression tests: TRANSACTION insurance economics + gates (Step 6).

Pins the four locked rules against the frozen contract and immutable claim
history — never the live policy:

1. Period payout ceiling CLAMPS (never rejects) an over-cap reimbursement;
   only APPROVED monetary payouts consume capacity; zero remaining capacity
   fails as CLAIM_ALLOWANCE_EXHAUSTED rather than a $0 approval.
2. Claim-per-week-equivalent allowance counts EVERY created lifecycle
   (SUBMITTED + APPROVED + REJECTED), is enforced at submission, and a later
   submission never retroactively denies an earlier claim's resolution.
3. Claim window is class-local calendar days from the source transaction date;
   a transaction on class-local date D with window N is filable through the end
   of D+N (inclusive) and rejected at D+N+1.

Uses the canonical test initializer per SPEC-TEST-001 and injects reference
times through the source transaction timestamp per SPEC-TIME-001 (no wall-clock
business decisions in the assertions).
"""

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from app.extensions import db
from app.feats.base import FEATContext
from app.models import EntitlementEvent
from app.services import insurance_definition_service as insurance_defs
from app.services.context_resolver import CanonicalContext
from app.feats.insurance_claim_feat import (
    submit_insurance_claim,
    resolve_insurance_claim,
)
from app.utils.canonical_temporal_resolver import (
    canonical_temporal_resolver,
    CLASS_LEVEL_EVALUATION,
    ensure_utc,
)
from tests.helpers.ledger import create_ledger_idempotent_transaction
from tests.helpers.classroom_initializer import initialize


def _frozen(
    *,
    premium="100.00",
    payout_multiple="1",
    reimbursement_percentage="100",
    claims_per_week_equivalent="5",
    claim_window_days=7,
) -> dict:
    return {
        "insurance_type": "TRANSACTION",
        "premium": premium,
        "charge_frequency": "WEEKLY",
        "reimbursement_percentage": reimbursement_percentage,
        "payout_multiple": payout_multiple,
        "claims_per_week_equivalent": claims_per_week_equivalent,
        "claim_window_days": claim_window_days,
    }


def _add_granted(classroom, student, entitlement_id, *, granted_at=None, **frozen_kwargs):
    # Claim-time authority is the IMMUTABLE ``insurance_policies`` row resolved via
    # the GRANTED entitlement's ``policy_uuid`` — never a ``frozen_contract`` payload
    # snapshot (FEAT-STOR-003 §1.2, DOM-STORE-001 §VII.A). A policy edit mints a new
    # ``policy_uuid``, so the referenced row IS the frozen contract. The entitlement
    # payload therefore duplicates no terms; it carries only the ``policy_uuid``
    # reference, exactly like ``grant_insurance_entitlement``.
    definition = dict(_frozen(**frozen_kwargs))
    definition["title"] = "Insurance Policy"
    policy = insurance_defs.create_insurance_definition(
        class_id=classroom.class_id,
        actor_seat_id=classroom.teacher_seat.id,
        definition=definition,
    )
    ev = EntitlementEvent(
        event_id=str(uuid4()),
        class_id=classroom.class_id,
        entitlement_id=entitlement_id,
        target_seat_id=student.seat.id,
        actor_seat_id=student.seat.id,
        product_id=None,
        entitlement_type="INSURANCE",
        acquisition_type="PURCHASE",
        event_type="GRANTED",
        payload={"policy_uuid": policy.policy_uuid},
    )
    if granted_at is not None:
        ev.timestamp = granted_at
    db.session.add(ev)
    db.session.flush()
    return ev


def _seed_loss(classroom, student, *, idem, amount, at=None):
    txn, _created = create_ledger_idempotent_transaction(
        idempotency_key=f"econ-source:{idem}:{uuid4().hex}",
        seat_id=student.seat.id,
        class_id=classroom.class_id,
        user_id=student.user.id,
        amount=Decimal(amount),
        account_type="checking",
        type="purchase",
        description="Insurance claim source loss",
        actor_seat_id=student.seat.id,
    )
    if at is not None:
        txn.timestamp = at
        db.session.flush()
    return txn


def _student_ctx(classroom, student):
    return CanonicalContext(
        user_id=student.user.id,
        class_id=classroom.class_id,
        seat_id=student.seat.id,
        actor_role="student",
    )


def _teacher_ctx(classroom):
    t = classroom.teacher_seat
    return CanonicalContext(
        user_id=t.user_id,
        class_id=classroom.class_id,
        seat_id=t.id,
        actor_role="teacher",
    )


def _now_utc(classroom, student):
    temporal = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=_student_ctx(classroom, student),
        primitive="current_time",
    )
    return ensure_utc(temporal.canonical_now_utc)


class TestPeriodPayoutCeiling:
    def test_second_approval_clamps_to_remaining_capacity_then_exhausts(self, app):
        """Ceiling = premium × payout_multiple = 10.00. Two 8.00 losses at 100%:
        first pays 8.00, second CLAMPS to the remaining 2.00, and a third
        submission fails CLAIM_ALLOWANCE_EXHAUSTED (capacity, not nominal, rules)."""
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]

        with app.app_context():
            entitlement_id = str(uuid4())
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="econ-clamp"):
                _add_granted(
                    classroom, student, entitlement_id,
                    premium="10.00", payout_multiple="1",
                    reimbursement_percentage="100", claims_per_week_equivalent="5",
                )
                loss1 = _seed_loss(classroom, student, idem="clamp-1", amount="-8.00").id
                loss2 = _seed_loss(classroom, student, idem="clamp-2", amount="-8.00").id
                loss3 = _seed_loss(classroom, student, idem="clamp-3", amount="-8.00").id

            student_ctx = _student_ctx(classroom, student)
            teacher_ctx = _teacher_ctx(classroom)

            # Claim 1: full 8.00.
            s1 = submit_insurance_claim(
                canonical_context=student_ctx, entitlement_id=entitlement_id,
                claim_subject={"transaction_id": loss1}, correlation_id=f"corr_{uuid4().hex}",
            )
            assert s1.success is True, s1.error_message
            r1 = resolve_insurance_claim(
                canonical_context=teacher_ctx, claim_id=s1.claim_id, approved=True
            )
            assert r1.success is True, r1.error_message
            assert r1.reimbursement_amount == Decimal("8.00")

            # Claim 2: nominal 8.00 but only 2.00 capacity remains → CLAMPED to 2.00.
            s2 = submit_insurance_claim(
                canonical_context=student_ctx, entitlement_id=entitlement_id,
                claim_subject={"transaction_id": loss2}, correlation_id=f"corr_{uuid4().hex}",
            )
            assert s2.success is True, s2.error_message
            r2 = resolve_insurance_claim(
                canonical_context=teacher_ctx, claim_id=s2.claim_id, approved=True
            )
            assert r2.success is True, r2.error_message
            assert r2.reimbursement_amount == Decimal("2.00")

            # Capacity is now exhausted (8 + 2 == 10). A third submission fails.
            s3 = submit_insurance_claim(
                canonical_context=student_ctx, entitlement_id=entitlement_id,
                claim_subject={"transaction_id": loss3}, correlation_id=f"corr_{uuid4().hex}",
            )
            assert s3.success is False
            assert s3.error_code == "CLAIM_ALLOWANCE_EXHAUSTED"

    def test_rejected_claims_do_not_consume_payout_capacity(self, app):
        """Only APPROVED monetary results consume the payout ceiling."""
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]

        with app.app_context():
            entitlement_id = str(uuid4())
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="econ-reject-nocap"):
                _add_granted(
                    classroom, student, entitlement_id,
                    premium="10.00", payout_multiple="1",
                    reimbursement_percentage="100", claims_per_week_equivalent="5",
                )
                loss1 = _seed_loss(classroom, student, idem="rc-1", amount="-10.00").id
                loss2 = _seed_loss(classroom, student, idem="rc-2", amount="-10.00").id

            student_ctx = _student_ctx(classroom, student)
            teacher_ctx = _teacher_ctx(classroom)

            s1 = submit_insurance_claim(
                canonical_context=student_ctx, entitlement_id=entitlement_id,
                claim_subject={"transaction_id": loss1}, correlation_id=f"corr_{uuid4().hex}",
            )
            assert s1.success is True, s1.error_message
            r1 = resolve_insurance_claim(
                canonical_context=teacher_ctx, claim_id=s1.claim_id, approved=False
            )
            assert r1.success is True and r1.decision == "REJECTED"

            # The rejected claim consumed no capacity, so the full 10.00 pays out.
            s2 = submit_insurance_claim(
                canonical_context=student_ctx, entitlement_id=entitlement_id,
                claim_subject={"transaction_id": loss2}, correlation_id=f"corr_{uuid4().hex}",
            )
            assert s2.success is True, s2.error_message
            r2 = resolve_insurance_claim(
                canonical_context=teacher_ctx, claim_id=s2.claim_id, approved=True
            )
            assert r2.success is True, r2.error_message
            assert r2.reimbursement_amount == Decimal("10.00")


class TestClaimAllowance:
    def test_rejected_claim_counts_and_limit_is_enforced_at_submission(self, app):
        """Allowance = ceil(2 × 1) = 2. A rejected claim still counts; the third
        submission is blocked; and resolving the second claim afterward still
        APPROVES (a later submission never retroactively denies it)."""
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]

        with app.app_context():
            entitlement_id = str(uuid4())
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="econ-allowance"):
                _add_granted(
                    classroom, student, entitlement_id,
                    premium="100.00", payout_multiple="1",
                    reimbursement_percentage="100", claims_per_week_equivalent="2",
                )
                loss1 = _seed_loss(classroom, student, idem="al-1", amount="-5.00").id
                loss2 = _seed_loss(classroom, student, idem="al-2", amount="-5.00").id
                loss3 = _seed_loss(classroom, student, idem="al-3", amount="-5.00").id

            student_ctx = _student_ctx(classroom, student)
            teacher_ctx = _teacher_ctx(classroom)

            # Claim 1 created, then REJECTED — it still consumes one allowance slot.
            s1 = submit_insurance_claim(
                canonical_context=student_ctx, entitlement_id=entitlement_id,
                claim_subject={"transaction_id": loss1}, correlation_id=f"corr_{uuid4().hex}",
            )
            assert s1.success is True, s1.error_message
            rej = resolve_insurance_claim(
                canonical_context=teacher_ctx, claim_id=s1.claim_id, approved=False
            )
            assert rej.success is True and rej.decision == "REJECTED"

            # Claim 2 created — allowance now fully consumed (rejected + this one).
            s2 = submit_insurance_claim(
                canonical_context=student_ctx, entitlement_id=entitlement_id,
                claim_subject={"transaction_id": loss2}, correlation_id=f"corr_{uuid4().hex}",
            )
            assert s2.success is True, s2.error_message

            # Claim 3 is blocked at SUBMISSION by the per-period allowance.
            s3 = submit_insurance_claim(
                canonical_context=student_ctx, entitlement_id=entitlement_id,
                claim_subject={"transaction_id": loss3}, correlation_id=f"corr_{uuid4().hex}",
            )
            assert s3.success is False
            assert s3.error_code == "CLAIM_LIMIT_EXCEEDED"

            # Resolution of claim 2 is NOT retroactively denied by the later attempt.
            r2 = resolve_insurance_claim(
                canonical_context=teacher_ctx, claim_id=s2.claim_id, approved=True
            )
            assert r2.success is True, r2.error_message
            assert r2.decision == "APPROVED"
            assert r2.reimbursement_amount == Decimal("5.00")


class TestClaimWindow:
    def test_transaction_on_last_eligible_day_is_timely(self, app):
        """A transaction whose class-local date is exactly window_days ago (D where
        D + N == today) may still be filed today."""
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]

        with app.app_context():
            now_utc = _now_utc(classroom, student)
            entitlement_id = str(uuid4())
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="econ-window-ok"):
                _add_granted(
                    classroom, student, entitlement_id,
                    claim_window_days=7, claims_per_week_equivalent="5",
                    premium="100.00", payout_multiple="1",
                    granted_at=now_utc - timedelta(days=30),
                )
                loss = _seed_loss(
                    classroom, student, idem="win-ok", amount="-5.00",
                    at=now_utc - timedelta(days=7),
                ).id

            s = submit_insurance_claim(
                canonical_context=_student_ctx(classroom, student),
                entitlement_id=entitlement_id,
                claim_subject={"transaction_id": loss},
                correlation_id=f"corr_{uuid4().hex}",
            )
            assert s.success is True, s.error_message

    def test_transaction_past_window_is_rejected(self, app):
        """One class-local day past the window (D + N < today) is too late."""
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]

        with app.app_context():
            now_utc = _now_utc(classroom, student)
            entitlement_id = str(uuid4())
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="econ-window-late"):
                _add_granted(
                    classroom, student, entitlement_id,
                    claim_window_days=7, claims_per_week_equivalent="5",
                    premium="100.00", payout_multiple="1",
                    granted_at=now_utc - timedelta(days=30),
                )
                loss = _seed_loss(
                    classroom, student, idem="win-late", amount="-5.00",
                    at=now_utc - timedelta(days=8),
                ).id

            s = submit_insurance_claim(
                canonical_context=_student_ctx(classroom, student),
                entitlement_id=entitlement_id,
                claim_subject={"transaction_id": loss},
                correlation_id=f"corr_{uuid4().hex}",
            )
            assert s.success is False
            assert s.error_code == "CLAIM_WINDOW_EXCEEDED"
