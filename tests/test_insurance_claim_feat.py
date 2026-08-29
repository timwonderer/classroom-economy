"""
Tests for FEAT-STOR-003: Insurance Claim Lifecycle

Covers:
- Submission validation, idempotency, eligibility flags
- Resolution (approval/rejection) on the first-class ``InsuranceClaim`` entity
- The insurance entitlement is NEVER consumed by claim activity (no CONSUMED event)
- Terminal claim decisions are immutable; one transaction backs at most one claim
- Frozen-contract snapshot consumption (claim never re-reads current policy)

Uses canonical test initializer per SPEC-TEST-001.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4
from app.extensions import db
from app.feats.base import FEATContext
from app.models import (
    AttendanceSession,
    ClassEconomy,
    ClassFeature,
    EconomicEngine,
    EntitlementEvent,
    InsuranceClaim,
    InsuranceClaimProductivityDate,
    PayrollEvent,
    PayrollSettings,
)
from app.models import PolicyVersion
from app.services.context_resolver import CanonicalContext
from app.services import insurance_claim_service
from app.services.class_configuration_query_service import (
    get_economic_engine_by_version,
    get_effective_economic_engine,
)
from app.utils.canonical_temporal_resolver import (
    CLASS_LEVEL_EVALUATION,
    canonical_temporal_resolver,
)
from app.feats.class_configuration.feat_class_004_feature_enablement import (
    execute_enable_feature,
)
from app.feats.insurance_claim_feat import (
    submit_insurance_claim,
    resolve_insurance_claim,
    build_productivity_review_context,
    _resolve_hourly_pay_rate,
)
from tests.helpers.ledger import create_ledger_idempotent_transaction
from tests.helpers.classroom_initializer import initialize


def _transaction_frozen_contract(
    reimbursement_percentage: str = "100",
    *,
    premium: str = "100.00",
    payout_multiple: str = "1",
    claims_per_week_equivalent: str = "5",
    claim_window_days: int = 7,
) -> dict:
    """A lawful TRANSACTION frozen_contract subset (must match insurance_contract_freeze).

    Defaults give a meaningful period payout ceiling (premium × payout_multiple =
    100.00) and a generous per-period claim allowance (5) so the general lifecycle
    fixtures are never incidentally throttled by the economic gates. Regression
    tests that exercise a gate pass explicit tight values.
    """
    return {
        "insurance_type": "TRANSACTION",
        "premium": premium,
        "charge_frequency": "WEEKLY",
        "reimbursement_percentage": str(reimbursement_percentage),
        "payout_multiple": payout_multiple,
        "claims_per_week_equivalent": claims_per_week_equivalent,
        "claim_window_days": claim_window_days,
    }


def granted_insurance_payload(
    policy_uuid: str, reimbursement_percentage: str = "100", **contract_kwargs
) -> dict:
    """GRANTED-event payload carrying the frozen snapshot the claim path consumes."""
    return {
        "insurance_policy_uuid": policy_uuid,
        "frozen_contract": _transaction_frozen_contract(
            reimbursement_percentage, **contract_kwargs
        ),
        "purchase_metadata": {"tier_level": 1, "tier_name": "Basic", "title": "Insurance Policy"},
    }


def make_policy_uuid(suffix: str = "") -> str:
    """A synthetic provenance UUID; the claim path never resolves it back to the store."""
    return f"pol-{suffix}-{uuid4().hex}" if suffix else f"pol-{uuid4().hex}"


def _add_granted_event(
    classroom, student, entitlement_id, policy_uuid, reimbursement_percentage="100", **contract_kwargs
):
    """Insert a GRANTED INSURANCE event with a frozen snapshot (caller inside FEATContext)."""
    granted_event = EntitlementEvent(
        event_id=str(uuid4()),
        class_id=classroom.class_id,
        entitlement_id=entitlement_id,
        target_seat_id=student.seat.id,
        actor_seat_id=student.seat.id,
        product_id=1,
        entitlement_type="INSURANCE",
        acquisition_type="PERK",
        event_type="GRANTED",
        payload=granted_insurance_payload(
            policy_uuid, reimbursement_percentage, **contract_kwargs
        ),
    )
    db.session.add(granted_event)
    db.session.flush()
    return granted_event


def _seed_source_loss(classroom, student, *, idem, amount=Decimal("-10.00")):
    """Create a negative (loss) source transaction eligible to back a TRANSACTION claim.

    Losses are stored negative from the covered seat's perspective (the system-law
    eligibility contract requires a negative amount). Caller must be inside a FEAT
    context. Returns the persisted ``Transaction``.
    """
    source_transaction, _created = create_ledger_idempotent_transaction(
        idempotency_key=f"insurance-source-loss:{idem}",
        seat_id=student.seat.id,
        class_id=classroom.class_id,
        user_id=student.user.id,
        amount=amount,
        account_type="checking",
        type="purchase",
        description="Insurance claim source loss",
        actor_seat_id=student.seat.id,
    )
    return source_transaction


def _terminal_events(class_id, entitlement_id):
    """All terminal (CONSUMED/EXPIRED/REVOKED) events on an entitlement lineage."""
    return (
        db.session.query(EntitlementEvent)
        .filter(
            EntitlementEvent.class_id == class_id,
            EntitlementEvent.entitlement_id == entitlement_id,
            EntitlementEvent.event_type.in_(["CONSUMED", "EXPIRED", "REVOKED"]),
        )
        .all()
    )


class TestInsuranceClaimSubmission:
    """Tests for FEAT-STOR-003-SUBMIT"""

    def test_valid_submission_creates_claim(self, app):
        """Valid submission creates a SUBMITTED InsuranceClaim; entitlement stays GRANTED."""
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]
        policy_uuid = make_policy_uuid("valid-submission")

        with app.app_context():
            entitlement_id = str(uuid4())
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="insurance-claim:valid-submission"):
                _add_granted_event(classroom, student, entitlement_id, policy_uuid)
                source = _seed_source_loss(classroom, student, idem="valid-submission")
                source_txn_id = source.id

            context = CanonicalContext(
                user_id=student.user.id,
                class_id=classroom.class_id,
                seat_id=student.seat.id,
                actor_role="student",
            )

            claim_subject = {"transaction_id": source_txn_id}
            result = submit_insurance_claim(
                canonical_context=context,
                entitlement_id=entitlement_id,
                claim_subject=claim_subject,
            )

            assert result.success is True, result.error_message
            assert result.claim_id is not None
            assert result.correlation_id is not None
            assert result.submitted_at is not None

            claim = db.session.query(InsuranceClaim).filter_by(
                claim_id=result.claim_id
            ).first()
            assert claim is not None
            assert claim.class_id == classroom.class_id
            assert claim.target_seat_id == student.seat.id
            assert claim.entitlement_id == entitlement_id
            assert claim.status == "SUBMITTED"
            assert claim.claim_basis == claim_subject

            # The entitlement is NOT consumed by submission.
            assert _terminal_events(classroom.class_id, entitlement_id) == []

    def test_submission_rejects_nonexistent_entitlement(self, app):
        """Submission fails if entitlement doesn't exist."""
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]

        with app.app_context():
            context = CanonicalContext(
                user_id=student.user.id,
                class_id=classroom.class_id,
                seat_id=student.seat.id,
                actor_role="student",
            )

            result = submit_insurance_claim(
                canonical_context=context,
                entitlement_id=str(uuid4()),  # Non-existent
                claim_subject={"transaction_id": 123},
            )

            assert result.success is False
            assert result.error_code == "ENTITLEMENT_NOT_FOUND"

    def test_submission_rejects_wrong_entitlement_type(self, app):
        """Submission fails if entitlement is not INSURANCE type."""
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]

        with app.app_context():
            entitlement_id = str(uuid4())
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="insurance-claim:wrong-type"):
                granted_event = EntitlementEvent(
                    event_id=str(uuid4()),
                    class_id=classroom.class_id,
                    entitlement_id=entitlement_id,
                    target_seat_id=student.seat.id,
                    actor_seat_id=student.seat.id,
                    product_id=1,
                    entitlement_type="DELAYED_USE",  # Wrong type
                    acquisition_type="PERK",
                    event_type="GRANTED",
                    payload={"policy_uuid": "policy-001"},
                )
                db.session.add(granted_event)
                db.session.flush()

            context = CanonicalContext(
                user_id=student.user.id,
                class_id=classroom.class_id,
                seat_id=student.seat.id,
                actor_role="student",
            )

            result = submit_insurance_claim(
                canonical_context=context,
                entitlement_id=entitlement_id,
                claim_subject={"transaction_id": 123},
            )

            assert result.success is False
            assert result.error_code == "WRONG_ENTITLEMENT_TYPE"

    def test_submission_rejects_terminal_entitlement(self, app):
        """Submission fails if entitlement already has a terminal event."""
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]
        policy_uuid = make_policy_uuid("terminal-entitlement")

        with app.app_context():
            entitlement_id = str(uuid4())
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="insurance-claim:terminal-entitlement"):
                _add_granted_event(classroom, student, entitlement_id, policy_uuid)
                consumed_event = EntitlementEvent(
                    event_id=str(uuid4()),
                    class_id=classroom.class_id,
                    entitlement_id=entitlement_id,
                    target_seat_id=student.seat.id,
                    actor_seat_id=student.seat.id,
                    product_id=1,
                    entitlement_type="INSURANCE",
                    acquisition_type="PERK",
                    event_type="REVOKED",
                    payload={"reason": "coverage boundary"},
                )
                db.session.add(consumed_event)
                db.session.flush()

            context = CanonicalContext(
                user_id=student.user.id,
                class_id=classroom.class_id,
                seat_id=student.seat.id,
                actor_role="student",
            )

            result = submit_insurance_claim(
                canonical_context=context,
                entitlement_id=entitlement_id,
                claim_subject={"transaction_id": 123},
            )

            assert result.success is False
            assert result.error_code == "ENTITLEMENT_TERMINAL"

    def test_submission_idempotency(self, app):
        """Retrying submission with same correlation_id returns the prior claim."""
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]
        policy_uuid = make_policy_uuid("idempotency")

        with app.app_context():
            entitlement_id = str(uuid4())
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="insurance-claim:idempotency"):
                _add_granted_event(classroom, student, entitlement_id, policy_uuid)
                source = _seed_source_loss(classroom, student, idem="idempotency")
                source_txn_id = source.id

            context = CanonicalContext(
                user_id=student.user.id,
                class_id=classroom.class_id,
                seat_id=student.seat.id,
                actor_role="student",
            )

            correlation_id = f"corr_{uuid4().hex}"

            result1 = submit_insurance_claim(
                canonical_context=context,
                entitlement_id=entitlement_id,
                claim_subject={"transaction_id": source_txn_id},
                correlation_id=correlation_id,
            )
            result2 = submit_insurance_claim(
                canonical_context=context,
                entitlement_id=entitlement_id,
                claim_subject={"transaction_id": source_txn_id},
                correlation_id=correlation_id,
            )

            assert result2.success is True
            assert result2.claim_id == result1.claim_id
            assert result2.correlation_id == result1.correlation_id

            # Exactly one claim row exists for this correlation.
            claims = db.session.query(InsuranceClaim).filter_by(
                correlation_id=correlation_id
            ).all()
            assert len(claims) == 1

    def test_submission_rejects_duplicate_transaction_subject(self, app):
        """One transaction may back at most one claim lifecycle."""
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]
        policy_uuid = make_policy_uuid("dup-subject")

        with app.app_context():
            entitlement_id = str(uuid4())
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="insurance-claim:dup-subject"):
                _add_granted_event(classroom, student, entitlement_id, policy_uuid)
                source = _seed_source_loss(classroom, student, idem="dup-subject")
                source_txn_id = source.id

            context = CanonicalContext(
                user_id=student.user.id,
                class_id=classroom.class_id,
                seat_id=student.seat.id,
                actor_role="student",
            )

            first = submit_insurance_claim(
                canonical_context=context,
                entitlement_id=entitlement_id,
                claim_subject={"transaction_id": source_txn_id},
                correlation_id=f"corr_{uuid4().hex}",
            )
            assert first.success is True

            # A DIFFERENT correlation against the SAME transaction is a duplicate subject.
            dup = submit_insurance_claim(
                canonical_context=context,
                entitlement_id=entitlement_id,
                claim_subject={"transaction_id": source_txn_id},
                correlation_id=f"corr_{uuid4().hex}",
            )
            assert dup.success is False
            assert dup.error_code == "DUPLICATE_CLAIM_SUBJECT"

    def test_multiple_claims_allowed_under_one_active_policy(self, app):
        """Distinct transactions may each back a claim while the entitlement stays active."""
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]
        policy_uuid = make_policy_uuid("multi-claim")

        with app.app_context():
            entitlement_id = str(uuid4())
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="insurance-claim:multi-claim"):
                _add_granted_event(classroom, student, entitlement_id, policy_uuid)
                source1 = _seed_source_loss(classroom, student, idem="multi-claim-1")
                source2 = _seed_source_loss(classroom, student, idem="multi-claim-2")
                source1_id, source2_id = source1.id, source2.id

            context = CanonicalContext(
                user_id=student.user.id,
                class_id=classroom.class_id,
                seat_id=student.seat.id,
                actor_role="student",
            )

            r1 = submit_insurance_claim(
                canonical_context=context,
                entitlement_id=entitlement_id,
                claim_subject={"transaction_id": source1_id},
                correlation_id=f"corr_{uuid4().hex}",
            )
            r2 = submit_insurance_claim(
                canonical_context=context,
                entitlement_id=entitlement_id,
                claim_subject={"transaction_id": source2_id},
                correlation_id=f"corr_{uuid4().hex}",
            )

            assert r1.success is True
            assert r2.success is True
            assert r1.claim_id != r2.claim_id
            assert _terminal_events(classroom.class_id, entitlement_id) == []


