"""
Tests for FEAT-STOR-003: Insurance Claim Lifecycle

Covers:
- Submission validation, idempotency, eligibility flags
- Resolution (approval/rejection), atomicity, Ledger coordination
- Error cases and edge conditions
- Policy-UUID immutability

Uses canonical test initializer per SPEC-TEST-001.
"""

from uuid import uuid4
from app.extensions import db
from app.feats.base import FEATContext
from app.models import EntitlementEvent, PendingAction
from app.services.context_resolver import CanonicalContext
from app.services.store_policy_resolver import StorePolicyResolver
from app.feats.insurance_claim_feat import (
    submit_insurance_claim,
    resolve_insurance_claim,
)
from tests.helpers.classroom_initializer import initialize


def seed_insurance_policy(app, classroom, teacher_seat, policy_uuid_suffix: str = "001"):
    with app.app_context():
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"insurance-policy-seed:{policy_uuid_suffix}"):
            policy = StorePolicyResolver.create_store_product(
                class_id=classroom.class_id,
                payload={
                    "product_id": 1,
                    "is_purchasable": True,
                    "supports_direct_grants": True,
                    "price": "0.00",
                    "entitlement_type": "INSURANCE",
                    "name": "Insurance Policy",
                },
                created_by_seat_id=teacher_seat.id,
            )
        db.session.flush()
    db.session.commit()
    return policy.policy_uuid


class TestInsuranceClaimSubmission:
    """Tests for FEAT-STOR-003-SUBMIT"""

    def test_valid_submission_creates_pending_action(self, app):
        """Valid insurance claim submission creates pending_action with correct payload."""
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]
        teacher = classroom.teacher_seat
        policy_uuid = seed_insurance_policy(app, classroom, teacher, "valid-submission")

        with app.app_context():
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="insurance-claim:valid-submission"):
                # Create GRANTED entitlement event
                entitlement_id = str(uuid4())

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
                    payload={"policy_uuid": policy_uuid},
                )
                db.session.add(granted_event)
                db.session.flush()

            # Create student context
            context = CanonicalContext(
                user_id=student.user.id,
                class_id=classroom.class_id,
                seat_id=student.seat.id,
                actor_role="student",
            )

            # Execute submission
            claim_subject = {"transaction_id": 123}
            result = submit_insurance_claim(
                canonical_context=context,
                entitlement_id=entitlement_id,
                claim_subject=claim_subject,
            )

            # Assert
            assert result.success is True
            assert result.pending_action_id is not None
            assert result.correlation_id is not None
            assert result.submitted_at is not None

            # Verify pending_action in database
            pending = db.session.query(PendingAction).filter_by(
                pending_action_id=result.pending_action_id
            ).first()
            assert pending is not None
            assert pending.class_id == classroom.class_id
            assert pending.seat_id == student.seat.id
            assert pending.entitlement_id == entitlement_id
            assert pending.payload["policy_uuid"] == policy_uuid
            assert pending.payload["claim_subject"] == claim_subject

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

            # Execute submission against non-existent entitlement
            result = submit_insurance_claim(
                canonical_context=context,
                entitlement_id=str(uuid4()),  # Non-existent
                claim_subject={"transaction_id": 123},
            )

            # Assert
            assert result.success is False
            assert result.error_code == "ENTITLEMENT_NOT_FOUND"

    def test_submission_rejects_wrong_entitlement_type(self, app):
        """Submission fails if entitlement is not INSURANCE type."""
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]
        teacher = classroom.teacher_seat
        policy_uuid = seed_insurance_policy(app, classroom, teacher, "wrong-type")

        with app.app_context():
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="insurance-claim:wrong-type"):
                entitlement_id = str(uuid4())

                # Create DELAYED_USE entitlement (not INSURANCE)
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

            # Assert
            assert result.success is False
            assert result.error_code == "WRONG_ENTITLEMENT_TYPE"

    def test_submission_rejects_terminal_entitlement(self, app):
        """Submission fails if entitlement already has terminal event."""
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]
        teacher = classroom.teacher_seat
        policy_uuid = seed_insurance_policy(app, classroom, teacher, "terminal-entitlement")

        with app.app_context():
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="insurance-claim:terminal-entitlement"):
                entitlement_id = str(uuid4())

                # Create GRANTED and CONSUMED events
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
                    payload={"policy_uuid": policy_uuid},
                )
                consumed_event = EntitlementEvent(
                    event_id=str(uuid4()),
                    class_id=classroom.class_id,
                    entitlement_id=entitlement_id,
                    target_seat_id=student.seat.id,
                    actor_seat_id=student.seat.id,
                    product_id=1,
                    entitlement_type="INSURANCE",
                    acquisition_type="PERK",
                    event_type="CONSUMED",
                    payload={"claim_decision": "APPROVED"},
                )
                db.session.add(granted_event)
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

            # Assert
            assert result.success is False
            assert result.error_code == "ENTITLEMENT_TERMINAL"

    def test_submission_idempotency(self, app):
        """Retrying submission with same correlation_id returns prior result."""
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]
        teacher = classroom.teacher_seat
        policy_uuid = seed_insurance_policy(app, classroom, teacher, "idempotency")

        with app.app_context():
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="insurance-claim:idempotency"):
                entitlement_id = str(uuid4())

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
                    payload={"policy_uuid": policy_uuid},
                )
                db.session.add(granted_event)
                db.session.flush()

            context = CanonicalContext(
                user_id=student.user.id,
                class_id=classroom.class_id,
                seat_id=student.seat.id,
                actor_role="student",
            )

            correlation_id = f"corr_{uuid4().hex}"

            # First submission
            result1 = submit_insurance_claim(
                canonical_context=context,
                entitlement_id=entitlement_id,
                claim_subject={"transaction_id": 123},
                correlation_id=correlation_id,
            )

            # Second submission with same correlation_id
            result2 = submit_insurance_claim(
                canonical_context=context,
                entitlement_id=entitlement_id,
                claim_subject={"transaction_id": 123},
                correlation_id=correlation_id,
            )

            # Assert idempotency
            assert result2.success is True
            assert result2.pending_action_id == result1.pending_action_id
            assert result2.correlation_id == result1.correlation_id


