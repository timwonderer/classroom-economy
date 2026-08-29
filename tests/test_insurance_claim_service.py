"""Tests for the Store & Entitlements-owned InsuranceClaim lifecycle (Step A).

Covers the additive, product-agnostic claim persistence contract in
``app.services.insurance_claim_service``:

* SUBMITTED -> APPROVED/REJECTED only
* terminal immutability
* multiple claims under one active entitlement
* claim activity never writes a CONSUMED entitlement event
* idempotent submission by correlation_id (and conflict detection)
* class/seat scoping
* downstream result refs nullable until approval

The existing TRANSACTION path (pending_actions + terminal CONSUMED events) is NOT
migrated by this step and is intentionally untouched.

Uses the canonical test initializer per SPEC-TEST-001.
"""

from decimal import Decimal
from uuid import uuid4

import pytest

from app.extensions import db
from app.feats.base import FEATContext
from app.models import EntitlementEvent, InsuranceClaim
from app.services import insurance_claim_service as claims
from tests.helpers.classroom_initializer import initialize


def _seed_granted_insurance(
    classroom,
    seat_id,
    *,
    entitlement_type="INSURANCE",
    add_terminal=False,
):
    """Create a GRANTED entitlement event (optionally terminal) and return its id."""
    entitlement_id = str(uuid4())
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"seed:{uuid4().hex}"):
        db.session.add(
            EntitlementEvent(
                event_id=str(uuid4()),
                class_id=classroom.class_id,
                entitlement_id=entitlement_id,
                target_seat_id=seat_id,
                actor_seat_id=seat_id,
                product_id=1,
                entitlement_type=entitlement_type,
                acquisition_type="PERK",
                event_type="GRANTED",
                payload={"policy_uuid": f"policy-{uuid4().hex}"},
            )
        )
        if add_terminal:
            db.session.add(
                EntitlementEvent(
                    event_id=str(uuid4()),
                    class_id=classroom.class_id,
                    entitlement_id=entitlement_id,
                    target_seat_id=seat_id,
                    actor_seat_id=seat_id,
                    product_id=1,
                    entitlement_type=entitlement_type,
                    acquisition_type="PERK",
                    event_type="CONSUMED",
                    payload={"claim_decision": "APPROVED"},
                )
            )
        db.session.flush()
    return entitlement_id