class TestInsuranceClaimResolution:
    """Tests for FEAT-STOR-003-RESOLVE on the InsuranceClaim lifecycle."""

    def _seed_granted_source_and_claim(
        self, app, classroom, student, *, idem, loss=Decimal("-12.34"), reimbursement_percentage="100"
    ):
        """Seed a GRANTED event, a source loss transaction, and a SUBMITTED claim.

        The source transaction is a negative (loss) amount, as required by the
        system-law eligibility contract. Returns
        (entitlement_id, claim_id, source_transaction_id).
        """
        entitlement_id = str(uuid4())
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"insurance-claim:{idem}"):
            _add_granted_event(
                classroom, student, entitlement_id, make_policy_uuid(idem), reimbursement_percentage
            )

            source_transaction, created = create_ledger_idempotent_transaction(
                idempotency_key=f"insurance-source:{idem}",
                seat_id=student.seat.id,
                class_id=classroom.class_id,
                user_id=student.user.id,
                amount=loss,
                account_type="checking",
                type="purchase",
                description="Insurance claim source transaction",
                actor_seat_id=student.seat.id,
            )
            assert created is True

            claim = insurance_claim_service.create_claim(
                class_id=classroom.class_id,
                entitlement_id=entitlement_id,
                target_seat_id=student.seat.id,
                actor_seat_id=student.seat.id,
                correlation_id=f"corr_{idem}_{uuid4().hex}",
                claim_basis={"transaction_id": source_transaction.id},
            )
        return entitlement_id, claim.claim_id, source_transaction.id

    def test_approval_decides_claim_no_consumed_event(self, app):
        """Approval → APPROVED claim + one Ledger effect, NO CONSUMED event, entitlement stays active."""
        classroom = initialize("chemistry_p1", app)
        teacher = classroom.teacher_seat
        student = classroom.students[0]

        with app.app_context():
            entitlement_id, claim_id, source_txn_id = self._seed_granted_source_and_claim(
                app, classroom, student, idem="approval"
            )

            teacher_context = CanonicalContext(
                user_id=teacher.user_id,
                class_id=classroom.class_id,
                seat_id=teacher.id,
                actor_role="teacher",
            )

            result = resolve_insurance_claim(
                canonical_context=teacher_context,
                claim_id=claim_id,
                approved=True,
            )

            assert result.success is True, result.error_message
            assert result.decision == "APPROVED"
            assert result.claim_id == claim_id
            assert result.reimbursement_amount == Decimal("12.34")
            assert result.ledger_transaction_id is not None

            claim = db.session.query(InsuranceClaim).filter_by(claim_id=claim_id).first()
            assert claim.status == "APPROVED"
            assert claim.result_amount == Decimal("12.34")
            assert claim.ledger_transaction_id == result.ledger_transaction_id
            assert claim.decided_by_seat_id == teacher.id

            # The insurance entitlement is NEVER consumed by a claim decision.
            assert _terminal_events(classroom.class_id, entitlement_id) == []

    def test_rejection_decides_claim_no_ledger_no_consumed(self, app):
        """Rejection → REJECTED claim, no Ledger effect, NO CONSUMED event, entitlement stays active."""
        classroom = initialize("chemistry_p1", app)
        teacher = classroom.teacher_seat
        student = classroom.students[0]

        with app.app_context():
            entitlement_id, claim_id, _ = self._seed_granted_source_and_claim(
                app, classroom, student, idem="rejection"
            )

            teacher_context = CanonicalContext(
                user_id=teacher.user_id,
                class_id=classroom.class_id,
                seat_id=teacher.id,
                actor_role="teacher",
            )

            result = resolve_insurance_claim(
                canonical_context=teacher_context,
                claim_id=claim_id,
                approved=False,
                override_reason="Ineligible claim",
            )

            assert result.success is True, result.error_message
            assert result.decision == "REJECTED"
            assert result.reimbursement_amount is None
            assert result.ledger_transaction_id is None

            claim = db.session.query(InsuranceClaim).filter_by(claim_id=claim_id).first()
            assert claim.status == "REJECTED"
            assert claim.decision_note == "Ineligible claim"
            assert claim.result_amount is None
            assert claim.ledger_transaction_id is None

            # The insurance entitlement is NEVER consumed by a claim decision.
            assert _terminal_events(classroom.class_id, entitlement_id) == []

    def test_terminal_decision_is_immutable(self, app):
        """A decided claim cannot be re-decided (terminal states are immutable)."""
        classroom = initialize("chemistry_p1", app)
        teacher = classroom.teacher_seat
        student = classroom.students[0]

        with app.app_context():
            _, claim_id, _ = self._seed_granted_source_and_claim(
                app, classroom, student, idem="immutable"
            )

            teacher_context = CanonicalContext(
                user_id=teacher.user_id,
                class_id=classroom.class_id,
                seat_id=teacher.id,
                actor_role="teacher",
            )

            first = resolve_insurance_claim(
                canonical_context=teacher_context,
                claim_id=claim_id,
                approved=True,
            )
            assert first.success is True

            second = resolve_insurance_claim(
                canonical_context=teacher_context,
                claim_id=claim_id,
                approved=False,
            )
            assert second.success is False
            assert second.error_code == "ALREADY_DECIDED"

            # The original decision stands.
            claim = db.session.query(InsuranceClaim).filter_by(claim_id=claim_id).first()
            assert claim.status == "APPROVED"

    def test_resolution_requires_teacher_role(self, app):
        """Only teachers can resolve insurance claims."""
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]

        with app.app_context():
            _, claim_id, _ = self._seed_granted_source_and_claim(
                app, classroom, student, idem="authz"
            )

            student_context = CanonicalContext(
                user_id=student.user.id,
                class_id=classroom.class_id,
                seat_id=student.seat.id,
                actor_role="student",  # Not teacher
            )

            result = resolve_insurance_claim(
                canonical_context=student_context,
                claim_id=claim_id,
                approved=True,
            )

            assert result.success is False
            assert result.error_code == "UNAUTHORIZED"

    def test_resolution_rejects_nonexistent_claim(self, app):
        """Resolution fails if the claim doesn't exist."""
        classroom = initialize("chemistry_p1", app)
        teacher = classroom.teacher_seat

        with app.app_context():
            teacher_context = CanonicalContext(
                user_id=teacher.user_id,
                class_id=classroom.class_id,
                seat_id=teacher.id,
                actor_role="teacher",
            )

            result = resolve_insurance_claim(
                canonical_context=teacher_context,
                claim_id=str(uuid4()),  # Non-existent
                approved=True,
            )

            assert result.success is False
            assert result.error_code == "CLAIM_NOT_FOUND"


