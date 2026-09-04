from __future__ import annotations

from decimal import Decimal
from typing import NamedTuple

from app.extensions import db
from app.models import LedgerBalanceSnapshot, Transaction, TransactionStatus, _quantize_currency


def _non_void_filter():
    return Transaction.is_void.isnot(True)


class LedgerProofResult(NamedTuple):
    outcome: str
    reconstructed_cents: int | None = None
    boundary: int | None = None
    complete: bool = True
    code: str | None = None


class TransferProofResult(NamedTuple):
    outcome: str
    leg_count: int
    scope_consistent: bool
    account_pair_valid: bool
    equal_magnitude: bool
    zero_sum: bool
    posting_consistent: bool
    code: str | None = None


def _get_balance_cache(seat_id: int, class_id: str, account_type: str):
    if not class_id or not seat_id:
        raise ValueError("FATAL: Balance lookup requires class_id and seat_id.")
    return LedgerBalanceSnapshot.query.filter_by(seat_id=seat_id, class_id=class_id, account_type=account_type).first()


def _get_posted_balance_fallback(seat_id: int, class_id: str, account_type: str) -> Decimal:
    total = db.session.query(db.func.sum(Transaction.amount)).filter(
        Transaction.seat_id == seat_id, Transaction.class_id == class_id,
        Transaction.account_type == account_type, Transaction.status == TransactionStatus.POSTED,
        _non_void_filter(),
    ).scalar() or Decimal("0.00")
    return _quantize_currency(total)


def get_posted_balance(seat_id: int, class_id: str, account_type: str) -> Decimal:
    cache = _get_balance_cache(seat_id, class_id, account_type)
    return _quantize_currency(Decimal(cache.posted_balance_cents) / 100) if cache else _get_posted_balance_fallback(seat_id, class_id, account_type)


def get_pending_balance_delta(seat_id: int, class_id: str, account_type: str) -> Decimal:
    pending = db.session.query(db.func.sum(Transaction.amount)).filter(
        Transaction.seat_id == seat_id, Transaction.class_id == class_id,
        Transaction.account_type == account_type, Transaction.status == TransactionStatus.PENDING,
        _non_void_filter(),
    ).scalar() or Decimal("0.00")
    return _quantize_currency(pending)


def get_available_balance(seat_id: int, class_id: str, account_type: str) -> Decimal:
    return _quantize_currency(get_posted_balance(seat_id, class_id, account_type) + get_pending_balance_delta(seat_id, class_id, account_type))


def get_available_balances(seat_id: int, class_id: str) -> tuple[Decimal, Decimal]:
    return (get_available_balance(seat_id, class_id, "checking"), get_available_balance(seat_id, class_id, "savings"))


def reconstruct_posted_balance(class_id: str, seat_id: int, account_type: str, through_posting_sequence: int | None = None) -> LedgerProofResult:
    if not class_id or not seat_id or account_type not in {"checking", "savings"}:
        return LedgerProofResult("UNAVAILABLE", complete=False, code="invalid_scope")
    query = Transaction.query.filter(
        Transaction.class_id == class_id, Transaction.seat_id == seat_id,
        Transaction.account_type == account_type, Transaction.status == TransactionStatus.POSTED,
        _non_void_filter(), Transaction.posting_sequence.isnot(None),
    )
    boundary = through_posting_sequence
    if boundary is None:
        boundary = db.session.query(db.func.max(Transaction.posting_sequence)).filter(Transaction.class_id == class_id).scalar()
    if boundary is None:
        return LedgerProofResult("UNAVAILABLE", complete=False, code="missing_posting_boundary")
    total = query.filter(Transaction.posting_sequence <= boundary).with_entities(db.func.coalesce(db.func.sum(Transaction.amount_cents), 0)).scalar()
    return LedgerProofResult("PASS", reconstructed_cents=int(total or 0), boundary=int(boundary))


def reconstruct_available_balance(class_id: str, seat_id: int, account_type: str) -> LedgerProofResult:
    posted = reconstruct_posted_balance(class_id, seat_id, account_type)
    if posted.outcome != "PASS":
        return posted
    pending = db.session.query(db.func.coalesce(db.func.sum(Transaction.amount_cents), 0)).filter(
        Transaction.class_id == class_id, Transaction.seat_id == seat_id,
        Transaction.account_type == account_type, Transaction.status == TransactionStatus.PENDING,
        _non_void_filter(),
    ).scalar()
    return LedgerProofResult("PASS", reconstructed_cents=posted.reconstructed_cents + int(pending or 0), boundary=posted.boundary)


def verify_transfer(class_id: str, correlation_id: str) -> TransferProofResult:
    if not class_id or not correlation_id:
        return TransferProofResult("UNAVAILABLE", 0, False, False, False, False, False, "invalid_scope")
    rows = Transaction.query.filter_by(class_id=class_id, correlation_id=correlation_id).all()
    if not rows:
        return TransferProofResult("UNAVAILABLE", 0, False, False, False, False, False, "missing_transfer")
    amounts = [int(row.amount_cents or 0) for row in rows]
    seats = {row.seat_id for row in rows}
    accounts = {row.account_type for row in rows}
    signs = {value > 0 for value in amounts}
    scope_ok = len(seats) == 1 and all(row.class_id == class_id for row in rows)
    pair_ok = len(rows) == 2 and accounts == {"checking", "savings"} and signs == {True, False}
    magnitude_ok = len(amounts) == 2 and abs(amounts[0]) == abs(amounts[1])
    zero_sum = sum(amounts) == 0
    posting_ok = all(
        row.posting_sequence is not None
        and row.status == TransactionStatus.POSTED
        and not row.is_void
        for row in rows
    )
    if not posting_ok and scope_ok and pair_ok and magnitude_ok and zero_sum:
        return TransferProofResult("UNAVAILABLE", len(rows), scope_ok, pair_ok, magnitude_ok, zero_sum, False, "missing_posting_evidence")
    passed = scope_ok and pair_ok and magnitude_ok and zero_sum and posting_ok
    return TransferProofResult("PASS" if passed else "FAIL", len(rows), scope_ok, pair_ok, magnitude_ok, zero_sum, posting_ok, None if passed else "transfer_contract_violation")


__all__ = ["LedgerProofResult", "TransferProofResult", "get_posted_balance", "get_pending_balance_delta", "get_available_balance", "get_available_balances", "reconstruct_posted_balance", "reconstruct_available_balance", "verify_transfer"]
