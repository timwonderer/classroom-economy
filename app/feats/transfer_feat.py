from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.extensions import db
from app.services import ledger_service


@dataclass
class TransferResult:
    withdrawal_transaction_id: int
    deposit_transaction_id: int
    amount: Decimal
    from_account: str
    to_account: str


def execute_account_transfer(
    *,
    seat_id: int,
    class_id: str,
    user_id: int,
    amount: Decimal,
    from_account: str,
    to_account: str,
) -> TransferResult:
    """Ledger-led FEAT for student checking/savings transfers."""
    withdraw_tx, deposit_tx = ledger_service.create_transfer_pair(
        seat_id=seat_id,
        class_id=class_id,
        teacher_id=user_id,
        amount=amount,
        from_account=from_account,
        to_account=to_account,
        withdraw_description=f"Transfer to {to_account}",
        deposit_description=f"Transfer from {from_account}",
    )
    return TransferResult(
        withdrawal_transaction_id=withdraw_tx.id,
        deposit_transaction_id=deposit_tx.id,
        amount=amount,
        from_account=from_account,
        to_account=to_account,
    )