def _productivity_frozen_contract(
    *,
    reimbursement_percentage: str = "100",
    premium: str = "100.00",
    payout_multiple: str = "1",
    claimable_dates_per_week_equivalent: str = "5",
) -> dict:
    """A lawful PRODUCTIVITY frozen_contract subset.

    The PRODUCTIVITY subset intentionally omits ``claim_window_days`` (no filing
    window) and ``claims_per_week_equivalent`` (the metered unit is the DATE, gated
    by ``claimable_dates_per_week_equivalent``).
    """
    return {
        "insurance_type": "PRODUCTIVITY",
        "premium": premium,
        "charge_frequency": "WEEKLY",
        "reimbursement_percentage": reimbursement_percentage,
        "payout_multiple": payout_multiple,
        "claimable_dates_per_week_equivalent": claimable_dates_per_week_equivalent,
    }


_ENGINE_CARRY_FORWARD_FIELDS = (
    "economy_policy_mode",
    "expected_weekly_hours",
    "interest_rate",
    "interest_calculation_type",
    "compound_frequency",
    "interest_accrual_frequency",
    "interest_payout_frequency",
    "flat_overdraft_fee",
    "progressive_overdraft_fee",
    "overdraft_protection_enabled",
)


def _make_economic_engine_ready(class_id: str, *, expected_weekly_hours: str = "40") -> None:
    """Give the effective payroll engine an expected_weekly_hours so the base resolves READY.

    The default provisioned classroom leaves ``expected_weekly_hours`` NULL, which keeps
    the Economic Engine NOT_READY and blocks CWI-dependent PRODUCTIVITY claims. Seeding a
    value here reflects the lawful precondition for a PRODUCTIVITY claim.

    EconomicEngine versions are immutable, so we mint a new version carrying every field
    forward with expected_weekly_hours set, then link the payroll feature to it via a
    later-effective ClassFeature row (INSERT-only; matches the canonical evolution shape).
    Caller must already be inside a FEAT context.
    """
    current = get_effective_economic_engine(class_id, "payroll")
    if current is not None and current.expected_weekly_hours is not None:
        return

    carried = {name: getattr(current, name) for name in _ENGINE_CARRY_FORWARD_FIELDS}
    carried["expected_weekly_hours"] = float(Decimal(str(expected_weekly_hours)))

    new_engine_id = str(uuid4())
    new_engine = EconomicEngine(
        economic_version_id=new_engine_id,
        class_id=class_id,
        previous_version_id=current.economic_version_id,
        **carried,
    )
    db.session.add(new_engine)
    db.session.flush()

    existing_payroll_feature = (
        ClassFeature.query.filter(
            ClassFeature.class_id == class_id,
            ClassFeature.feature == "payroll",
            ClassFeature.economic_version_id.isnot(None),
        )
        .order_by(ClassFeature.effective_at.desc())
        .first()
    )
    effective_at = existing_payroll_feature.effective_at + timedelta(microseconds=1)
    db.session.add(
        ClassFeature(
            class_id=class_id,
            feature="payroll",
            effective_at=effective_at,
            economic_version_id=new_engine_id,
        )
    )
    db.session.flush()


def _add_productivity_granted_event(
    classroom,
    student,
    entitlement_id,
    policy_uuid,
    *,
    granted_at: datetime | None = None,
    expected_weekly_hours: str | None = "40",
    **contract_kwargs,
):
    """Insert a GRANTED INSURANCE event carrying a PRODUCTIVITY frozen snapshot.

    ``granted_at`` backdates the coverage start so multiple past class-local dates
    fall inside coverage. ``expected_weekly_hours`` makes the Economic Engine READY by
    default; pass ``None`` to leave it unready (execution-gate containment tests).
    Caller must be inside a FEAT context.
    """
    if expected_weekly_hours is not None:
        _make_economic_engine_ready(
            classroom.class_id, expected_weekly_hours=expected_weekly_hours
        )
    granted_event = EntitlementEvent(
        event_id=str(uuid4()),
        class_id=classroom.class_id,
        entitlement_id=entitlement_id,
        target_seat_id=student.seat.id,
        actor_seat_id=student.seat.id,
        product_id=1,
        entitlement_type="INSURANCE",
        acquisition_type="PERK",
        event_type="GRANTED",
        payload={
            "insurance_policy_uuid": policy_uuid,
            "frozen_contract": _productivity_frozen_contract(**contract_kwargs),
            "purchase_metadata": {
                "tier_level": 1,
                "tier_name": "Basic",
                "title": "Productivity Insurance",
            },
        },
    )
    if granted_at is not None:
        granted_event.timestamp = granted_at
    db.session.add(granted_event)
    db.session.flush()
    return granted_event


