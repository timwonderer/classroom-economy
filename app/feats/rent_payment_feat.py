"""STUB: Rent Payment FEAT — Being rebuilt under Obligations domain.

This module is a placeholder during the migration from legacy rent payment
to the canonical Obligations domain (DOM-OBL-001).

The new implementation will:
1. Create a Ledger transaction for the payment amount
2. Call execute_satisfy_obligation_payment() to record PAYMENT event
3. Award hall passes and update balances per payment policies

Currently stubbed to allow application load.
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class RentPaymentResult:
    """Result of rent payment execution."""
    transaction_id: int | None = None
    payment_id: int | None = None
    amount_paid: Decimal = Decimal('0.00')
    is_partial: bool = False
    new_remaining: Decimal = Decimal('0.00')
    passes_awarded: int = 0


def execute_rent_payment(**kwargs) -> RentPaymentResult:
    """STUB: Execute rent payment through Obligations domain.

    TODO: Implement using:
    - create_ledger_transaction() from ledger service (records payment amount)
    - execute_satisfy_obligation_payment() from satisfy_obligation_feat (records PAYMENT event)
    - Award hall passes based on payment policies
    """
    return RentPaymentResult(
        transaction_id=None,
        payment_id=None,
        amount_paid=Decimal('0.00'),
        is_partial=False,
        new_remaining=Decimal('0.00'),
        passes_awarded=0,
    )
