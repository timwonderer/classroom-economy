"""Void/reversal obligation-finality guard (SPEC-OPS-001 §VII, INV-OPS-008).

Obligation-related monetary transactions are neither voidable nor reversible.
The canonical void/reversal boundary (FEAT-LED-002, _execute_void_transaction_impl)
must reject them by provenance BEFORE any compensating transaction is created, and
must not resurrect the removed legacy rent-payment reversal path (INV-OPS-012).

Non-obligation transactions must still follow the ordinary lawful void path.
"""

from decimal import Decimal

import pytest

from app import db
from app.feats.base import FEATContext
from app.models import Transaction, TransactionStatus
from app.feats.transaction_void_feat import (
    execute_void_transaction,
    ObligationTransactionNotVoidable,
)
from app.feats.assess_obligation_feat import execute_assess_obligation
from app.feats.satisfy_obligation_feat import execute_satisfy_obligation_payment
from app.services import ledger_service
from tests.helpers.ledger import provision_ledger_classroom


def _create_transaction(seat, *, type, amount, description, idempotency_key,
                        status=TransactionStatus.POSTED):
    """Create a ledger transaction row through the canonical FEAT boundary."""
    with FEATContext("FEAT-LED-001", idempotency_key=idempotency_key):
        tx = Transaction(
            user_id=seat.user_id,
            class_id=seat.class_id,
            seat_id=seat.id,
            target_seat_id=seat.id,
            actor_seat_id=seat.id,
            mechanism="self",
            amount=amount,
            account_type="checking",
            status=status,
            type=type,
            description=description,
        )
        db.session.add(tx)
        db.session.flush()
        db.session.refresh(tx)
    return tx


def _make_obligation_related_payment(seat, *, correlation_id, amount, idempotency_key):
    """Create a payment transaction with genuine obligation provenance.

    Establishes an ASSESSMENT then a PAYMENT satisfaction event that references
    the ledger transaction via ledger_transaction_id, exactly as a lawful rent
    payment would. The transaction is thereafter obligation-related by provenance.
    """
    tx = _create_transaction(
        seat,
        type='Rent Payment',
        amount=amount,
        description='Rent Payment',
        idempotency_key=idempotency_key,
    )
    execute_assess_obligation(
        seat_id=seat.id,
        class_id=seat.class_id,
        internal_ref='rent:monthly',
        correlation_id=correlation_id,
        obligation_type='RENT',
    )
    db.session.commit()
    execute_satisfy_obligation_payment(
        correlation_id=correlation_id,
        class_id=seat.class_id,
        seat_id=seat.id,
        ledger_transaction_id=tx.id,
    )
    db.session.commit()
    return tx


def test_DOM_OPS_001__rent_payment_obligation_related_tx_cannot_be_voided(client, app):
    """A rent payment (obligation-related by provenance) cannot be voided (INV-OPS-008)."""
    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat = classroom.students[0].seat

    tx = _make_obligation_related_payment(
        seat,
        correlation_id='rent-void-guard-a',
        amount=Decimal('-20.00'),
        idempotency_key='void-guard:a:paytx',
    )

    with pytest.raises(ObligationTransactionNotVoidable):
        execute_void_transaction(
            tx,
            correlation_id='void-guard:a:corr',
            idempotency_key='void-guard:a:idem',
        )


def test_DOM_OPS_001__obligation_tx_does_not_fall_through_to_compensation(client, app, monkeypatch):
    """Rejection happens before any compensating/reversal transaction is created."""
    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat = classroom.students[0].seat

    tx = _make_obligation_related_payment(
        seat,
        correlation_id='rent-void-guard-b',
        amount=Decimal('-20.00'),
        idempotency_key='void-guard:b:paytx',
    )

    calls = {"compensate": 0, "void_pending": 0}
    real_compensate = ledger_service.compensate_posted_transaction
    real_void_pending = ledger_service.void_pending_transaction

    def _spy_compensate(*a, **k):
        calls["compensate"] += 1
        return real_compensate(*a, **k)

    def _spy_void_pending(*a, **k):
        calls["void_pending"] += 1
        return real_void_pending(*a, **k)

    monkeypatch.setattr(ledger_service, "compensate_posted_transaction", _spy_compensate)
    monkeypatch.setattr(ledger_service, "void_pending_transaction", _spy_void_pending)

    with pytest.raises(ObligationTransactionNotVoidable):
        execute_void_transaction(
            tx,
            correlation_id='void-guard:b:corr',
            idempotency_key='void-guard:b:idem',
        )

    assert calls["compensate"] == 0, "obligation-related tx must not reach compensation"
    assert calls["void_pending"] == 0, "obligation-related tx must not reach pending-void"


def test_DOM_OPS_001__rejection_makes_no_ledger_mutation(client, app):
    """No ledger row is created or mutated when an obligation-related void is rejected."""
    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat = classroom.students[0].seat

    tx = _make_obligation_related_payment(
        seat,
        correlation_id='rent-void-guard-c',
        amount=Decimal('-20.00'),
        idempotency_key='void-guard:c:paytx',
    )

    tx_count_before = Transaction.query.filter_by(class_id=seat.class_id).count()

    with pytest.raises(ObligationTransactionNotVoidable):
        execute_void_transaction(
            tx,
            correlation_id='void-guard:c:corr',
            idempotency_key='void-guard:c:idem',
        )
    db.session.rollback()

    assert Transaction.query.filter_by(class_id=seat.class_id).count() == tx_count_before
    db.session.refresh(tx)
    assert tx.is_void is False
    assert tx.reversal_transaction_id is None
    assert tx.status != TransactionStatus.VOID


def test_DOM_OPS_001__non_obligation_transaction_still_voids_lawfully(client, app):
    """A plain (non-obligation) transaction still follows the lawful void path.

    The guard must only reject obligation-related transactions; an ordinary
    transaction passes the guard and is lawfully voided (here via the pending
    void path), proving the guard did not over-reach.
    """
    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat = classroom.students[0].seat

    tx = _create_transaction(
        seat,
        type='adjustment',
        amount=Decimal('-5.00'),
        description='teacher adjustment',
        idempotency_key='void-guard:d:paytx',
        status=TransactionStatus.PENDING,
    )

    # Must not raise: non-obligation transactions are not blocked by the guard.
    # Void under the tx's own stored correlation to satisfy the FEAT-LED-002
    # tier-1 correlation-alignment check (models.py before_flush enforcement).
    execute_void_transaction(
        tx,
        correlation_id=tx.correlation_id,
        idempotency_key='void-guard:d:idem',
    )

    db.session.refresh(tx)
    assert tx.is_void is True
    assert tx.status == TransactionStatus.VOID