def _seed_active_payroll_policy(class_id: str) -> PolicyVersion:
    """An active payroll PolicyVersion so PRODUCTIVITY approval can post MANUAL_CREDIT."""
    policy = PolicyVersion(
        class_id=class_id,
        domain="payroll",
        version_number=1,
        policy_payload_json='{"source":"test"}',
        activated_at=datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc),
        is_active=True,
    )
    db.session.add(policy)
    db.session.flush()
    return policy


class TestProductivityClaimLifecycle:
    """FEAT-STOR-003 PRODUCTIVITY: normalized asserted-date child rows."""

    def _student_context(self, classroom, student) -> CanonicalContext:
        return CanonicalContext(
            user_id=student.user.id,
            class_id=classroom.class_id,
            seat_id=student.seat.id,
            actor_role="student",
        )

    def _teacher_context(self, classroom) -> CanonicalContext:
        teacher = classroom.teacher_seat
        return CanonicalContext(
            user_id=teacher.user_id,
            class_id=classroom.class_id,
            seat_id=teacher.id,
            actor_role="teacher",
        )

    def test_submission_creates_immutable_date_rows(self, app):
        """Each asserted date becomes its own child row with immutable submitted hours."""
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]

        with app.app_context():
            entitlement_id = str(uuid4())
            granted_at = datetime.now(timezone.utc) - timedelta(days=30)
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="prod:create-rows"):
                _add_productivity_granted_event(
                    classroom, student, entitlement_id,
                    make_policy_uuid("prod-create"), granted_at=granted_at,
                )

            d1 = (datetime.now(timezone.utc) - timedelta(days=3)).date()
            d2 = (datetime.now(timezone.utc) - timedelta(days=2)).date()
            result = submit_insurance_claim(
                canonical_context=self._student_context(classroom, student),
                entitlement_id=entitlement_id,
                claim_subject={
                    "claimed_dates": [
                        {"date": d2.isoformat(), "hours": "1.0", "explanation": "documented loss"},
                        {"date": d1.isoformat(), "hours": "2.0", "explanation": "documented loss"},
                    ]
                },
            )

            assert result.success is True, result.error_message
            claim = db.session.query(InsuranceClaim).filter_by(
                claim_id=result.claim_id
            ).first()
            assert claim.status == "SUBMITTED"

            rows = insurance_claim_service.list_productivity_dates_for_claim(
                claim.claim_id, class_id=classroom.class_id
            )
            assert [r.claim_date for r in rows] == [d1, d2]  # ascending
            assert rows[0].student_claimed_hours == Decimal("2.00")
            assert rows[1].student_claimed_hours == Decimal("1.00")
            # Not yet adjudicated: no approved hours, no recognized payout.
            assert all(r.teacher_approved_hours is None for r in rows)
            assert all(r.recognized_payout is None for r in rows)
            assert all(r.entitlement_id == entitlement_id for r in rows)

    def test_submission_rejects_future_date(self, app):
        """A class-local future date is not an eligible asserted loss."""
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]

        with app.app_context():
            entitlement_id = str(uuid4())
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="prod:future"):
                _add_productivity_granted_event(
                    classroom, student, entitlement_id, make_policy_uuid("prod-future"),
                )

            future = (datetime.now(timezone.utc) + timedelta(days=2)).date()
            result = submit_insurance_claim(
                canonical_context=self._student_context(classroom, student),
                entitlement_id=entitlement_id,
                claim_subject={"claimed_dates": [{"date": future.isoformat(), "hours": "1", "explanation": "documented loss"}]},
            )
            assert result.success is False
            assert result.error_code == "PRODUCTIVITY_DATE_NOT_ELIGIBLE"

    def test_submission_rejects_empty_dates(self, app):
        """PRODUCTIVITY requires a non-empty claimed_dates list."""
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]

        with app.app_context():
            entitlement_id = str(uuid4())
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="prod:empty"):
                _add_productivity_granted_event(
                    classroom, student, entitlement_id, make_policy_uuid("prod-empty"),
                )

            result = submit_insurance_claim(
                canonical_context=self._student_context(classroom, student),
                entitlement_id=entitlement_id,
                claim_subject={"claimed_dates": []},
            )
            assert result.success is False
            assert result.error_code == "INVALID_CLAIM_BASIS"

    def test_submission_rejects_duplicate_date_in_submission(self, app):
        """A date may not appear twice within one submission."""
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]

        with app.app_context():
            entitlement_id = str(uuid4())
            granted_at = datetime.now(timezone.utc) - timedelta(days=10)
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="prod:dup"):
                _add_productivity_granted_event(
                    classroom, student, entitlement_id,
                    make_policy_uuid("prod-dup"), granted_at=granted_at,
                )

            d1 = (datetime.now(timezone.utc) - timedelta(days=2)).date()
            result = submit_insurance_claim(
                canonical_context=self._student_context(classroom, student),
                entitlement_id=entitlement_id,
                claim_subject={
                    "claimed_dates": [
                        {"date": d1.isoformat(), "hours": "1", "explanation": "documented loss"},
                        {"date": d1.isoformat(), "hours": "2", "explanation": "documented loss"},
                    ]
                },
            )
            assert result.success is False
            assert result.error_code == "INVALID_CLAIM_BASIS"

    def test_date_allowance_exhausted(self, app):
        """Distinct-date count over the period allowance fails the submission."""
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]

        with app.app_context():
            entitlement_id = str(uuid4())
            granted_at = datetime.now(timezone.utc) - timedelta(days=10)
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="prod:allowance"):
                _add_productivity_granted_event(
                    classroom, student, entitlement_id, make_policy_uuid("prod-allow"),
                    granted_at=granted_at,
                    claimable_dates_per_week_equivalent="1",  # WEEKLY → allowance 1
                )

            d1 = (datetime.now(timezone.utc) - timedelta(days=3)).date()
            d2 = (datetime.now(timezone.utc) - timedelta(days=2)).date()
            result = submit_insurance_claim(
                canonical_context=self._student_context(classroom, student),
                entitlement_id=entitlement_id,
                claim_subject={
                    "claimed_dates": [
                        {"date": d1.isoformat(), "hours": "1", "explanation": "documented loss"},
                        {"date": d2.isoformat(), "hours": "1", "explanation": "documented loss"},
                    ]
                },
            )
            assert result.success is False
            assert result.error_code == "CLAIM_ALLOWANCE_EXHAUSTED"

    def test_cross_claim_date_reuse_rejected(self, app):
        """A date settled under one claim cannot be re-asserted by another (rejection does not free it)."""
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]

        with app.app_context():
            entitlement_id = str(uuid4())
            granted_at = datetime.now(timezone.utc) - timedelta(days=10)
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="prod:reuse"):
                _add_productivity_granted_event(
                    classroom, student, entitlement_id, make_policy_uuid("prod-reuse"),
                    granted_at=granted_at,
                )

            d1 = (datetime.now(timezone.utc) - timedelta(days=2)).date()
            ctx = self._student_context(classroom, student)
            first = submit_insurance_claim(
                canonical_context=ctx,
                entitlement_id=entitlement_id,
                claim_subject={"claimed_dates": [{"date": d1.isoformat(), "hours": "1", "explanation": "documented loss"}]},
            )
            assert first.success is True, first.error_message

            second = submit_insurance_claim(
                canonical_context=ctx,
                entitlement_id=entitlement_id,
                claim_subject={"claimed_dates": [{"date": d1.isoformat(), "hours": "1", "explanation": "documented loss"}]},
                correlation_id=f"corr_{uuid4().hex}",  # distinct case
            )
            assert second.success is False
            assert second.error_code == "PRODUCTIVITY_DATE_NOT_ELIGIBLE"

    def test_approval_persists_recognized_payout_and_credits(self, app):
        """Approval adjudicates each date, persists recognized_payout, posts ONE credit."""
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]

        with app.app_context():
            entitlement_id = str(uuid4())
            granted_at = datetime.now(timezone.utc) - timedelta(days=10)
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="prod:approve"):
                _add_productivity_granted_event(
                    classroom, student, entitlement_id, make_policy_uuid("prod-approve"),
                    granted_at=granted_at,
                )
                _seed_active_payroll_policy(classroom.class_id)

            hourly = _resolve_hourly_pay_rate(classroom.class_id)

            d1 = (datetime.now(timezone.utc) - timedelta(days=3)).date()
            d2 = (datetime.now(timezone.utc) - timedelta(days=2)).date()
            submit = submit_insurance_claim(
                canonical_context=self._student_context(classroom, student),
                entitlement_id=entitlement_id,
                claim_subject={
                    "claimed_dates": [
                        {"date": d1.isoformat(), "hours": "2", "explanation": "documented loss"},
                        {"date": d2.isoformat(), "hours": "1", "explanation": "documented loss"},
                    ]
                },
            )
            assert submit.success is True, submit.error_message
            claim_id = submit.claim_id

            expected = (hourly * Decimal("2") + hourly * Decimal("1")).quantize(Decimal("0.01"))
            result = resolve_insurance_claim(
                canonical_context=self._teacher_context(classroom),
                claim_id=claim_id,
                approved=True,
            )
            assert result.success is True, result.error_message
            assert result.decision == "APPROVED"
            assert result.reimbursement_amount == expected
            assert result.ledger_transaction_id is None  # payout flows through payroll

            claim = db.session.query(InsuranceClaim).filter_by(claim_id=claim_id).first()
            assert claim.status == "APPROVED"
            assert claim.result_amount == expected

            rows = insurance_claim_service.list_productivity_dates_for_claim(
                claim_id, class_id=classroom.class_id
            )
            assert rows[0].teacher_approved_hours == Decimal("2.00")
            assert rows[0].recognized_payout == (hourly * Decimal("2")).quantize(Decimal("0.01"))
            assert rows[1].recognized_payout == (hourly * Decimal("1")).quantize(Decimal("0.01"))

    def test_approval_with_per_date_adjustment_requires_note(self, app):
        """Lowering a date's hours requires that date's own adjustment note."""
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]

        with app.app_context():
            entitlement_id = str(uuid4())
            granted_at = datetime.now(timezone.utc) - timedelta(days=10)
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="prod:adjust"):
                _add_productivity_granted_event(
                    classroom, student, entitlement_id, make_policy_uuid("prod-adjust"),
                    granted_at=granted_at,
                )
                _seed_active_payroll_policy(classroom.class_id)

            hourly = _resolve_hourly_pay_rate(classroom.class_id)
            d1 = (datetime.now(timezone.utc) - timedelta(days=2)).date()
            submit = submit_insurance_claim(
                canonical_context=self._student_context(classroom, student),
                entitlement_id=entitlement_id,
                claim_subject={"claimed_dates": [{"date": d1.isoformat(), "hours": "2", "explanation": "documented loss"}]},
            )
            assert submit.success is True, submit.error_message
            claim_id = submit.claim_id

            # Missing note on an adjusted date fails.
            missing_note = resolve_insurance_claim(
                canonical_context=self._teacher_context(classroom),
                claim_id=claim_id,
                approved=True,
                date_adjustments={d1.isoformat(): {"hours": "1"}},
            )
            assert missing_note.success is False
            assert missing_note.error_code == "ADJUSTMENT_NOTE_REQUIRED"

            claim = db.session.query(InsuranceClaim).filter_by(claim_id=claim_id).first()
            assert claim.status == "SUBMITTED"  # still open after failed adjudication

            # With a note the adjustment is lawful; student hours stay immutable.
            adjusted = resolve_insurance_claim(
                canonical_context=self._teacher_context(classroom),
                claim_id=claim_id,
                approved=True,
                date_adjustments={
                    d1.isoformat(): {"hours": "1", "note": "Only one hour verified"}
                },
            )
            assert adjusted.success is True, adjusted.error_message
            assert adjusted.reimbursement_amount == (hourly * Decimal("1")).quantize(Decimal("0.01"))

            row = insurance_claim_service.list_productivity_dates_for_claim(
                claim_id, class_id=classroom.class_id
            )[0]
            assert row.student_claimed_hours == Decimal("2.00")  # immutable submitted truth
            assert row.teacher_approved_hours == Decimal("1.00")
            assert row.adjustment_note == "Only one hour verified"

    def test_approval_clamps_to_period_payout_capacity(self, app):
        """recognized_payout is capped by premium × payout_multiple remaining capacity."""
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]

        with app.app_context():
            entitlement_id = str(uuid4())
            granted_at = datetime.now(timezone.utc) - timedelta(days=10)
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="prod:clamp"):
                _add_productivity_granted_event(
                    classroom, student, entitlement_id, make_policy_uuid("prod-clamp"),
                    granted_at=granted_at,
                    premium="10.00",
                    payout_multiple="1",  # cap = $10.00
                )
                _seed_active_payroll_policy(classroom.class_id)

            hourly = _resolve_hourly_pay_rate(classroom.class_id)
            # 2h at the hourly rate exceeds the $10 cap by construction.
            assert hourly * Decimal("2") > Decimal("10.00")

            d1 = (datetime.now(timezone.utc) - timedelta(days=2)).date()
            submit = submit_insurance_claim(
                canonical_context=self._student_context(classroom, student),
                entitlement_id=entitlement_id,
                claim_subject={"claimed_dates": [{"date": d1.isoformat(), "hours": "2", "explanation": "documented loss"}]},
            )
            assert submit.success is True, submit.error_message

            result = resolve_insurance_claim(
                canonical_context=self._teacher_context(classroom),
                claim_id=submit.claim_id,
                approved=True,
            )
            assert result.success is True, result.error_message
            assert result.reimbursement_amount == Decimal("10.00")

            row = insurance_claim_service.list_productivity_dates_for_claim(
                submit.claim_id, class_id=classroom.class_id
            )[0]
            assert row.recognized_payout == Decimal("10.00")