class TestSubmission:
    def test_create_claim_starts_submitted(self, app):
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]
        with app.app_context():
            entitlement_id = _seed_granted_insurance(classroom, student.seat.id)
            with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"create:{uuid4().hex}"):
                claim = claims.create_claim(
                    class_id=classroom.class_id,
                    entitlement_id=entitlement_id,
                    target_seat_id=student.seat.id,
                    actor_seat_id=student.seat.id,
                    correlation_id=f"corr_{uuid4().hex}",
                    claim_basis={"transaction_id": 42},
                )
                assert claim.status == claims.SUBMITTED
                assert claim.claim_basis == {"transaction_id": 42}
                # Downstream refs are nullable until approval.
                assert claim.decided_at is None
                assert claim.decided_by_seat_id is None
                assert claim.result_amount is None
                assert claim.payroll_event_id is None
                assert claim.ledger_transaction_id is None

    def test_create_rejects_missing_entitlement(self, app):
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]
        with app.app_context():
            with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"create:{uuid4().hex}"):
                with pytest.raises(claims.ClaimEntitlementInvalid):
                    claims.create_claim(
                        class_id=classroom.class_id,
                        entitlement_id=str(uuid4()),  # never granted
                        target_seat_id=student.seat.id,
                        actor_seat_id=student.seat.id,
                        correlation_id=f"corr_{uuid4().hex}",
                        claim_basis={"transaction_id": 1},
                    )

    def test_create_rejects_wrong_entitlement_type(self, app):
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]
        with app.app_context():
            entitlement_id = _seed_granted_insurance(
                classroom, student.seat.id, entitlement_type="DELAYED_USE"
            )
            with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"create:{uuid4().hex}"):
                with pytest.raises(claims.ClaimEntitlementInvalid):
                    claims.create_claim(
                        class_id=classroom.class_id,
                        entitlement_id=entitlement_id,
                        target_seat_id=student.seat.id,
                        actor_seat_id=student.seat.id,
                        correlation_id=f"corr_{uuid4().hex}",
                        claim_basis={"transaction_id": 1},
                    )

    def test_create_rejects_terminal_entitlement(self, app):
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]
        with app.app_context():
            entitlement_id = _seed_granted_insurance(
                classroom, student.seat.id, add_terminal=True
            )
            with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"create:{uuid4().hex}"):
                with pytest.raises(claims.ClaimEntitlementInvalid):
                    claims.create_claim(
                        class_id=classroom.class_id,
                        entitlement_id=entitlement_id,
                        target_seat_id=student.seat.id,
                        actor_seat_id=student.seat.id,
                        correlation_id=f"corr_{uuid4().hex}",
                        claim_basis={"transaction_id": 1},
                    )

    def test_idempotent_submission_returns_same_claim(self, app):
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]
        with app.app_context():
            entitlement_id = _seed_granted_insurance(classroom, student.seat.id)
            correlation_id = f"corr_{uuid4().hex}"
            with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"create:{uuid4().hex}"):
                first = claims.create_claim(
                    class_id=classroom.class_id,
                    entitlement_id=entitlement_id,
                    target_seat_id=student.seat.id,
                    actor_seat_id=student.seat.id,
                    correlation_id=correlation_id,
                    claim_basis={"transaction_id": 1},
                )
                second = claims.create_claim(
                    class_id=classroom.class_id,
                    entitlement_id=entitlement_id,
                    target_seat_id=student.seat.id,
                    actor_seat_id=student.seat.id,
                    correlation_id=correlation_id,
                    claim_basis={"transaction_id": 1},
                )
                assert first.claim_id == second.claim_id
                rows = (
                    db.session.query(InsuranceClaim)
                    .filter(InsuranceClaim.correlation_id == correlation_id)
                    .count()
                )
                assert rows == 1

    def test_idempotency_conflict_on_different_context(self, app):
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]
        with app.app_context():
            ent_a = _seed_granted_insurance(classroom, student.seat.id)
            ent_b = _seed_granted_insurance(classroom, student.seat.id)
            correlation_id = f"corr_{uuid4().hex}"
            with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"create:{uuid4().hex}"):
                claims.create_claim(
                    class_id=classroom.class_id,
                    entitlement_id=ent_a,
                    target_seat_id=student.seat.id,
                    actor_seat_id=student.seat.id,
                    correlation_id=correlation_id,
                    claim_basis={"transaction_id": 1},
                )
                with pytest.raises(claims.ClaimIdempotencyConflict):
                    claims.create_claim(
                        class_id=classroom.class_id,
                        entitlement_id=ent_b,  # different entitlement, same correlation
                        target_seat_id=student.seat.id,
                        actor_seat_id=student.seat.id,
                        correlation_id=correlation_id,
                        claim_basis={"transaction_id": 1},
                    )


