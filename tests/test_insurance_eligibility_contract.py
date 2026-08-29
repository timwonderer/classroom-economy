"""Unit tests for the system-owned TRANSACTION eligibility law.

``insurance_eligibility_contract.evaluate_transaction_claim_basis`` is CTH's
canonical authority for *which* ledger transactions may lawfully back a
TRANSACTION insurance claim (Step 6, rule 4). The disallowed set is fixed system
law — a teacher cannot widen or narrow it — so these tests pin every predicate:

* structural gates (not-found, wrong class, wrong seat, not-a-loss) that never
  touch the DB and are exercised with lightweight in-memory ``Transaction`` rows;
* category gates (transfer, obligation, globally-disallowed type);
* entitlement-linked gates resolved through shared correlation lineage
  (collective-goal exclusion; item purchased-and-USED requirement; item
  revoked/expired exclusion) which require persisted ``EntitlementEvent`` rows.

Uses the canonical test initializer per SPEC-TEST-001.
"""

from decimal import Decimal
from uuid import uuid4

from app.extensions import db
from app.feats.base import FEATContext
from app.models import EntitlementEvent, Transaction
from app.services import insurance_eligibility_contract as eligibility
from tests.helpers.classroom_initializer import initialize


# ---------------------------------------------------------------------------
# Structural gates — no DB access, so an unpersisted Transaction row suffices.
# ---------------------------------------------------------------------------

def _txn(*, class_id, seat_id, amount, ttype="purchase", correlation_id=None):
    """Build an (unpersisted) Transaction carrying only the fields the contract reads."""
    return Transaction(
        class_id=class_id,
        seat_id=seat_id,
        amount=Decimal(amount) if not isinstance(amount, Decimal) else amount,
        type=ttype,
        correlation_id=correlation_id or f"corr_{uuid4().hex}",
    )


class TestStructuralGates:
    def test_none_transaction_not_found(self, app):
        with app.app_context():
            verdict = eligibility.evaluate_transaction_claim_basis(
                None, class_id="c1", covered_seat_id=1
            )
            assert verdict.eligible is False
            assert verdict.reason_code == eligibility.NOT_FOUND

    def test_wrong_class(self, app):
        with app.app_context():
            txn = _txn(class_id="OTHER", seat_id=1, amount="-5.00")
            verdict = eligibility.evaluate_transaction_claim_basis(
                txn, class_id="THIS", covered_seat_id=1
            )
            assert verdict.eligible is False
            assert verdict.reason_code == eligibility.WRONG_CLASS

    def test_wrong_seat(self, app):
        with app.app_context():
            txn = _txn(class_id="c1", seat_id=2, amount="-5.00")
            verdict = eligibility.evaluate_transaction_claim_basis(
                txn, class_id="c1", covered_seat_id=1
            )
            assert verdict.eligible is False
            assert verdict.reason_code == eligibility.WRONG_SEAT

    def test_positive_amount_is_not_a_loss(self, app):
        with app.app_context():
            txn = _txn(class_id="c1", seat_id=1, amount="5.00")
            verdict = eligibility.evaluate_transaction_claim_basis(
                txn, class_id="c1", covered_seat_id=1
            )
            assert verdict.eligible is False
            assert verdict.reason_code == eligibility.NOT_A_LOSS

    def test_zero_amount_is_not_a_loss(self, app):
        with app.app_context():
            txn = _txn(class_id="c1", seat_id=1, amount="0.00")
            verdict = eligibility.evaluate_transaction_claim_basis(
                txn, class_id="c1", covered_seat_id=1
            )
            assert verdict.eligible is False
            assert verdict.reason_code == eligibility.NOT_A_LOSS

    def test_transfer_not_insurable(self, app):
        with app.app_context():
            for ttype in ("withdrawal", "deposit", "transfer"):
                txn = _txn(class_id="c1", seat_id=1, amount="-5.00", ttype=ttype)
                verdict = eligibility.evaluate_transaction_claim_basis(
                    txn, class_id="c1", covered_seat_id=1
                )
                assert verdict.eligible is False, ttype
                assert verdict.reason_code == eligibility.TRANSFER, ttype

    def test_obligation_not_insurable(self, app):
        with app.app_context():
            for ttype in ("rent", "property_tax"):
                txn = _txn(class_id="c1", seat_id=1, amount="-5.00", ttype=ttype)
                verdict = eligibility.evaluate_transaction_claim_basis(
                    txn, class_id="c1", covered_seat_id=1
                )
                assert verdict.eligible is False, ttype
                assert verdict.reason_code == eligibility.OBLIGATION, ttype

    def test_disallowed_category(self, app):
        with app.app_context():
            for ttype in eligibility.DISALLOWED_TRANSACTION_TYPES:
                txn = _txn(class_id="c1", seat_id=1, amount="-5.00", ttype=ttype)
                verdict = eligibility.evaluate_transaction_claim_basis(
                    txn, class_id="c1", covered_seat_id=1
                )
                assert verdict.eligible is False, ttype
                assert verdict.reason_code == eligibility.DISALLOWED_CATEGORY, ttype

    def test_type_comparison_is_case_insensitive(self, app):
        with app.app_context():
            txn = _txn(class_id="c1", seat_id=1, amount="-5.00", ttype="TRANSFER")
            verdict = eligibility.evaluate_transaction_claim_basis(
                txn, class_id="c1", covered_seat_id=1
            )
            assert verdict.reason_code == eligibility.TRANSFER

    def test_plain_loss_with_no_lineage_is_eligible(self, app):
        """A negative, owned, ordinary-category loss with no entitlement lineage passes."""
        with app.app_context():
            txn = _txn(class_id="c1", seat_id=1, amount="-5.00", ttype="purchase")
            verdict = eligibility.evaluate_transaction_claim_basis(
                txn, class_id="c1", covered_seat_id=1
            )
            assert verdict.eligible is True
            assert verdict.reason_code is None