# ---------------------------------------------------------------------------
# Economic Engine readiness (two gates) + PRODUCTIVITY daily/weekly capacity
# ---------------------------------------------------------------------------


def _set_global_daily_limit_hours(class_id: str, hours: float) -> None:
    """Set a simple-mode daily limit on the class-global payroll settings row.

    Caller must be inside a FEAT context. This is the SOLE per-day capacity
    authority PRODUCTIVITY consults via ``get_daily_limit_seconds``.
    """
    row = (
        PayrollSettings.query.filter(
            PayrollSettings.class_id == class_id,
            PayrollSettings.block.is_(None),
            PayrollSettings.is_active.is_(True),
        ).first()
    )
    assert row is not None, "default classroom must have a global payroll settings row"
    row.settings_mode = "simple"
    row.daily_limit_hours = float(hours)
    db.session.flush()


def _seed_worked_interval(classroom, student, *, ctx, evaluation_date, hours: float) -> None:
    """Seed one active→inactive attendance pair worth ``hours`` inside a class-local day.

    Caller must be inside a FEAT context. Timestamps are anchored to the canonical
    evaluation-day boundaries so the worked duration lands inside the target date.
    """
    evaluation = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx,
        primitive="evaluation_day_boundaries",
        evaluation_date=evaluation_date,
    )
    start = evaluation.boundary_start_utc + timedelta(hours=1)
    end = start + timedelta(hours=float(hours))
    common = dict(
        target_seat_id=student.seat.id,
        class_id=classroom.class_id,
        target_user_id=student.user.id,
        actor_seat_id=student.seat.id,
        reason_code="start_work",
    )
    db.session.add(AttendanceSession(status="active", timestamp=start, **common))
    db.session.add(AttendanceSession(status="inactive", timestamp=end, **common))
    db.session.flush()