class TestMultipleClaims:
    def test_multiple_claims_under_one_active_entitlement(self, app):
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]
        with app.app_context():
            entitlement_id = _seed_granted_insurance(classroom, student.seat.id)
            with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"create:{uuid4().hex}"):
                for i in range(3):
                    claims.create_claim(
                        class_id=classroom.class_id,
                        entitlement_id=entitlement_id,
                        target_seat_id=student.seat.id,
                        actor_seat_id=student.seat.id,
                        correlation_id=f"corr_{uuid4().hex}",
                        claim_basis={"claimed_date": f"2026-08-2{i}"},
                    )
                listed = claims.list_claims_for_entitlement(
                    class_id=classroom.class_id,
                    entitlement_id=entitlement_id,
                    target_seat_id=student.seat.id,
                )
                assert len(listed) == 3
                assert all(c.status == claims.SUBMITTED for c in listed)

    def test_claim_activity_never_writes_consumed_event(self, app):
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]
        teacher = classroom.teacher_seat
        with app.app_context():
            entitlement_id = _seed_granted_insurance(classroom, student.seat.id)
            with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"lifecycle:{uuid4().hex}"):
                claim = claims.create_claim(
                    class_id=classroom.class_id,
                    entitlement_id=entitlement_id,
                    target_seat_id=student.seat.id,
                    actor_seat_id=student.seat.id,
                    correlation_id=f"corr_{uuid4().hex}",
                    claim_basis={"transaction_id": 7},
                )
                claims.decide_claim(
                    claim_id=claim.claim_id,
                    class_id=classroom.class_id,
                    decided_by_seat_id=teacher.id,
                    approved=True,
                    result_amount=Decimal("5.00"),
                )
            # No terminal entitlement event should exist for this lineage.
            terminal = (
                db.session.query(EntitlementEvent)
                .filter(
                    EntitlementEvent.entitlement_id == entitlement_id,
                    EntitlementEvent.class_id == classroom.class_id,
                    EntitlementEvent.event_type.in_(["CONSUMED", "EXPIRED", "REVOKED"]),
                )
                .count()
            )
            assert terminal == 0


class TestDecision:
    def test_approval_sets_terminal_and_refs(self, app):
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]
        teacher = classroom.teacher_seat
        with app.app_context():
            entitlement_id = _seed_granted_insurance(classroom, student.seat.id)
            with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"decide:{uuid4().hex}"):
                claim = claims.create_claim(
                    class_id=classroom.class_id,
                    entitlement_id=entitlement_id,
                    target_seat_id=student.seat.id,
                    actor_seat_id=student.seat.id,
                    correlation_id=f"corr_{uuid4().hex}",
                    claim_basis={"transaction_id": 7},
                )
                decided = claims.decide_claim(
                    claim_id=claim.claim_id,
                    class_id=classroom.class_id,
                    decided_by_seat_id=teacher.id,
                    approved=True,
                    decision_note="Looks valid",
                    result_amount=Decimal("9.50"),
                    payroll_event_id=111,
                    ledger_transaction_id=222,
                )
                assert decided.status == claims.APPROVED
                assert decided.decided_by_seat_id == teacher.id
                assert decided.decided_at is not None
                assert decided.decision_note == "Looks valid"
                assert decided.result_amount == Decimal("9.50")
                assert decided.payroll_event_id == 111
                assert decided.ledger_transaction_id == 222

    def test_rejection_sets_terminal_no_refs(self, app):
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]
        teacher = classroom.teacher_seat
        with app.app_context():
            entitlement_id = _seed_granted_insurance(classroom, student.seat.id)
            with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"decide:{uuid4().hex}"):
                claim = claims.create_claim(
                    class_id=classroom.class_id,
                    entitlement_id=entitlement_id,
                    target_seat_id=student.seat.id,
                    actor_seat_id=student.seat.id,
                    correlation_id=f"corr_{uuid4().hex}",
                    claim_basis={"transaction_id": 7},
                )
                decided = claims.decide_claim(
                    claim_id=claim.claim_id,
                    class_id=classroom.class_id,
                    decided_by_seat_id=teacher.id,
                    approved=False,
                    decision_note="Ineligible",
                    # refs supplied but must be ignored on rejection
                    result_amount=Decimal("9.50"),
                    payroll_event_id=111,
                    ledger_transaction_id=222,
                )
                assert decided.status == claims.REJECTED
                assert decided.decision_note == "Ineligible"
                assert decided.result_amount is None
                assert decided.payroll_event_id is None
                assert decided.ledger_transaction_id is None

    def test_terminal_immutability(self, app):
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]
        teacher = classroom.teacher_seat
        with app.app_context():
            entitlement_id = _seed_granted_insurance(classroom, student.seat.id)
            with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"decide:{uuid4().hex}"):
                claim = claims.create_claim(
                    class_id=classroom.class_id,
                    entitlement_id=entitlement_id,
                    target_seat_id=student.seat.id,
                    actor_seat_id=student.seat.id,
                    correlation_id=f"corr_{uuid4().hex}",
                    claim_basis={"transaction_id": 7},
                )
                claims.decide_claim(
                    claim_id=claim.claim_id,
                    class_id=classroom.class_id,
                    decided_by_seat_id=teacher.id,
                    approved=True,
                    result_amount=Decimal("1.00"),
                )
                with pytest.raises(claims.ClaimAlreadyDecided):
                    claims.decide_claim(
                        claim_id=claim.claim_id,
                        class_id=classroom.class_id,
                        decided_by_seat_id=teacher.id,
                        approved=False,
                    )

    def test_decide_missing_claim_raises(self, app):
        classroom = initialize("chemistry_p1", app)
        teacher = classroom.teacher_seat
        with app.app_context():
            with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"decide:{uuid4().hex}"):
                with pytest.raises(claims.ClaimNotFound):
                    claims.decide_claim(
                        claim_id=str(uuid4()),
                        class_id=classroom.class_id,
                        decided_by_seat_id=teacher.id,
                        approved=True,
                    )