# ---------------------------------------------------------------------------
# Entitlement-linked gates — require persisted GRANTED/terminal EntitlementEvents
# sharing the transaction's correlation lineage.
# ---------------------------------------------------------------------------

def _add_event(classroom, student, *, entitlement_id, entitlement_type, event_type, correlation_id):
    ev = EntitlementEvent(
        event_id=str(uuid4()),
        class_id=classroom.class_id,
        entitlement_id=entitlement_id,
        target_seat_id=student.seat.id,
        actor_seat_id=student.seat.id,
        product_id=1,
        entitlement_type=entitlement_type,
        acquisition_type="PURCHASE",
        event_type=event_type,
        correlation_id=correlation_id,
        payload={},
    )
    db.session.add(ev)
    db.session.flush()
    return ev


class TestEntitlementLinkedGates:
    def test_collective_goal_contribution_not_insurable(self, app):
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]
        with app.app_context():
            cid = f"corr_{uuid4().hex}"
            with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"elig-goal:{cid}"):
                _add_event(
                    classroom, student,
                    entitlement_id=str(uuid4()),
                    entitlement_type="COLLECTIVE_GOAL",
                    event_type="GRANTED",
                    correlation_id=cid,
                )
            txn = _txn(
                class_id=classroom.class_id, seat_id=student.seat.id,
                amount="-5.00", ttype="purchase", correlation_id=cid,
            )
            verdict = eligibility.evaluate_transaction_claim_basis(
                txn, class_id=classroom.class_id, covered_seat_id=student.seat.id
            )
            assert verdict.eligible is False
            assert verdict.reason_code == eligibility.GOAL

    def test_item_not_yet_used_is_ineligible(self, app):
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]
        with app.app_context():
            cid = f"corr_{uuid4().hex}"
            entitlement_id = str(uuid4())
            with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"elig-item-unused:{cid}"):
                _add_event(
                    classroom, student,
                    entitlement_id=entitlement_id,
                    entitlement_type="IMMEDIATE_USE",
                    event_type="GRANTED",
                    correlation_id=cid,
                )
            txn = _txn(
                class_id=classroom.class_id, seat_id=student.seat.id,
                amount="-5.00", ttype="purchase", correlation_id=cid,
            )
            verdict = eligibility.evaluate_transaction_claim_basis(
                txn, class_id=classroom.class_id, covered_seat_id=student.seat.id
            )
            assert verdict.eligible is False
            assert verdict.reason_code == eligibility.ITEM_NOT_USED

    def test_item_used_is_eligible(self, app):
        """An item purchase becomes claimable once its value is realized (CONSUMED)."""
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]
        with app.app_context():
            cid = f"corr_{uuid4().hex}"
            entitlement_id = str(uuid4())
            with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"elig-item-used:{cid}"):
                _add_event(
                    classroom, student,
                    entitlement_id=entitlement_id,
                    entitlement_type="DELAYED_USE",
                    event_type="GRANTED",
                    correlation_id=cid,
                )
                _add_event(
                    classroom, student,
                    entitlement_id=entitlement_id,
                    entitlement_type="DELAYED_USE",
                    event_type="CONSUMED",
                    correlation_id=cid,
                )
            txn = _txn(
                class_id=classroom.class_id, seat_id=student.seat.id,
                amount="-5.00", ttype="purchase", correlation_id=cid,
            )
            verdict = eligibility.evaluate_transaction_claim_basis(
                txn, class_id=classroom.class_id, covered_seat_id=student.seat.id
            )
            assert verdict.eligible is True
            assert verdict.reason_code is None

    def test_item_revoked_is_ineligible(self, app):
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]
        with app.app_context():
            cid = f"corr_{uuid4().hex}"
            entitlement_id = str(uuid4())
            with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"elig-item-revoked:{cid}"):
                _add_event(
                    classroom, student,
                    entitlement_id=entitlement_id,
                    entitlement_type="PRIVILEGE",
                    event_type="GRANTED",
                    correlation_id=cid,
                )
                # A revoked item never delivered lasting value — its loss is not
                # insurable even though it was purchased. (Schema permits only one
                # terminal event per lineage, so REVOKED stands alone here.)
                _add_event(
                    classroom, student,
                    entitlement_id=entitlement_id,
                    entitlement_type="PRIVILEGE",
                    event_type="REVOKED",
                    correlation_id=cid,
                )
            txn = _txn(
                class_id=classroom.class_id, seat_id=student.seat.id,
                amount="-5.00", ttype="purchase", correlation_id=cid,
            )
            verdict = eligibility.evaluate_transaction_claim_basis(
                txn, class_id=classroom.class_id, covered_seat_id=student.seat.id
            )
            assert verdict.eligible is False
            assert verdict.reason_code == eligibility.ITEM_REVOKED_OR_EXPIRED