class TestProductivityReadinessAndCapacity:
    """Economic Engine readiness lifecycle (prevention + containment) and Req 3/5 capacity."""

    def _student_context(self, classroom, student) -> CanonicalContext:
        return CanonicalContext(
            user_id=student.user.id,
            class_id=classroom.class_id,
            seat_id=student.seat.id,
            actor_role="student",
        )

    def _teacher_context(self, classroom) -> CanonicalContext:
        teacher = classroom.teacher_seat
        return CanonicalContext(
            user_id=teacher.user_id,
            class_id=classroom.class_id,
            seat_id=teacher.id,
            actor_role="teacher",
        )

    def _prev_week_dates(self):
        """Three dates in the same Monday-anchored week, safely in the past."""
        today = datetime.now(timezone.utc).date()
        monday = today - timedelta(days=today.weekday() + 7)
        return monday, monday + timedelta(days=1), monday + timedelta(days=2)

    # ---- Gate 1: enablement gate (prevention) ----------------------------

    def test_enablement_gate_blocks_unready_class_enabling_insurance(self, app):
        """A NOT_READY Economic Engine cannot flip insurance disabled→enabled."""
        classroom = initialize("chemistry_p1", app)

        with app.app_context():
            class_id = classroom.class_id
            # Default classroom: insurance disabled, expected_weekly_hours NULL.
            current_engine = get_effective_economic_engine(class_id, "payroll")
            assert current_engine.expected_weekly_hours is None

            blocked = execute_enable_feature(
                canonical_context=self._teacher_context(classroom),
                class_id=class_id,
                feature="insurance",
                economic_version_id=current_engine.economic_version_id,
                idempotency_key=f"enable-insurance-blocked:{uuid4().hex}",
            )
            assert blocked.success is False
            assert blocked.error_code == "ECONOMIC_ENGINE_NOT_READY"

    def test_enablement_gate_permits_insurance_once_engine_ready(self, app):
        """Positive control: a READY engine may enable insurance (gate is not a blanket ban)."""
        classroom = initialize("chemistry_p1", app)

        with app.app_context():
            class_id = classroom.class_id
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="enable-ready:make"):
                _make_economic_engine_ready(class_id)

            ready_engine = get_effective_economic_engine(class_id, "payroll")
            assert ready_engine.expected_weekly_hours is not None

            enabled = execute_enable_feature(
                canonical_context=self._teacher_context(classroom),
                class_id=class_id,
                feature="insurance",
                economic_version_id=ready_engine.economic_version_id,
                idempotency_key=f"enable-insurance-ready:{uuid4().hex}",
            )
            assert enabled.success is True, enabled.error_message

    # ---- Gate 2: execution invariant (containment) -----------------------

    def test_execution_gate_fails_closed_on_unready_engine(self, app):
        """Even if a PRODUCTIVITY claim reaches submission, an unready engine fails closed.

        We construct the impossible-ordinary state deliberately: grant a PRODUCTIVITY
        entitlement directly (bypassing the enablement gate) while the engine stays
        NOT_READY. The submission execution invariant must still refuse.
        """
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]

        with app.app_context():
            entitlement_id = str(uuid4())
            granted_at = datetime.now(timezone.utc) - timedelta(days=30)
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="exec-gate:unready"):
                _add_productivity_granted_event(
                    classroom, student, entitlement_id,
                    make_policy_uuid("exec-unready"),
                    granted_at=granted_at,
                    expected_weekly_hours=None,  # keep the engine NOT_READY
                )

            d1 = (datetime.now(timezone.utc) - timedelta(days=2)).date()
            result = submit_insurance_claim(
                canonical_context=self._student_context(classroom, student),
                entitlement_id=entitlement_id,
                claim_subject={"claimed_dates": [{"date": d1.isoformat(), "hours": "1", "explanation": "documented loss"}]},
            )
            assert result.success is False
            assert result.error_code == "ECONOMIC_ENGINE_NOT_READY"

    def test_gates_are_not_redundant(self, app):
        """The two gates guard different transitions and neither substitutes for the other.

        Prevention lives at feature enablement; containment lives at claim execution.
        Constructing an enabled-but-unready state (grant + NOT_READY) still fails at
        execution — proving the execution gate is load-bearing on its own.
        """
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]

        with app.app_context():
            class_id = classroom.class_id
            # Prevention: enablement refuses while unready.
            engine = get_effective_economic_engine(class_id, "payroll")
            prevented = execute_enable_feature(
                canonical_context=self._teacher_context(classroom),
                class_id=class_id,
                feature="insurance",
                economic_version_id=engine.economic_version_id,
                idempotency_key=f"redundancy-prevent:{uuid4().hex}",
            )
            assert prevented.success is False
            assert prevented.error_code == "ECONOMIC_ENGINE_NOT_READY"

            # Containment: a directly-granted claim on the same unready engine also fails.
            entitlement_id = str(uuid4())
            granted_at = datetime.now(timezone.utc) - timedelta(days=30)
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="redundancy:grant"):
                _add_productivity_granted_event(
                    classroom, student, entitlement_id,
                    make_policy_uuid("redundancy"),
                    granted_at=granted_at,
                    expected_weekly_hours=None,
                )
            d1 = (datetime.now(timezone.utc) - timedelta(days=2)).date()
            contained = submit_insurance_claim(
                canonical_context=self._student_context(classroom, student),
                entitlement_id=entitlement_id,
                claim_subject={"claimed_dates": [{"date": d1.isoformat(), "hours": "1", "explanation": "documented loss"}]},
            )
            assert contained.success is False
            assert contained.error_code == "ECONOMIC_ENGINE_NOT_READY"

    # ---- Req 3: per-date daily capacity ----------------------------------

    def test_daily_capacity_blocks_claim_exceeding_remaining_worked_room(self, app):
        """claimed_seconds may not exceed max(0, daily_cap - actual_worked) for that date."""
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]

        with app.app_context():
            entitlement_id = str(uuid4())
            granted_at = datetime.now(timezone.utc) - timedelta(days=30)
            ctx = self._student_context(classroom, student)
            d_pass = (datetime.now(timezone.utc) - timedelta(days=3)).date()
            d_fail = (datetime.now(timezone.utc) - timedelta(days=2)).date()
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="daily:setup"):
                _add_productivity_granted_event(
                    classroom, student, entitlement_id, make_policy_uuid("daily"),
                    granted_at=granted_at,
                )
                _set_global_daily_limit_hours(classroom.class_id, 4.0)
                # 3h worked on each date → 1h of remaining room.
                _seed_worked_interval(classroom, student, ctx=ctx, evaluation_date=d_pass, hours=3.0)
                _seed_worked_interval(classroom, student, ctx=ctx, evaluation_date=d_fail, hours=3.0)

            # Claiming exactly the remaining 1h is lawful.
            ok = submit_insurance_claim(
                canonical_context=ctx,
                entitlement_id=entitlement_id,
                claim_subject={"claimed_dates": [{"date": d_pass.isoformat(), "hours": "1", "explanation": "documented loss"}]},
            )
            assert ok.success is True, ok.error_message

            # Claiming 2h against 1h of remaining room is refused.
            blocked = submit_insurance_claim(
                canonical_context=ctx,
                entitlement_id=entitlement_id,
                claim_subject={"claimed_dates": [{"date": d_fail.isoformat(), "hours": "2", "explanation": "documented loss"}]},
                correlation_id=f"corr_{uuid4().hex}",
            )
            assert blocked.success is False
            assert blocked.error_code == "PRODUCTIVITY_DAILY_LIMIT_EXCEEDED"

    def test_no_daily_cap_imposes_no_invented_per_day_limit(self, app):
        """With no configured daily cap, PRODUCTIVITY invents none (Req 3 negative)."""
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]

        with app.app_context():
            entitlement_id = str(uuid4())
            granted_at = datetime.now(timezone.utc) - timedelta(days=30)
            ctx = self._student_context(classroom, student)
            d1 = (datetime.now(timezone.utc) - timedelta(days=2)).date()
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="nodaily:setup"):
                _add_productivity_granted_event(
                    classroom, student, entitlement_id, make_policy_uuid("nodaily"),
                    granted_at=granted_at,
                )
                # Large worked block, but NO daily limit configured.
                _seed_worked_interval(classroom, student, ctx=ctx, evaluation_date=d1, hours=6.0)

            # 8h on the day is accepted (only the weekly base cap applies).
            ok = submit_insurance_claim(
                canonical_context=ctx,
                entitlement_id=entitlement_id,
                claim_subject={"claimed_dates": [{"date": d1.isoformat(), "hours": "8", "explanation": "documented loss"}]},
            )
            assert ok.success is True, ok.error_message

    # ---- Weekly guidance is ADVISORY, not a gate -----------------------

    def test_over_guidance_claim_still_submits_and_warns(self, app):
        """Exceeding expected_weekly_hours never blocks a claim; it only warns."""
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]

        with app.app_context():
            entitlement_id = str(uuid4())
            granted_at = datetime.now(timezone.utc) - timedelta(days=30)
            ctx = self._student_context(classroom, student)
            a, _b, _c = self._prev_week_dates()
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="advisory:over"):
                _add_productivity_granted_event(
                    classroom, student, entitlement_id, make_policy_uuid("adv-over"),
                    granted_at=granted_at, expected_weekly_hours="5",
                )

            # 6 claimed hours in one week against 5 expected: submits, but warns.
            over = submit_insurance_claim(
                canonical_context=ctx, entitlement_id=entitlement_id,
                claim_subject={"claimed_dates": [{"date": a.isoformat(), "hours": "6", "explanation": "documented loss"}]},
            )
            assert over.success is True, over.error_message
            flags = over.eligibility_flags or {}
            assert flags.get("weekly_guidance_exceeded") is True
            warnings = flags.get("weekly_guidance_warnings") or []
            assert len(warnings) == 1
            assert warnings[0]["projected_hours"] == "6.00"
            assert warnings[0]["expected_weekly_hours"] == "5.0"

    def test_within_guidance_claim_submits_without_warning(self, app):
        """A claim at or under expected_weekly_hours submits with no warning."""
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]

        with app.app_context():
            entitlement_id = str(uuid4())
            granted_at = datetime.now(timezone.utc) - timedelta(days=30)
            ctx = self._student_context(classroom, student)
            a, _b, _c = self._prev_week_dates()
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="advisory:within"):
                _add_productivity_granted_event(
                    classroom, student, entitlement_id, make_policy_uuid("adv-within"),
                    granted_at=granted_at, expected_weekly_hours="5",
                )

            ok = submit_insurance_claim(
                canonical_context=ctx, entitlement_id=entitlement_id,
                claim_subject={"claimed_dates": [{"date": a.isoformat(), "hours": "4", "explanation": "documented loss"}]},
            )
            assert ok.success is True, ok.error_message
            flags = ok.eligibility_flags or {}
            assert flags.get("weekly_guidance_exceeded") is False
            assert (flags.get("weekly_guidance_warnings") or []) == []

    def test_guidance_aggregates_worked_plus_claimed(self, app):
        """Guidance compares (worked_week + claimed_week) with expected_weekly_hours.

        Worked attendance now contributes to the advisory (the opposite of a limit
        that ignored it): claimed hours alone are under the guidance, but worked +
        claimed together exceed it, so a warning is surfaced without blocking.
        """
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]

        with app.app_context():
            entitlement_id = str(uuid4())
            granted_at = datetime.now(timezone.utc) - timedelta(days=30)
            ctx = self._student_context(classroom, student)
            a, b, _c = self._prev_week_dates()
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="advisory:aggregate"):
                _add_productivity_granted_event(
                    classroom, student, entitlement_id, make_policy_uuid("adv-agg"),
                    granted_at=granted_at, expected_weekly_hours="5",
                )
                # 4h actually worked on day A (same week as the claimed day B).
                _seed_worked_interval(classroom, student, ctx=ctx, evaluation_date=a, hours=4.0)

            # Claimed alone (2h) is under 5, but worked(4) + claimed(2) = 6 > 5.
            claim = submit_insurance_claim(
                canonical_context=ctx, entitlement_id=entitlement_id,
                claim_subject={"claimed_dates": [{"date": b.isoformat(), "hours": "2", "explanation": "documented loss"}]},
            )
            assert claim.success is True, claim.error_message
            flags = claim.eligibility_flags or {}
            assert flags.get("weekly_guidance_exceeded") is True
            warnings = flags.get("weekly_guidance_warnings") or []
            assert len(warnings) == 1
            assert warnings[0]["worked_hours"] == "4.00"
            assert warnings[0]["claimed_hours"] == "2"
            assert warnings[0]["projected_hours"] == "6.00"

    # ---- Evidentiary submission form -----------------------------------

    def test_per_date_explanation_is_required(self, app):
        """Every claimed date requires a non-empty student explanation."""
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]

        with app.app_context():
            entitlement_id = str(uuid4())
            granted_at = datetime.now(timezone.utc) - timedelta(days=30)
            ctx = self._student_context(classroom, student)
            a, _b, _c = self._prev_week_dates()
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="evidence:required"):
                _add_productivity_granted_event(
                    classroom, student, entitlement_id, make_policy_uuid("ev-req"),
                    granted_at=granted_at, expected_weekly_hours="5",
                )

            # Missing explanation.
            missing = submit_insurance_claim(
                canonical_context=ctx, entitlement_id=entitlement_id,
                claim_subject={"claimed_dates": [{"date": a.isoformat(), "hours": "2"}]},
            )
            assert missing.success is False
            assert missing.error_code == "INVALID_CLAIM_BASIS"

            # Blank/whitespace explanation is also rejected.
            blank = submit_insurance_claim(
                canonical_context=ctx, entitlement_id=entitlement_id,
                claim_subject={"claimed_dates": [{"date": a.isoformat(), "hours": "2", "explanation": "   "}]},
                correlation_id=f"corr_{uuid4().hex}",
            )
            assert blank.success is False
            assert blank.error_code == "INVALID_CLAIM_BASIS"

    def test_explanation_and_additional_information_persist_and_surface(self, app):
        """Per-date explanation and claim-wide additional_information are persisted."""
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]

        with app.app_context():
            entitlement_id = str(uuid4())
            granted_at = datetime.now(timezone.utc) - timedelta(days=30)
            ctx = self._student_context(classroom, student)
            a, _b, _c = self._prev_week_dates()
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="evidence:persist"):
                _add_productivity_granted_event(
                    classroom, student, entitlement_id, make_policy_uuid("ev-persist"),
                    granted_at=granted_at, expected_weekly_hours="5",
                )

            submit = submit_insurance_claim(
                canonical_context=ctx, entitlement_id=entitlement_id,
                claim_subject={
                    "claimed_dates": [
                        {"date": a.isoformat(), "hours": "2", "explanation": "laptop crashed mid-task"},
                    ],
                    "additional_information": "IT ticket #4412 filed",
                },
            )
            assert submit.success is True, submit.error_message

            # Persisted per-date evidence is immutable and surfaces to the teacher.
            row = (
                db.session.query(InsuranceClaimProductivityDate)
                .filter_by(claim_id=submit.claim_id, claim_date=a)
                .first()
            )
            assert row is not None
            assert row.student_explanation == "laptop crashed mid-task"

            claim = db.session.query(InsuranceClaim).filter_by(claim_id=submit.claim_id).first()
            review = build_productivity_review_context(claim, canonical_context=ctx)
            assert review.additional_information == "IT ticket #4412 filed"
            assert len(review.dates) == 1
            assert review.dates[0].student_explanation == "laptop crashed mid-task"

    def test_additional_information_must_be_string(self, app):
        """A non-string additional_information is rejected as malformed basis."""
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]

        with app.app_context():
            entitlement_id = str(uuid4())
            granted_at = datetime.now(timezone.utc) - timedelta(days=30)
            ctx = self._student_context(classroom, student)
            a, _b, _c = self._prev_week_dates()
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="evidence:addl-type"):
                _add_productivity_granted_event(
                    classroom, student, entitlement_id, make_policy_uuid("ev-type"),
                    granted_at=granted_at, expected_weekly_hours="5",
                )

            bad = submit_insurance_claim(
                canonical_context=ctx, entitlement_id=entitlement_id,
                claim_subject={
                    "claimed_dates": [{"date": a.isoformat(), "hours": "2", "explanation": "x"}],
                    "additional_information": {"not": "a string"},
                },
            )
            assert bad.success is False
            assert bad.error_code == "INVALID_CLAIM_BASIS"

    # ---- Task 8: teacher adjudication receives actual worked duration ----

    def test_review_context_surfaces_actual_worked_seconds(self, app):
        """build_productivity_review_context reports each date's actual worked seconds."""
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]

        with app.app_context():
            entitlement_id = str(uuid4())
            granted_at = datetime.now(timezone.utc) - timedelta(days=30)
            ctx = self._student_context(classroom, student)
            d1 = (datetime.now(timezone.utc) - timedelta(days=2)).date()
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="review:setup"):
                _add_productivity_granted_event(
                    classroom, student, entitlement_id, make_policy_uuid("review"),
                    granted_at=granted_at,
                )
                _seed_worked_interval(classroom, student, ctx=ctx, evaluation_date=d1, hours=2.0)

            submit = submit_insurance_claim(
                canonical_context=ctx, entitlement_id=entitlement_id,
                claim_subject={"claimed_dates": [{"date": d1.isoformat(), "hours": "1", "explanation": "documented loss"}]},
            )
            assert submit.success is True, submit.error_message

            claim = db.session.query(InsuranceClaim).filter_by(claim_id=submit.claim_id).first()
            review = build_productivity_review_context(claim, canonical_context=ctx)
            assert len(review.dates) == 1
            assert review.dates[0].claim_date == d1
            assert review.dates[0].student_claimed_hours == Decimal("1.00")
            assert review.dates[0].already_worked_seconds == 2 * 3600