class TestScoping:
    def test_get_claim_wrong_class_returns_none(self, app):
        classroom = initialize("chemistry_p1", app)
        other = initialize("ap_csp_p3", app)
        student = classroom.students[0]
        with app.app_context():
            entitlement_id = _seed_granted_insurance(classroom, student.seat.id)
            with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"create:{uuid4().hex}"):
                claim = claims.create_claim(
                    class_id=classroom.class_id,
                    entitlement_id=entitlement_id,
                    target_seat_id=student.seat.id,
                    actor_seat_id=student.seat.id,
                    correlation_id=f"corr_{uuid4().hex}",
                    claim_basis={"transaction_id": 1},
                )
            assert claims.get_claim(claim.claim_id, class_id=classroom.class_id) is not None
            assert claims.get_claim(claim.claim_id, class_id=other.class_id) is None

    def test_list_scoped_by_target_seat(self, app):
        classroom = initialize("chemistry_p1", app)
        student_a = classroom.students[0]
        student_b = classroom.students[1]
        with app.app_context():
            entitlement_id = _seed_granted_insurance(classroom, student_a.seat.id)
            with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"create:{uuid4().hex}"):
                claims.create_claim(
                    class_id=classroom.class_id,
                    entitlement_id=entitlement_id,
                    target_seat_id=student_a.seat.id,
                    actor_seat_id=student_a.seat.id,
                    correlation_id=f"corr_{uuid4().hex}",
                    claim_basis={"transaction_id": 1},
                )
            # Claims for student A's entitlement are not visible under student B's seat.
            listed_b = claims.list_claims_for_entitlement(
                class_id=classroom.class_id,
                entitlement_id=entitlement_id,
                target_seat_id=student_b.seat.id,
            )
            assert listed_b == []

    def test_create_rejects_seat_without_grant(self, app):
        classroom = initialize("chemistry_p1", app)
        student_a = classroom.students[0]
        student_b = classroom.students[1]
        with app.app_context():
            entitlement_id = _seed_granted_insurance(classroom, student_a.seat.id)
            with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"create:{uuid4().hex}"):
                # Entitlement granted to A; claiming as B must fail validation.
                with pytest.raises(claims.ClaimEntitlementInvalid):
                    claims.create_claim(
                        class_id=classroom.class_id,
                        entitlement_id=entitlement_id,
                        target_seat_id=student_b.seat.id,
                        actor_seat_id=student_b.seat.id,
                        correlation_id=f"corr_{uuid4().hex}",
                        claim_basis={"transaction_id": 1},
                    )


def test_migration_revision_chain_links_to_head():
    """The Step A migration must chain from the prior head and be reversible."""
    from migrations.versions.a7b8c9d0e1f3_add_insurance_claims_table import (
        revision,
        down_revision,
        upgrade,
        downgrade,
    )

    assert revision == "a7b8c9d0e1f3"
    assert down_revision == "d4e5f6a7b8c9"
    assert callable(upgrade)
    assert callable(downgrade)
