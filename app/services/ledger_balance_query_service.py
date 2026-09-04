from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import NamedTuple
from sqlalchemy import func, tuple_

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


def _invalid_balance_scope(class_id: str, seat_id: int, account_type: str) -> bool:
    return not class_id or not seat_id or account_type not in {"checking", "savings"}


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


def get_batch_balances_by_class_seat(class_seat_pairs):
    """Read scoped checking, savings, and existing earnings display totals."""
    raw_balances = defaultdict(lambda: {"checking_cents": 0, "savings_cents": 0, "earnings": Decimal("0.00")})
    normalized_pairs = {(str(class_id), int(seat_id)) for class_id, seat_id in (class_seat_pairs or []) if class_id and seat_id}
    if not normalized_pairs:
        return raw_balances
    class_ids = sorted({class_id for class_id, _ in normalized_pairs})
    seat_ids = sorted({seat_id for _, seat_id in normalized_pairs})
    scope = tuple_(LedgerBalanceSnapshot.class_id, LedgerBalanceSnapshot.seat_id)
    tx_scope = tuple_(Transaction.class_id, Transaction.seat_id)
    for rec in db.session.query(
        LedgerBalanceSnapshot.class_id, LedgerBalanceSnapshot.seat_id,
        LedgerBalanceSnapshot.account_type, LedgerBalanceSnapshot.posted_balance_cents,
    ).filter(
        LedgerBalanceSnapshot.class_id.in_(class_ids), LedgerBalanceSnapshot.seat_id.in_(seat_ids),
        scope.in_(list(normalized_pairs)),
    ).all():
        key = (str(rec.class_id), int(rec.seat_id))
        if rec.account_type == "checking":
            raw_balances[key]["checking_cents"] = rec.posted_balance_cents
        elif rec.account_type == "savings":
            raw_balances[key]["savings_cents"] = rec.posted_balance_cents
    for rec in db.session.query(
        Transaction.class_id, Transaction.seat_id, Transaction.account_type,
        func.sum(Transaction.amount_cents),
    ).filter(
        Transaction.class_id.in_(class_ids), Transaction.seat_id.in_(seat_ids),
        tx_scope.in_(list(normalized_pairs)), Transaction.status == TransactionStatus.PENDING,
        _non_void_filter(),
    ).group_by(Transaction.class_id, Transaction.seat_id, Transaction.account_type).all():
        key = (str(rec.class_id), int(rec.seat_id))
        if str(rec.account_type).lower() in {"checking", "savings"}:
            raw_balances[key][f"{str(rec.account_type).lower()}_cents"] += int(rec[3] or 0)
    for rec in db.session.query(
        Transaction.class_id, Transaction.seat_id, func.sum(Transaction.amount),
    ).filter(
        Transaction.class_id.in_(class_ids), Transaction.seat_id.in_(seat_ids),
        tx_scope.in_(list(normalized_pairs)), Transaction.amount > 0,
        _non_void_filter(), ~Transaction.description.ilike("Transfer%"),
    ).group_by(Transaction.class_id, Transaction.seat_id).all():
        raw_balances[(str(rec.class_id), int(rec.seat_id))]["earnings"] = _quantize_currency(rec[2])
    return raw_balances


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


def verify_posted_balance(class_id: str, seat_id: int, account_type: str) -> LedgerProofResult:
    """Compare the stored balance projection with canonical posted history."""
    if _invalid_balance_scope(class_id, seat_id, account_type):
        return LedgerProofResult("UNAVAILABLE", complete=False, code="invalid_scope")
    snapshot = LedgerBalanceSnapshot.query.filter_by(
        class_id=class_id, seat_id=seat_id, account_type=account_type
    ).first()
    reconstructed = reconstruct_posted_balance(class_id, seat_id, account_type)
    if reconstructed.outcome != "PASS":
        return reconstructed
    if snapshot is None:
        return LedgerProofResult("UNAVAILABLE", boundary=reconstructed.boundary, complete=False, code="missing_snapshot")
    stored = int(snapshot.posted_balance_cents)
    if stored != reconstructed.reconstructed_cents:
        return LedgerProofResult("FAIL", reconstructed_cents=reconstructed.reconstructed_cents,
                                 boundary=reconstructed.boundary, complete=True, code="posted_balance_mismatch")
    return reconstructed


def verify_available_balance(class_id: str, seat_id: int, account_type: str) -> LedgerProofResult:
    """Compare the normal Ledger read with independent canonical reconstruction."""
    if _invalid_balance_scope(class_id, seat_id, account_type):
        return LedgerProofResult("UNAVAILABLE", complete=False, code="invalid_scope")
    reconstructed = reconstruct_available_balance(class_id, seat_id, account_type)
    if reconstructed.outcome != "PASS":
        return reconstructed
    observed = get_available_balance(seat_id, class_id, account_type)
    observed_cents = int(observed * 100)
    if observed_cents != reconstructed.reconstructed_cents:
        return LedgerProofResult("FAIL", reconstructed_cents=reconstructed.reconstructed_cents,
                                 boundary=reconstructed.boundary, complete=True, code="available_balance_mismatch")
    return reconstructed


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


__all__ = ["LedgerProofResult", "TransferProofResult", "get_posted_balance", "get_pending_balance_delta", "get_available_balance", "get_available_balances", "get_batch_balances_by_class_seat", "reconstruct_posted_balance", "reconstruct_available_balance", "verify_posted_balance", "verify_available_balance", "verify_transfer"]