class TestProductivityAdjudicationAtomicity:
    """Teacher adjudication semantics: downward-only, note discipline, atomic approval."""

    def _student_context(self, classroom, student) -> CanonicalContext:
        return CanonicalContext(
            user_id=student.user.id,
            class_id=classroom.class_id,
            seat_id=student.seat.id,
            actor_role="student",
        )

    def _teacher_context(self, classroom) -> CanonicalContext:
        teacher = classroom.teacher_seat
        return CanonicalContext(
            user_id=teacher.user_id,
            class_id=classroom.class_id,
            seat_id=teacher.id,
            actor_role="teacher",
        )

    def _submit_single_date(self, classroom, student, *, idem, hours="2"):
        """Grant a ready PRODUCTIVITY entitlement + payroll policy and submit one date."""
        entitlement_id = str(uuid4())
        granted_at = datetime.now(timezone.utc) - timedelta(days=10)
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=idem):
            _add_productivity_granted_event(
                classroom, student, entitlement_id, make_policy_uuid(idem),
                granted_at=granted_at,
            )
            _seed_active_payroll_policy(classroom.class_id)

        d1 = (datetime.now(timezone.utc) - timedelta(days=2)).date()
        submit = submit_insurance_claim(
            canonical_context=self._student_context(classroom, student),
            entitlement_id=entitlement_id,
            claim_subject={"claimed_dates": [{"date": d1.isoformat(), "hours": hours, "explanation": "documented loss"}]},
        )
        assert submit.success is True, submit.error_message
        return entitlement_id, d1, submit.claim_id

    def test_upward_adjustment_rejected_not_clamped(self, app):
        """Approving MORE hours than claimed is rejected outright; nothing is written."""
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]

        with app.app_context():
            _, d1, claim_id = self._submit_single_date(
                classroom, student, idem="adj:upward", hours="2"
            )

            result = resolve_insurance_claim(
                canonical_context=self._teacher_context(classroom),
                claim_id=claim_id,
                approved=True,
                date_adjustments={d1.isoformat(): {"hours": "3", "note": "wants more"}},
            )
            assert result.success is False
            assert result.error_code == "ADJUSTMENT_EXCEEDS_CLAIM"

            claim = db.session.query(InsuranceClaim).filter_by(claim_id=claim_id).first()
            assert claim.status == "SUBMITTED"
            assert claim.payroll_event_id is None
            row = insurance_claim_service.list_productivity_dates_for_claim(
                claim_id, class_id=classroom.class_id
            )[0]
            assert row.student_claimed_hours == Decimal("2.00")  # immutable
            assert row.teacher_approved_hours is None  # nothing adjudicated
            assert row.recognized_payout is None

    def test_approval_without_adjustment_recognizes_claimed_hours(self, app):
        """Plain approval (no adjustments) records teacher_approved == student_claimed."""
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]

        with app.app_context():
            _, d1, claim_id = self._submit_single_date(
                classroom, student, idem="adj:plain", hours="2"
            )
            hourly = _resolve_hourly_pay_rate(classroom.class_id)

            result = resolve_insurance_claim(
                canonical_context=self._teacher_context(classroom),
                claim_id=claim_id,
                approved=True,
            )
            assert result.success is True, result.error_message
            assert result.reimbursement_amount == (hourly * Decimal("2")).quantize(Decimal("0.01"))

            claim = db.session.query(InsuranceClaim).filter_by(claim_id=claim_id).first()
            assert claim.status == "APPROVED"
            assert claim.payroll_event_id is not None
            row = insurance_claim_service.list_productivity_dates_for_claim(
                claim_id, class_id=classroom.class_id
            )[0]
            assert row.teacher_approved_hours == Decimal("2.00")
            assert row.adjustment_note is None  # no adjustment ⇒ no note needed

    def test_rejection_is_immediate_and_posts_no_money(self, app):
        """Rejection transitions to REJECTED with no payroll effect and no adjudication."""
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]

        with app.app_context():
            _, _d1, claim_id = self._submit_single_date(
                classroom, student, idem="adj:reject", hours="2"
            )

            result = resolve_insurance_claim(
                canonical_context=self._teacher_context(classroom),
                claim_id=claim_id,
                approved=False,
                override_reason="Not substantiated",
            )
            assert result.success is True, result.error_message

            claim = db.session.query(InsuranceClaim).filter_by(claim_id=claim_id).first()
            assert claim.status == "REJECTED"
            assert claim.payroll_event_id is None
            assert claim.ledger_transaction_id is None
            # No fabricated zero-hour adjudication for a rejection.
            row = insurance_claim_service.list_productivity_dates_for_claim(
                claim_id, class_id=classroom.class_id
            )[0]
            assert row.teacher_approved_hours is None
            assert row.recognized_payout is None
            events = db.session.query(PayrollEvent).filter_by(
                class_id=classroom.class_id
            ).all()
            assert events == []

    def test_forced_payroll_failure_rolls_back_entire_approval_unit(self, app, monkeypatch):
        """A forced MANUAL_CREDIT failure leaves the claim fully SUBMITTED — atomic unit.

        Proves the whole approval unit rolls back, not merely status: no adjudication
        hours, no recognized payout, no payroll/ledger lineage, no PayrollEvent.
        """
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]

        with app.app_context():
            _, _d1, claim_id = self._submit_single_date(
                classroom, student, idem="adj:forced-fail", hours="2"
            )

            def _boom(*args, **kwargs):
                raise RuntimeError("forced payroll coordination failure")

            # The FEAT imports record_payroll_event from app.feats.prod at call time.
            monkeypatch.setattr("app.feats.prod.record_payroll_event", _boom)

            result = resolve_insurance_claim(
                canonical_context=self._teacher_context(classroom),
                claim_id=claim_id,
                approved=True,
            )
            assert result.success is False
            assert result.error_code == "PAYROLL_COMPENSATION_FAILED"

            db.session.expire_all()

            # (1) claim remains SUBMITTED
            claim = db.session.query(InsuranceClaim).filter_by(claim_id=claim_id).first()
            assert claim.status == "SUBMITTED"
            # (4) no payroll_event_id  (5) no ledger_transaction_id
            assert claim.payroll_event_id is None
            assert claim.ledger_transaction_id is None
            assert claim.result_amount is None

            row = insurance_claim_service.list_productivity_dates_for_claim(
                claim_id, class_id=classroom.class_id
            )[0]
            # (2) teacher_approved_hours NULL on every date row
            assert row.teacher_approved_hours is None
            # (3) recognized_payout NULL
            assert row.recognized_payout is None

            # (6) no MANUAL_CREDIT / PayrollEvent effect exists
            events = db.session.query(PayrollEvent).filter_by(
                class_id=classroom.class_id
            ).all()
            assert events == []