class TestInsuranceClaimResolution:
    """Tests for FEAT-STOR-003-RESOLVE"""

    def test_approval_writes_consumed_and_deletes_pending(self, app):
        """Approval writes CONSUMED event and deletes pending_action atomically."""
        classroom = initialize("chemistry_p1", app)
        teacher = classroom.teacher_seat
        student = classroom.students[0]
        policy_uuid = seed_insurance_policy(app, classroom, teacher, "approval")

        with app.app_context():
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="insurance-claim:approval-setup"):
                entitlement_id = str(uuid4())

                # Create GRANTED event
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
                    payload={"policy_uuid": policy_uuid},
                )
                db.session.add(granted_event)
                db.session.flush()

                # Create pending_action
                correlation_id = f"corr_{uuid4().hex}"
                pending_action = PendingAction(
                    pending_action_id=str(uuid4()),
                    class_id=classroom.class_id,
                    seat_id=student.seat.id,
                    entitlement_id=entitlement_id,
                    correlation_id=correlation_id,
                    authoritative_feat="FEAT-STOR-003-RESOLVE",
                    payload={
                        "claim_subject": {"transaction_id": 123},
                        "policy_uuid": policy_uuid,
                    },
                )
                db.session.add(pending_action)
                db.session.flush()

            # Create teacher context
            teacher_context = CanonicalContext(
                user_id=teacher.user_id,
                class_id=classroom.class_id,
                seat_id=teacher.id,
                actor_role="teacher",
            )

            # Execute approval
            result = resolve_insurance_claim(
                canonical_context=teacher_context,
                pending_action_id=pending_action.pending_action_id,
                approved=True,
            )

            # Assert
            assert result.success is True
            assert result.decision == "APPROVED"
            assert result.entitlement_event_id is not None

            # Verify CONSUMED event created
            consumed_event = db.session.query(EntitlementEvent).filter_by(
                event_id=result.entitlement_event_id
            ).first()
            assert consumed_event is not None
            assert consumed_event.event_type == "CONSUMED"
            assert consumed_event.payload["claim_decision"] == "APPROVED"

            # Verify pending_action deleted
            deleted_pending = db.session.query(PendingAction).filter_by(
                pending_action_id=pending_action.pending_action_id
            ).first()
            assert deleted_pending is None

    def test_rejection_writes_consumed_no_ledger(self, app):
        """Rejection writes CONSUMED event with rejection marker, no Ledger coordination."""
        classroom = initialize("chemistry_p1", app)
        teacher = classroom.teacher_seat
        student = classroom.students[0]
        policy_uuid = seed_insurance_policy(app, classroom, teacher, "rejection")

        with app.app_context():
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="insurance-claim-rejection-setup"):
                entitlement_id = str(uuid4())

                # Create GRANTED event
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
                    payload={"policy_uuid": policy_uuid},
                )
                db.session.add(granted_event)
                db.session.flush()

                # Create pending_action
                correlation_id = f"corr_{uuid4().hex}"
                pending_action = PendingAction(
                    pending_action_id=str(uuid4()),
                    class_id=classroom.class_id,
                    seat_id=student.seat.id,
                    entitlement_id=entitlement_id,
                    correlation_id=correlation_id,
                    authoritative_feat="FEAT-STOR-003-RESOLVE",
                    payload={
                        "claim_subject": {"transaction_id": 123},
                        "policy_uuid": policy_uuid,
                    },
                )
                db.session.add(pending_action)
                db.session.flush()

            # Create teacher context
            teacher_context = CanonicalContext(
                user_id=teacher.user_id,
                class_id=classroom.class_id,
                seat_id=teacher.id,
                actor_role="teacher",
            )

            # Execute rejection
            result = resolve_insurance_claim(
                canonical_context=teacher_context,
                pending_action_id=pending_action.pending_action_id,
                approved=False,
                override_reason="Ineligible claim",
            )

            # Assert
            assert result.success is True
            assert result.decision == "REJECTED"
            assert result.reimbursement_amount is None

            # Verify CONSUMED event created with rejection marker
            consumed_event = db.session.query(EntitlementEvent).filter_by(
                event_id=result.entitlement_event_id
            ).first()
            assert consumed_event is not None
            assert consumed_event.payload["claim_decision"] == "REJECTED"
            assert consumed_event.payload["rejection_reason"] == "Ineligible claim"

            # Verify pending_action deleted
            deleted_pending = db.session.query(PendingAction).filter_by(
                pending_action_id=pending_action.pending_action_id
            ).first()
            assert deleted_pending is None

    def test_resolution_requires_teacher_role(self, app):
        """Only teachers can resolve insurance claims."""
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]
        teacher = classroom.teacher_seat
        policy_uuid = seed_insurance_policy(app, classroom, teacher, "authz")

        with app.app_context():
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="insurance-claim:authz"):
                entitlement_id = str(uuid4())

                # Create pending_action
                pending_action = PendingAction(
                    pending_action_id=str(uuid4()),
                    class_id=classroom.class_id,
                    seat_id=student.seat.id,
                    entitlement_id=entitlement_id,
                    correlation_id=f"corr_{uuid4().hex}",
                    authoritative_feat="FEAT-STOR-003-RESOLVE",
                    payload={"claim_subject": {}, "policy_uuid": "policy-001"},
                )
                db.session.add(pending_action)
                db.session.flush()

            # Create student context (not teacher)
            student_context = CanonicalContext(
                user_id=student.user.id,
                class_id=classroom.class_id,
                seat_id=student.seat.id,
                actor_role="student",  # Not teacher
            )

            # Execute resolution as student (should fail)
            result = resolve_insurance_claim(
                canonical_context=student_context,
                pending_action_id=pending_action.pending_action_id,
                approved=True,
            )

            # Assert
            assert result.success is False
            assert result.error_code == "UNAUTHORIZED"

    def test_resolution_rejects_nonexistent_pending_action(self, app):
        """Resolution fails if pending_action doesn't exist."""
        classroom = initialize("chemistry_p1", app)
        teacher = classroom.teacher_seat

        with app.app_context():
            teacher_context = CanonicalContext(
                user_id=teacher.user_id,
                class_id=classroom.class_id,
                seat_id=teacher.id,
                actor_role="teacher",
            )

            # Execute resolution with non-existent pending_action
            result = resolve_insurance_claim(
                canonical_context=teacher_context,
                pending_action_id=str(uuid4()),  # Non-existent
                approved=True,
            )

            # Assert
            assert result.success is False
            assert result.error_code == "PENDING_ACTION_NOT_FOUND"
